import chess
import pytest
from mate_explanation import explain_mate, finish_line

@pytest.mark.parametrize('fen',[
 '7k/6Q1/5K2/8/8/8/8/8 b - - 0 1',
 'R3k3/6Q1/8/1B6/8/8/8/4K3 b - - 0 1',
 'R3k3/3p2Q1/8/8/8/8/8/4K3 b - - 0 1',
])
def test_mate_cells_and_mirrored_white(fen):
 for b in (chess.Board(fen),chess.Board(fen).mirror()):
  before=b.fen();r=explain_mate(b)
  assert r['available'] and r['legal_replies']==0 and len(r['cells'])==8
  assert b.fen()==before
  for cell in r['cells']:
   if cell['square'] is None:assert cell['reasons']==['보드 밖'];continue
   dest=chess.parse_square(cell['square']);trial=b.copy()
   trial.remove_piece_at(b.king(b.turn));trial.remove_piece_at(dest)
   trial.set_piece_at(dest,chess.Piece(chess.KING,b.turn))
   assert {a['square'] for a in cell['attackers']}=={chess.square_name(a) for a in trial.attackers(not b.turn,dest)}
   assert not cell['legal'] and cell['reasons']


def test_vacated_origin_reveals_rook_and_multiple_attackers():
 b=chess.Board('R3k3/6Q1/8/1B6/8/8/8/4K3 b - - 0 1')
 assert chess.A8 not in b.attackers(chess.WHITE,chess.F8)
 r=explain_mate(b);assert len(r['checkers'])==2
 cell=next(c for c in r['cells'] if c['square']=='f8')
 assert {a['square'] for a in cell['attackers']}=={'a8','g7'}


def test_capture_removes_attacker_and_king_adjacency():
 r=explain_mate(chess.Board('7k/6Q1/5K2/8/8/8/8/8 b - - 0 1'))
 c=next(c for c in r['cells'] if c['square']=='g7')
 assert c['attackers']==[{'square':'f6','piece':'K'}]
 assert '상대 왕과 인접' in c['reasons']

@pytest.mark.parametrize('fen',[
 chess.STARTING_FEN,'k7/8/1QK5/8/8/8/8/8 b - - 0 1',
 '7k/6Q1/8/8/8/8/8/K7 b - - 0 1',
 'R3k3/3b4/8/8/8/8/8/4K3 b - - 0 1'])
def test_nonmate_never_explained(fen):assert not explain_mate(chess.Board(fen))['available']


def test_multi_ply_line_and_invalid_line():
 r=finish_line(chess.STARTING_FEN,['f2f3','e7e5','g2g4','d8h4'])
 assert r['available'] and r['defender']=='white'
 assert not finish_line(chess.STARTING_FEN,['a1a8'])['available']
 assert not finish_line(chess.STARTING_FEN,['e2e4'])['available']

from test_qa_behavior import api, seed, FEN
import time
import v8_server
import v9_server

@pytest.mark.parametrize('promotion',['q','r'])
def test_actual_alternative_promotion_explained(api,monkeypatch,promotion):
 c,s=api;seed(monkeypatch,s,['d7d8b','g8h8','d8f7'])
 result=c.post('/api/v9/puzzle/move',json={'move':'d7d8'+promotion}).json()
 explanation=result['mate_explanation']
 assert explanation['available'] and explanation['fen']==result['completed_fen']
 assert chess.Board(explanation['fen']).piece_at(chess.D8).symbol()==promotion.upper()
 assert c.get('/api/v9/session/puzzle').json()['result']['mate_explanation']==explanation

@pytest.mark.parametrize('correct',[True,False])
def test_diagnosis_multi_move_gates_explanation_without_advancing(api,monkeypatch,correct):
 c,s=api
 original=next(p for p in v9_server.LIB.values() if 'mateIn2' in p['themes'] and finish_line(p['fen'],p['moves'])['available'])
 b=chess.Board(original['fen']);b.push_uci(original['moves'][0]);fen=b.fen()
 q={'id':0,'fen':fen,'answers':[original['moves'][1]],'domain':'mate','domain_name':'체크메이트 계산','difficulty':1,'puzzle_id':original['id']}
 monkeypatch.setattr(v8_server,'questions',lambda _: [q])
 s['assessment_v8']={'seed':1,'phase':'questions','index':0,'shown_at':time.time(),'log':[]}
 move=q['answers'][0] if correct else next(m.uci() for m in b.legal_moves if m.uci() not in q['answers'] and not (lambda x:x.is_checkmate())(after(b,m)))
 feedback=c.post('/api/v8/assessment/answer',json={'id':0,'move':move}).json()['feedback']
 assert feedback['correct']==correct
 assert ('mate_explanation' in feedback)==correct
 if correct:
  assert feedback['mate_explanation']['available']
  assert feedback['answer_fen']!=feedback['mate_explanation']['fen']
  assert c.get('/api/v8/assessment/status').json()['feedback']==feedback
 assert s['assessment_v8']['index']==0 and len(s['assessment_v8']['log'])==1

def after(board,move):
 b=board.copy();b.push(move);return b


def test_diagnostic_alternative_mate_uses_actual_move(api,monkeypatch):
 c,s=api;seed(monkeypatch,s,['d7d8b','g8h8','d8f7'])
 q={'id':0,'fen':FEN,'answers':['d7d8b'],'domain':'mate','domain_name':'메이트','difficulty':1,'puzzle_id':'fixture'}
 monkeypatch.setattr(v8_server,'questions',lambda _: [q])
 s['assessment_v8']={'seed':1,'phase':'questions','index':0,'shown_at':time.time(),'log':[]}
 f=c.post('/api/v8/assessment/answer',json={'id':0,'move':'d7d8q'}).json()['feedback']
 assert f['correct'] and f['answer']=='d7d8q'
 assert f['mate_explanation']['fen']==f['answer_fen']
 assert chess.Board(f['answer_fen']).piece_at(chess.D8).symbol()=='Q'


def test_truncated_mate_corpus_reports_unavailable(api,monkeypatch):
 c,s=api;seed(monkeypatch,s,['d7d8b'])
 r=c.post('/api/v9/puzzle/move',json={'move':'d7d8b'}).json()
 assert r['correct'] and r['solved'] and not r['mate_explanation']['available']
