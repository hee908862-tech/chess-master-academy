"""Real chess rules and isolated DB; no production account writes."""
import copy
import json
import os
from pathlib import Path
import chess
import pytest
from fastapi import HTTPException
from test_runtime_isolation import runtime
from study_server import courses,references,key,replay,note,opening_position,OpeningPosition,DATA


@pytest.mark.parametrize('line,expected',[
    ('e4 e5 Ke2','백 Ke2: 킹을 e1에서 e2로 옮깁니다.'),
    ('e4 e5 Qh5','백 Qh5: 퀸을 d1에서 h5로 옮깁니다.'),
    ('h4 a6 Rh3','백 Rh3: 룩을 h1에서 h3로 옮깁니다.'),
    ('e4 e5 Bc4','백 Bc4: 비숍을 f1에서 c4로 옮깁니다.'),
    ('Nf3','백 Nf3: 나이트를 g1에서 f3로 옮깁니다.'),
    ('e4','백 e4: 폰을 e2에서 e4로 옮깁니다.'),
])
def test_piece_object_particles_in_move_explanation(line,expected):
    board=chess.Board();moves=[]
    for san in line.split():
        move=board.parse_san(san);moves.append(move.uci());board.push(move)
    assert note({'moves':moves,'notes':{}},len(moves)-1)['facts'].startswith(expected)


def test_every_authored_and_reference_line_is_legal_and_source_hashes_match():
    import hashlib
    manifest=json.loads((DATA/'SOURCE.json').read_text())
    for name,digest in manifest['sha256'].items():assert hashlib.sha256((DATA/name).read_bytes()).hexdigest()==digest
    assert len(courses())==55 and len({c['family'] for c in courses().values()})==11
    assert sum(len(c['notes']) for c in courses().values())==192
    for c in courses().values():
        b=replay(chess.STARTING_FEN,c['moves']);assert key(b)==c['positions'][-1]
        result=opening_position(OpeningPosition(course_id=c['id'],moves=c['moves']))
        assert result['theory_end'] and result['plans'] and result['structure']
    for row in references():
        b=chess.Board()
        for san in row['pgn'].split():
            if not san[0].isdigit():b.push_san(san)
        assert b.is_valid(),row['name']


def test_graph_transposition_rights_unknown_move_and_recall():
    c=courses()['italian-pianissimo'];moves=['e2e4','e7e5','g1f3','b8c6','f1c4','g8f6','d2d3','f8c5']
    result=opening_position(OpeningPosition(course_id=c['id'],moves=moves))
    assert result['transposed'] and result['on_course']
    unknown=opening_position(OpeningPosition(course_id=c['id'],moves=['a2a3']))
    assert unknown['unregistered'] and '오답' in unknown['message']
    recalled=opening_position(OpeningPosition(course_id=c['id'],moves=c['moves'][:8],mode='recall'))
    assert recalled['options']==[] and recalled['note'] is None and recalled['next_note'] is None and recalled['plans'] is None
    a=chess.Board();b=a.copy();b.castling_rights=0;assert key(a)!=key(b)
    a=chess.Board('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1');b=a.copy();b.ep_square=None;assert key(a)!=key(b)
    b=a.copy();b.turn=not b.turn;assert key(a)!=key(b)


def test_exploration_preserves_all_account_state_and_actual_engine(runtime,monkeypatch):
    server,(client,_)=runtime;path=os.environ.get('STOCKFISH_PATH','/tmp/chess-stockfish/usr/games/stockfish')
    monkeypatch.setattr(server,'STOCKFISH_PATH',path)
    before=copy.deepcopy(dict(server.get_state('RUNTIME-A')))
    r=client.post('/api/study/position',json={'moves':['e2e4'],'engine':True})
    assert r.status_code==200,r.text
    board=chess.Board();board.push_uci('e2e4');assert chess.Move.from_uci(r.json()['reply']) in board.legal_moves
    assert dict(server.get_state('RUNTIME-A'))==before
    for table in ['journey_progress','learning_progress']:
        with server.db() as conn:
            row=server.execute(conn,f'SELECT state FROM {table} WHERE code=?',('RUNTIME-A',)).fetchone()
            assert not row or not json.loads(row['state']).get('attempts')


@pytest.mark.parametrize('fen,move,expected',[
 ('7k/P7/8/8/8/8/8/K7 w - - 0 1','a7a8n','n'),
 ('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1','e1g1','castled'),
 ('4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1','e5d6','ep')])
def test_special_moves(runtime,fen,move,expected):
    _,(c,_)=runtime;r=c.post('/api/study/position',json={'fen':fen,'moves':[move]});assert r.status_code==200
    b=chess.Board(r.json()['fen'])
    if expected=='n':assert b.piece_type_at(chess.A8)==chess.KNIGHT
    elif expected=='castled':assert b.piece_type_at(chess.F1)==chess.ROOK
    else:assert not b.piece_at(chess.D5)


def test_terminal_repetition_invalid_and_bounded_busy(runtime,monkeypatch):
    import study_server
    from engine_budget import EngineBusy
    server,(c,_)=runtime
    for moves in [['f2f3','e7e5','g2g4','d8h4'],(['g1f3','g8f6','f3g1','f6g8']*2)[:7]]:
        r=c.post('/api/study/position',json={'moves':moves});assert r.json()['terminal'] and not r.json()['legal']
    r=c.post('/api/study/position',json={'fen':'7k/5K2/4Q3/8/8/8/8/8 w - - 0 1','moves':['e6g6']})
    assert r.json()['ending']=='스테일메이트'
    assert c.post('/api/study/position',json={'moves':['e2e5']}).status_code==400
    monkeypatch.setattr(server,'STOCKFISH_PATH',__file__)
    def busy(*a,**k):raise EngineBusy()
    monkeypatch.setattr(study_server,'open_engine',busy)
    r=c.post('/api/study/position',json={'engine':True});assert r.status_code==503 and r.headers['Retry-After']=='1'


def test_opening_bookmark_cas_separate_from_game_progress(runtime):
    server,(c,_)=runtime;before=copy.deepcopy(dict(server.get_state('RUNTIME-A')))
    data={'course_id':'french-advance','moves':['e2e4','e7e6'],'mode':'recall','orientation':'black','revision':0}
    r=c.post('/api/study/openings/save',json=data);assert r.status_code==200
    assert c.post('/api/study/openings/save',json={**data,'moves':[]}).status_code==409
    saved=c.get('/api/study/openings').json()['saved'];assert saved['moves']==data['moves'] and saved['revision']==1
    server.initdb();assert c.get('/api/study/openings').json()['saved']==saved
    after=dict(server.get_state('RUNTIME-A'));after.pop('opening_study');assert before==after


def test_commentary_matches_position_and_does_not_follow_free_moves():
    for c in courses().values():
        end=opening_position(OpeningPosition(course_id=c['id'],moves=c['moves']))
        b=replay(chess.STARTING_FEN,c['moves'])
        expected=' · '.join(label+' 폰: '+', '.join(chess.square_name(s) for s in b.pieces(chess.PAWN,color)) for color,label in [(chess.WHITE,'백'),(chess.BLACK,'흑')])
        assert end['structure']==expected and end['plans']==c['ending'] and end['family_overview'] is None
        free=opening_position(OpeningPosition(course_id=c['id'],moves=['a2a3']))
        assert free['structure'] is None and free['plans'] is None and free['family_overview'] is None
    for name in ['ruy-berlin','ruy-exchange']:
        c=courses()[name];b=replay(chess.STARTING_FEN,c['moves'])
        assert not b.pawns & b.occupied_co[chess.WHITE] & chess.BB_FILE_D
        end=opening_position(OpeningPosition(course_id=name,moves=c['moves']))
        assert 'c3-d4' not in end['plans']
    dragon=courses()['sicilian-dragon'];b=replay(chess.STARTING_FEN,dragon['moves'])
    assert b.piece_at(chess.C2)==chess.Piece(chess.PAWN,chess.WHITE)
    assert not b.pawns & b.occupied_co[chess.BLACK] & chess.BB_FILE_C
    assert '반열린 c파일' in dragon['notes'][20]
    najdorf=courses()['sicilian-najdorf'];b=replay(chess.STARTING_FEN,najdorf['moves'][:19])
    assert b.king(chess.WHITE)==chess.C1 and b.king(chess.BLACK)==chess.E8
    assert '아직 e8' in najdorf['notes'][19]

def test_new_systems_exact_positions_note_scope_and_transposition():
    cs=courses()
    assert len([c for c in cs.values() if c['family']=='london'])==7
    for c in cs.values():
        assert all(0<k<=len(c['moves']) for k in c['notes'])
    # Torre has a relative queen pin after e6; Veresov/Trompowsky still have e7.
    for id,ply,square in [('torre',5,'e6'),('veresov',5,'e7'),('trompowsky',3,'e7')]:
        b=replay(chess.STARTING_FEN,cs[id]['moves'][:ply])
        assert b.piece_at(chess.parse_square(square))==chess.Piece(chess.PAWN,chess.BLACK)
    b=replay(chess.STARTING_FEN,cs['grunfeld']['moves'])
    assert len(b.pieces(chess.PAWN,chess.WHITE)&chess.BB_FILE_C)==1
    assert b.piece_at(chess.D4)==chess.Piece(chess.PAWN,chess.WHITE)
    b=chess.Board()
    for san in 'd4 Nf6 Nc3 d5 Bf4'.split():b.push_san(san)
    r=opening_position(OpeningPosition(course_id='jobava-exchange',moves=[m.uci() for m in b.move_stack]))
    assert r['on_course'] and r['transposed']
    # End plans must not leak into an arbitrary legal branch.
    for id in ['london-core','jobava-exchange','catalan','grunfeld']:
        r=opening_position(OpeningPosition(course_id=id,moves=['a2a3']))
        assert r['unregistered'] and not r['plans']
