"""Movement sandbox contracts; only isolated synthetic accounts."""
import copy
from concurrent.futures import ThreadPoolExecutor
import chess
import pytest
from fastapi.testclient import TestClient
from test_onboarding import api
from movement_content import UNITS, BY_ID, replay, VERSION, POLICY
from movement_server import attach_movement, KEY, summary

@pytest.fixture
def movement(api):
    c,s=api;attach_movement(c.app,vars(s));return c,s

def start(c,s=None,unit='rook-path',action='start',request='request-first'):
    s=s or c.get('/api/movement').json()
    r=c.post('/api/movement/start',json=dict(revision=s['revision'],unit_id=unit,action=action,request_id=request))
    assert r.status_code==200,r.text
    return r.json()

def body(s,moves,**extra):
    return dict(unit_id=s['active']['unit_id'],session_id=s['active']['session_id'],revision=s['revision'],version=VERSION,policy=POLICY,moves=moves,**extra)

def save(c,s,moves,**extra):
    r=c.post('/api/movement/save',json=body(s,moves,**extra));assert r.status_code==200,r.text;return r.json()

PATHS={
'rook-path':['b2b5','b5f5','f5f3'],'rook-block':['c2c4','c4f4','f4f6'],'rook-apply':['e3f3','f3f4'],
'bishop-path':['b2e5','e5h2','h2f4'],'bishop-block':['c1b2','b2a3','a3d6'],'bishop-apply':['f3g4','g4h5'],
'queen-path':['d2d5','d5g5','g5e3'],'queen-capture':['b2b5','b5e5','e5g3'],'queen-apply':['e4f4','f4f5'],
'knight-path':['b2c4','c4e5','e5g4'],'knight-jump':['d3f4','f4e6','e6c5'],'knight-apply':['f3h4','h4f5'],
'king-path':['c3c4','c4d5','d5e4'],'king-apply':['f3g3','g3g4'],
'pawn-forward':['c2c3','c3c4','c4c5','c5c6'],'pawn-capture':['d3e4','e4e5','e5e6'],'pawn-apply':['f2f4','f4f5']}

@pytest.mark.parametrize('u',[u for u in UNITS if u['mode']!='rule'],ids=lambda u:u['id'])
def test_all_units_complete_and_actual_targets(u):
    r=replay(u,PATHS[u['id']]);assert r['done'];assert not r['legal']
    with pytest.raises(ValueError):replay(u,PATHS[u['id']]+[PATHS[u['id']][-1]])

def test_sandbox_detours_blockers_jump_and_pawn_deadend():
    r=replay(BY_ID['rook-path'],['b2c2','c2c5','c5b5','b5f5','f5f3']);assert r['done']
    assert replay(BY_ID['knight-path'],['b2d3'])['remaining']==BY_ID['knight-path']['targets']
    for name,moves in [('rook-block',['c2c6']),('bishop-block',['c1f4']),('king-path',['c3c5']),('pawn-forward',['c2d3']),('rook-path',['0000'])]:
        with pytest.raises(ValueError):replay(BY_ID[name],moves)
    assert replay(BY_ID['pawn-capture'],['d3d4'])['stuck']
    assert replay(BY_ID['pawn-forward'],['c2c4','c4c5','c5c6'])['done']
    # A same-side second move is educational, never passed to regular-game legality.
    b=chess.Board(BY_ID['rook-path']['fen']);b.push_uci('b2b5')
    assert chess.Move.from_uci('b5f5') not in b.pseudo_legal_moves
    assert replay(BY_ID['rook-path'],['b2b5','b5f5'])['source']=='f5'

def test_preserves_all_existing_state_get_and_old_default(movement):
    c,server=movement;s=server.get_state('INTRO-QA')
    s['foundation_v1']={'courses':{'rook-first-v1':{'step':3}},'updated_at':'2026-01-01'}
    s['active_game']={'saved':True};s['assessment_v8_history']=[{'original':True}];server.save_state('INTRO-QA',s)
    before=copy.deepcopy(dict(server.get_state('INTRO-QA')))
    assert not c.get('/api/movement').json()['summary']['preferred']
    assert dict(server.get_state('INTRO-QA'))==before
    state=start(c);state=save(c,state,PATHS['rook-path'])
    assert state==c.get('/api/movement').json()
    after=dict(server.get_state('INTRO-QA'));after.pop(KEY);assert after==before
    assert state['summary']['preferred']

def test_snapshot_idempotency_prefix_conflict_and_restart_archive(movement):
    c,server=movement;s=start(c);same=start(c,{'revision':0});assert same==s
    req=body(s,['b2c2']);a=save(c,s,req['moves']);assert c.post('/api/movement/save',json=req).json()==a
    assert c.post('/api/movement/save',json=body(a,['b2b5'])).status_code==409
    assert c.post('/api/movement/save',json=body(a,[])).status_code==409
    b=save(c,a,['b2c2','c2c5']);assert b['active']['source']=='c5'
    restarted=start(c,b,action='restart',request='request-restart')
    assert restarted['active']['session_id']!=s['active']['session_id']
    assert server.get_state('INTRO-QA')[KEY]['history'][0]['moves']==['b2c2','c2c5']
    assert c.post('/api/movement/save',json=body(b,['b2c2','c2c5','c5b5'])).status_code==409

def test_auth_account_and_version_protection(movement):
    c,server=movement;s=start(c)
    assert TestClient(c.app).get('/api/movement').status_code==401
    other=TestClient(c.app);token=other.post('/api/register',json={'code':'MOVE-OTHER','pin':'local-move-qa'}).json()['token'];other.headers['Authorization']='Bearer '+token
    assert other.post('/api/movement/save',json=body(s,['b2b5'])).status_code==409
    req=body(s,['b2b5']);req['policy']='unknown';assert c.post('/api/movement/save',json=req).status_code==409
    assert c.get('/api/movement').json()==s

def test_completion_results_next_and_limits(movement):
    c,server=movement;s=start(c,unit='rook-apply')
    assert c.post('/api/movement/start',json={'action':'next','revision':s['revision'],'request_id':'request-next'}).status_code==409
    s=save(c,s,['e3f3','f3f4']);assert s['active']['result']=='first_application'
    s=start(c,s,unit='rook-apply',action='restart',request='request-restart')
    s=save(c,s,['e3f3','f3f4']);assert s['active']['result']=='practice_application'
    s=start(c,s,action='next',request='request-next');assert s['active']['unit_id']==UNITS[next(i for i,u in enumerate(UNITS) if u['id']=='rook-apply')+1]['id']
    s=start(c,s,unit='bishop-path',request='request-bishop')
    req=body(s,['b2c3','c3b2']*65);assert c.post('/api/movement/save',json=req).status_code==422
    s=save(c,s,['b2c3','c3b2']*64);assert len(s['active']['moves'])==128 and not s['active']['done']

def test_concurrent_divergence_one_winner(movement):
    c,server=movement;s=start(c)
    def run(path):return TestClient(c.app,headers=dict(c.headers)).post('/api/movement/save',json=body(s,path)).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,[['b2b5'],['b2c2']]))
    assert sorted(results)==[200,409]

def test_restart_preserves_historical_completion_and_run_policy(movement):
    c,server=movement;s=start(c);s=save(c,s,PATHS['rook-path'])
    s=start(c,s,action='restart',request='restart-completed')
    assert s['summary']['completed']==1 and not s['active']['done']
    assert s['units'][0]['completed_before'] and not s['units'][0]['done']
    saved=server.get_state('INTRO-QA')[KEY]
    assert saved['history'][0]['done']
    assert saved['history'][0]['version']==VERSION and saved['units']['rook-path']['policy']==POLICY

def test_get_recovery_retains_first_snapshot_and_allows_only_prefix(movement):
    c,server=movement;s=start(c)
    first=save(c,s,['b2b5'])  # Response could be lost by the client.
    restored=TestClient(c.app,headers=dict(c.headers)).get('/api/movement').json()
    assert restored==first
    final=save(c,restored,['b2b5','b5f5','f5f3'])
    assert final['active']['done'] and final['active']['result']=='guided'
    assert c.get('/api/movement').json()==final
