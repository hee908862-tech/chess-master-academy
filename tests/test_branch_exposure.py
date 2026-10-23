"""Owned local fixture exposure; never modifies operating identities or reports."""
import copy,json
import chess
from fastapi.testclient import TestClient
from test_runtime_isolation import runtime
import branch_exposure as branch
import learning_server


def test_authenticated_idempotent_canonical_and_state_preservation(runtime):
    server,(a,b)=runtime
    before=copy.deepcopy(dict(server.get_state('RUNTIME-A')))
    assert TestClient(server.app).post('/api/study/exposure',json={'fens':[chess.STARTING_FEN]}).status_code==401
    first=a.post('/api/study/exposure',json={'fens':[chess.STARTING_FEN,chess.STARTING_FEN]})
    assert first.status_code==200 and first.json()['added']==1
    clock=' '.join(chess.STARTING_FEN.split()[:4])+' 7 5'
    assert a.post('/api/study/exposure',json={'fens':[clock]}).json()['added']==0
    after=dict(server.get_state('RUNTIME-A'));record=after.pop(branch.FIELD)
    assert after==before and len(record['positions'])==1
    assert branch.FIELD not in server.get_state('RUNTIME-B')
    assert a.post('/api/study/exposure',json={'fens':['8/8/8/8/8/8/8/8 w - - 0 1']}).status_code==400
    assert a.post('/api/study/exposure',json={'fens':[' '.join(chess.STARTING_FEN.split()[:4])]}).status_code==400
    assert a.post('/api/study/exposure',json={'fens':[clock]*33}).status_code==422
    assert dict(server.get_state('RUNTIME-A'))=={**before,branch.FIELD:record}


def test_active_diagnostic_exposure_loses_independence_not_original_record(runtime):
    server,(a,_)=runtime
    r=a.post('/api/journey/start',json={'mode':'domain','competency':'mate'});assert r.status_code==200
    with server.db() as conn:state=json.loads(server.execute(conn,'SELECT state FROM journey_progress WHERE code=?',('RUNTIME-A',)).fetchone()['state'])
    s=state['active'];item=copy.deepcopy(s['items'][0]);old_results=copy.deepcopy(state['results'])
    assert a.post('/api/study/exposure',json={'fens':[item['fen']]}).status_code==200
    moved=a.post('/api/journey/action',json={'session_id':s['session_id'],'revision':s['revision'],'action':'move','move':item['line'][0]})
    assert moved.status_code==200
    with server.db() as conn:after=json.loads(server.execute(conn,'SELECT state FROM journey_progress WHERE code=?',('RUNTIME-A',)).fetchone()['state'])
    current=after['active']['items'][0]
    assert not current['app_new'] and not current['independent']
    assert current['line']==item['line'] and current['fen']==item['fen'] and after['results']==old_results


def test_future_learning_excludes_branch_position(runtime,monkeypatch):
    server,(a,b)=runtime;monkeypatch.setattr(learning_server.secrets,'choice',lambda rows:rows[0])
    first=b.post('/api/learning/start',json={'fresh':True});assert first.status_code==200
    exposed=first.json()
    assert a.post('/api/study/exposure',json={'fens':[exposed['fen']]}).status_code==200
    selected=a.post('/api/learning/start',json={'fresh':True});assert selected.status_code==200
    assert selected.json()['fen']!=exposed['fen']


def test_overflow_keeps_positions_and_failcloses_future_independence(runtime,monkeypatch):
    server,(a,_)=runtime;monkeypatch.setattr(branch,'LIMIT',1)
    board=chess.Board();board.push_uci('e2e4')
    r=a.post('/api/study/exposure',json={'fens':[chess.STARTING_FEN,board.fen()]});assert r.status_code==200
    assert r.json()['overflow'] and r.json()['recorded']==1
    record=server.get_state('RUNTIME-A')[branch.FIELD]
    assert record['positions'][0]['fen']==chess.STARTING_FEN and record['overflow']
    r=a.post('/api/journey/start',json={'mode':'domain','competency':'mate'});assert r.status_code==200
    with server.db() as conn:state=json.loads(server.execute(conn,'SELECT state FROM journey_progress WHERE code=?',('RUNTIME-A',)).fetchone()['state'])
    assert all(not x['app_new'] and x['exposure_unknown_reason']=='branch_exposure_limit' for x in state['active']['items'])
    r=a.post('/api/learning/start',json={'fresh':True});assert r.status_code==200
    with server.db() as conn:learning=json.loads(server.execute(conn,'SELECT state FROM learning_progress WHERE code=?',('RUNTIME-A',)).fetchone()['state'])
    active=learning['active'];card=learning['cards'][active['card_id']]
    assert not active['first_exposure'] and card['prior_exposed'] and card['exposure_unknown_reason']=='branch_exposure_limit'


def test_post_submission_exploration_does_not_rewrite_confirmed_observation(runtime):
    server,(a,_)=runtime
    r=a.post('/api/journey/start',json={'mode':'subskill','competency':'mate','topic':'mateIn1'});assert r.status_code==200
    with server.db() as conn:state=json.loads(server.execute(conn,'SELECT state FROM journey_progress WHERE code=?',('RUNTIME-A',)).fetchone()['state'])
    s=state['active'];item=s['items'][0]
    r=a.post('/api/journey/action',json={'session_id':s['session_id'],'revision':s['revision'],'action':'move','move':item['line'][0]});assert r.status_code==200 and r.json()['phase']=='feedback'
    with server.db() as conn:before=json.loads(server.execute(conn,'SELECT state FROM journey_progress WHERE code=?',('RUNTIME-A',)).fetchone()['state'])['active']['items'][0]
    assert before['app_new']
    assert a.post('/api/study/exposure',json={'fens':[item['fen']]}).status_code==200
    r=a.post('/api/journey/action',json={'session_id':s['session_id'],'revision':r.json()['revision'],'action':'next'});assert r.status_code==200
    with server.db() as conn:after=json.loads(server.execute(conn,'SELECT state FROM journey_progress WHERE code=?',('RUNTIME-A',)).fetchone()['state'])['active']['items'][0]
    assert before==after


def test_future_diagnostic_sampling_excludes_explored_positions(runtime,monkeypatch):
    import journey_server as journey
    server,(a,_)=runtime
    candidates=[r for r in journey.inventory()['mate'] if 600<=r['rating']<1000 and len(r['line'])<=5]
    first=candidates[0];second=next(r for r in candidates if not journey.footprint(first).intersection(journey.footprint(r)))
    monkeypatch.setattr(journey,'inventory',lambda:{'mate':[first,second]})
    assert a.post('/api/study/exposure',json={'fens':[first['fen']]}).status_code==200
    r=a.post('/api/journey/start',json={'mode':'gentle'});assert r.status_code==200
    assert r.json()['question']['fen']==second['fen']
