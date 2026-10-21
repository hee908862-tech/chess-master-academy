import copy
import json
import re
import sqlite3
from pathlib import Path
import chess
import pytest
from skill_index import score_areas, scaled, VERSION
from diagnostic_replay import replay_snapshot
from test_learning import setup
from test_journey import attach, post, saved
from test_growth_cycle import finish_diagnosis
from test_runtime_isolation import runtime


def item(file, band, outcome='completed'):
    b=chess.Board('7k/8/8/8/8/8/8/K7 w - - 0 1')
    b.set_piece_at(chess.parse_square(file+'2'), chess.Piece(chess.PAWN, True))
    return dict(puzzle_id=file,fen=b.fen(),line=[file+'2'+file+'3'],competency='mate',band=band,
                outcome=outcome,app_new=True,first_attempt=True,helped=False)


def test_new_scale_application_weight_bounds_and_duplicates():
    basic=[600,1200];advanced=[1200,1800]
    rows=[item('c',basic),item('d',basic),item('e',advanced,'verified_error'),item('f',advanced,'verified_error')]
    assert score_areas(rows)['mate']['score']==1201
    for i in rows:i['outcome']='verified_error' if i['outcome']=='completed' else 'completed'
    assert score_areas(rows)['mate']['score']==1800
    assert scaled(0)==1 and scaled(1)==3000
    for i in rows:i['outcome']='completed'
    assert score_areas(rows)['mate']['score']==3000
    before=copy.deepcopy(rows)
    for patch in [{'helped':True},{'first_attempt':False},{'app_new':False},{'outcome':'not_answered'},
                  {'outcome':'partial_execution'},{'outcome':'unverified_alternative'},{'outcome':'equivalent_alternative'}]:
        altered=copy.deepcopy(rows);altered[0].update(patch);p=score_areas(altered)['mate']
        assert p['score'] is None and p['unresolved']==1 and p['observed']==3
        assert p['bounds'][1]==3000
    duplicate=score_areas(rows+[rows[0]])['mate']
    assert duplicate['score'] is None and duplicate['observed']==4
    assert rows==before
    assert score_areas([])['strategy']['score'] is None


def test_inflight_old_diagnosis_finishes_with_old_scale_and_snapshots(setup):
    c,ns,legacy,path=attach(setup);legacy.clear()
    session=post(c,'start',{'mode':'balanced'})
    state=saved(path);state['active'].pop('scoring_version')
    state['results']=[{'id':'preserved','version':'old','mode':'old','items':[],'areas':[], 'at':'2026-01-01'}]
    with sqlite3.connect(path) as db:db.execute('UPDATE journey_progress SET state=? WHERE code=?',(json.dumps(state),'A'))
    result=finish_diagnosis(c,session,path,solve=True)
    assert result['score_version']=='growth-v1' and 'internal_skill' not in result
    assert all(a['performance']['score']==100 for a in result['areas'] if a['count'])
    assert saved(path)['results'][0]==state['results'][0]
    before=saved(path)
    row=result['items'][0]
    replay=c.get('/api/journey/replay/'+result['id']+'/'+row['id'])
    assert replay.status_code==200 and replay.json()['frames'][0]['fen']==row['fen']
    assert c.get('/api/journey/replay/'+result['id']+'/'+row['id'],headers={'Authorization':'B'}).status_code==404
    assert saved(path)==before


@pytest.mark.parametrize('fen,line',[
    ('r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 7 20',['e1g1','e8c8']),
    ('7k/8/8/3pP3/8/8/8/K7 w - d6 0 12',['e5d6']),
    ('7k/P7/8/8/8/8/8/K7 w - - 0 12',['a7a8n']),
    ('7k/8/8/8/8/8/p7/7K b - - 0 12',['a2a1r'])])
def test_replay_preserves_start_rights_and_all_frames(fen,line):
    original={'fen':fen,'line':line};before=copy.deepcopy(original);r=replay_snapshot(original)
    assert r['available'] and r['frames'][0]['fen']==fen
    b=chess.Board(fen)
    for frame,uci in zip(r['frames'][1:],line):
        san=b.san(chess.Move.from_uci(uci));b.push_uci(uci)
        assert frame['fen']==b.fen(en_passant='fen') and frame['san']==san
    assert original==before
    assert not replay_snapshot({'fen':fen,'line':['a1a8']})['available'] or 'R' in fen
    assert not replay_snapshot({'fen':fen.split()[0],'line':line})['available']


def test_exact_new_education_outcomes():
    from education_content import ROOK_AFTER,ROOK_APPLY,ROOKPAWN,DRAW50,DRAW150,NEW_LESSONS
    for fen,uci in [(ROOK_AFTER,'a1a8'),(ROOK_APPLY,'h1h8')]:
        b=chess.Board(fen);b.push_uci(uci);assert b.is_checkmate()
    b=chess.Board(ROOKPAWN);b.push_uci('b5b6');assert b.is_stalemate()
    b=chess.Board(DRAW50);b.push_uci('a2a3');assert b.can_claim_fifty_moves() and not b.is_seventyfive_moves()
    b=chess.Board(DRAW150);b.push_uci('a2a3');assert b.is_seventyfive_moves()
    for lesson in NEW_LESSONS:
        for step in lesson['steps']:
            if step['kind']=='move':
                for u in step['answers']:
                    b=chess.Board(step['fen']);assert b.is_valid();assert chess.Move.from_uci(u) in b.legal_moves;b.push_uci(u)
                    if step.get('reply'):assert chess.Move.from_uci(step['reply']) in b.legal_moves


def test_old_education_snapshot_can_continue_without_rewriting(runtime):
    from test_education import start,post as action
    from education_server import KEY,PREVIOUS_VERSION
    server,(a,b)=runtime;d=start(a);s=server.get_state('RUNTIME-A')
    s[KEY]['active']['version']=PREVIOUS_VERSION;before=copy.deepcopy(s[KEY]['active']['snapshot']);server.save_state('RUNTIME-A',s)
    d=a.get('/api/education').json();assert not d['active']['outdated']
    d=action(a,d,'answer',answer='c3');assert d.status_code==200
    r=server.get_state('RUNTIME-A')[KEY]['active'];assert r['version']==PREVIOUS_VERSION and r['snapshot']==before


def test_pieces_same_geometry_and_packaged_license():
    root=Path('public/assets/pieces')
    for theme in ['classic','royal']:
        for piece in 'PRNBQK':
            sources=[(root/theme/(color+piece+'.svg')).read_text() for color in 'wb']
            assert all('<text' not in s and '<script' not in s for s in sources)
            assert re.sub('#[0-9a-fA-F]{6}','COLOR',sources[0])==re.sub('#[0-9a-fA-F]{6}','COLOR',sources[1])
    assert 'Apache License' in (root/'chessnut-source/LICENSE.txt').read_text()
    assert 'skill_index.py diagnostic_replay.py' in Path('Dockerfile').read_text()
