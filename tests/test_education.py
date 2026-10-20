import copy
import chess
import pytest
from test_runtime_isolation import runtime
from education_content import *
from education_server import KEY

def post(c,d,action,**kw):return c.post('/api/education/action',json=dict(action=action,revision=d['revision'],attempt_id=(d.get('active') or {}).get('id',''),**kw))
def start(c,lesson='threat-observe',mode='review'):
 d=c.get('/api/education').json();r=post(c,d,'start',lesson_id=lesson,mode=mode);assert r.status_code==200,r.text;return r.json()
def finish_lesson(c,d):
 l=BY_ID[d['active']['lesson_id']]
 for s in l['steps']:
  r=post(c,d,'answer',answer=s['answers'][0]);assert r.status_code==200,r.text;d=r.json()
  r=post(c,d,'next');assert r.status_code==200,r.text;d=r.json()
 return d

def test_content_rule_facts():
 from foundation_content import BY_ID as foundations
 for l in LESSONS:
  assert l['prerequisite'] in foundations
  for s in l['steps']:
   b=chess.Board(s['fen']);assert b.is_valid()
   if s['kind']=='move':
    for u in s['answers']:
     b=chess.Board(s['fen']);assert chess.Move.from_uci(u) in b.legal_moves;b.push_uci(u)
     if s.get('reply'):b.push_uci(s['reply'])
 b=chess.Board(LOOSE);assert chess.C3 in b.attacks(chess.B4) and not b.is_check()
 for u in BY_ID['threat-observe']['steps'][1]['answers']:assert chess.parse_square(u[2:]) not in b.attacks(chess.B4)
 assert chess.C3 in chess.Board(DEFENDED).attacks(chess.B2)
 b=chess.Board(BISHOP);assert not any(m.from_square==chess.C1 for m in b.legal_moves)
 for u in BY_ID['plan-piece']['steps'][1]['answers']:
  b=chess.Board(BISHOP);b.push_uci(u);assert any(chess.square_rank(s)>0 for s in b.attacks(chess.C1) if b.piece_at(s) is None)
 b=chess.Board(FILE)
 for f in [3,4]:assert not any(b.piece_at(chess.square(f,r)) and b.piece_at(chess.square(f,r)).piece_type==chess.PAWN for r in range(8))
 b=chess.Board(OPPOSITION);assert b.is_attacked_by(True,chess.E5) and b.is_attacked_by(False,chess.E5)
 assert chess.Board(QUEEN).is_stalemate() and not chess.Board(QUEEN).is_check()
 assert [m.uci() for m in chess.Board(ROOK).legal_moves]==['a1a2']

@pytest.mark.parametrize('lesson',[l['id'] for l in LESSONS])
def test_complete_restore_isolated(runtime,lesson):
 server,(a,b)=runtime;before=dict(server.get_state('RUNTIME-A'));d=start(a,lesson)
 assert d['active']['step']['reason'] is None and d['active']['step']['examples']==[]
 d=finish_lesson(a,d);assert d['active']['phase']=='complete'
 assert a.get('/api/education').json()==d
 assert post(a,d,'next').status_code==409
 d=post(a,d,'finish').json();assert d['history'][0]['phase']=='complete'
 assert a.get('/api/education/history/'+d['history'][0]['id']).status_code==200
 assert b.get('/api/education/history/'+d['history'][0]['id']).status_code==404
 after=dict(server.get_state('RUNTIME-A'));after.pop(KEY);assert after==before
 assert b.get('/api/education').json()['active'] is None

def test_hint_wrong_partial_retry_cas_and_failure(runtime,monkeypatch):
 from fastapi import HTTPException
 server,(a,b)=runtime;d=start(a);original=copy.deepcopy(d)
 d=post(a,d,'answer',answer='g1').json();assert d['active']['misses']==1
 d=post(a,d,'hint').json();assert d['active']['hints']==1 and d['active']['step']['reason']
 assert post(a,original,'hint').status_code==409
 d=post(a,d,'finish').json();d=start(a);assert d['metrics']['threat-observe']['hints']==1 and d['metrics']['threat-observe']['misses']==1
 save=server.save_state;monkeypatch.setattr(server,'save_state',lambda *a:(_ for _ in ()).throw(HTTPException(503,'save failed')))
 assert post(a,d,'hint').status_code==503
 monkeypatch.setattr(server,'save_state',save);assert a.get('/api/education').json()==d
 d=post(a,d,'answer',answer='c3').json();d=post(a,d,'next').json()
 assert post(a,d,'answer',answer='c3c8').status_code==400
 d=post(a,d,'answer',answer='c3b1').json();assert not d['active']['answered'] and '우열' in d['active']['feedback']

@pytest.mark.parametrize('count',[63,64])
@pytest.mark.parametrize('phase',[None,'playing','complete'])
def test_capacity_start_and_finish(runtime,count,phase):
 server,(a,b)=runtime;d=start(a);s=server.get_state('RUNTIME-A');r=copy.deepcopy(s[KEY]['active']);s[KEY]['history']=[dict(r,id=str(i),phase='complete') for i in range(count)];s[KEY]['active']=dict(r,phase=phase) if phase else None;server.save_state('RUNTIME-A',s)
 d=a.get('/api/education').json();res=post(a,d,'start',lesson_id='plan-file')
 assert res.status_code==(200 if count==63 and phase is None else 409)
 if phase:
  if phase=='playing':assert post(a,d,'hint').status_code==200;d=a.get('/api/education').json()
  d=post(a,d,'finish').json();assert d['active'] is None and len(d['history'])==count+1
  assert not d['can_start']

def test_row_bytes_and_version_finish_recovery(runtime):
 server,(a,b)=runtime;d=start(a);s=server.get_state('RUNTIME-A');s[KEY]['active']['events']=[{'kind':'hint'}]*256;server.save_state('RUNTIME-A',s)
 d=a.get('/api/education').json();assert post(a,d,'hint').status_code==409
 assert post(a,d,'finish').status_code==200
 d=start(a);s=server.get_state('RUNTIME-A');s[KEY]['active']['padding']='x'*1048576;server.save_state('RUNTIME-A',s)
 d=a.get('/api/education').json();assert post(a,d,'hint').status_code==409
 d=post(a,d,'finish').json();assert d['active'] is None
 assert post(a,d,'start',lesson_id='plan-file').status_code==409
 s=server.get_state('RUNTIME-A');s[KEY]['history'][-1].pop('padding');server.save_state('RUNTIME-A',s)
 d=start(a);s=server.get_state('RUNTIME-A');s[KEY]['active']['version']='old';server.save_state('RUNTIME-A',s)
 d=a.get('/api/education').json();assert d['active']['outdated']
 assert post(a,d,'answer',answer='c3').status_code==409
 assert post(a,d,'finish').status_code==200

def test_repertoire_history_missing_side_time_not_inferred(runtime):
 from test_repertoire import start as repstart,post as reppost
 from repertoire_server import KEY as RKEY
 server,(a,b)=runtime;d=repstart(a,side='black');d=reppost(a,d,'finish').json()
 assert d['history'][0]['side']=='black' and d['history'][0]['at']
 s=server.get_state('RUNTIME-A');s[RKEY]['history'][0].pop('side');s[RKEY]['history'][0].pop('at');server.save_state('RUNTIME-A',s)
 d=a.get('/api/repertoire').json();assert d['history'][0]['side'] is None and d['history'][0]['at'] is None
