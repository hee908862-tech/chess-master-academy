import copy
from concurrent.futures import ThreadPoolExecutor
import chess
import pytest
from fastapi.testclient import TestClient
from test_onboarding import api
from foundation_content import COURSES, BY_ID, validate_content
from foundation_server import attach_foundations, KEY

@pytest.fixture
def foundation(api):
    c,server=api
    attach_foundations(c.app,vars(server))
    return c,server

def send(c,s,action,id,value=''):
    r=c.post('/api/foundations/action',json={'revision':s['revision'],'course_id':id,'action':action,'step':(s.get('active') or {}).get('step',0),'value':value})
    assert r.status_code==200,r.text
    return r.json()

def test_authored_positions_and_rules():
    validate_content()
    assert len(COURSES)==10
    castle=chess.Board(BY_ID['castling']['steps'][0]['fen'])
    assert chess.Move.from_uci('e1g1') in castle.legal_moves
    castle.castling_rights=0
    assert chess.Move.from_uci('e1g1') not in castle.legal_moves
    # Rook attacked on h1 still permits castling when the king's route is safe.
    b=chess.Board('k6r/8/8/8/8/8/8/4K2R w K - 0 1')
    assert b.is_valid() and chess.Move.from_uci('e1g1') in b.legal_moves
    b=chess.Board('k3r3/8/8/3pP3/8/8/8/4K3 w - d6 0 2')
    assert b.is_valid() and b.has_pseudo_legal_en_passant() and not b.has_legal_en_passant()
    p=chess.Board(BY_ID['promotion']['steps'][0]['fen'])
    assert {m.promotion for m in p.legal_moves if m.from_square==chess.A7}=={chess.QUEEN,chess.ROOK,chess.BISHOP,chess.KNIGHT}

def test_complete_all_restore_account_separation_no_credit(foundation):
    c,server=foundation
    original=server.get_state('INTRO-QA');original['active_game']={'untouched':True};original['assessment_v8_history']=[{'id':'old'}];original['v9_course']={'saved':'keep'};original['learner_start']={'choice':'rules','revision':1,'rules_step':0};server.save_state('INTRO-QA',original)
    before=copy.deepcopy(dict(server.get_state('INTRO-QA')))
    s=c.get('/api/foundations').json()
    for course in COURSES:
        s=send(c,s,'start',course['id'])
        for i,step in enumerate(course['steps']):
            if step['kind']=='judge':s=send(c,s,'answer',course['id'],step['answer'])
            else:
                for move in step['line'][::2]:s=send(c,s,'move',course['id'],move)
            assert s['active']['solved']
            if i+1<len(course['steps']):s=send(c,s,'next',course['id'])
        assert next(x for x in s['courses'] if x['id']==course['id'])['done']
    assert s['completed']==10 and s['recommended'] is None
    restored=TestClient(c.app,headers=dict(c.headers)).get('/api/foundations').json()
    assert s.pop('interaction')=='step_complete'
    assert restored==s
    after=dict(server.get_state('INTRO-QA'));after.pop(KEY);assert after==before
    s=send(c,s,'review','rook-bishop');s=send(c,s,'move','rook-bishop','a1a4')
    assert s['completed']==10 and s['courses'][0]['completed']==3
    other=TestClient(c.app);t=other.post('/api/register',json={'code':'BASIC-OTHER','pin':'local-tutorial-42'}).json()['token'];other.headers['Authorization']='Bearer '+t
    assert other.get('/api/foundations').json()['completed']==0
    assert other.get('/api/foundations').json()['active'] is None
    assert TestClient(c.app).get('/api/foundations').status_code==401
    entry=c.post('/api/journey/start',json={'mode':'entry'})
    assert entry.status_code==200,entry.text
    assert entry.json()['version']=='journey-entry-v1'

def test_wrong_illegal_stale_duplicate_and_switch_resume(foundation):
    c,server=foundation;s=c.get('/api/foundations').json();s=send(c,s,'start','rook-bishop')
    wrong=send(c,s,'move','rook-bishop','a1b2');assert '방향' in wrong['active']['feedback'];assert wrong['active']['fen']==s['active']['fen'] and not wrong['active']['solved']
    legal=send(c,wrong,'move','rook-bishop','a1a3');assert '합법적인 수' in legal['active']['feedback']
    done=send(c,legal,'move','rook-bishop','a1a4')
    stale=c.post('/api/foundations/action',json={'revision':legal['revision'],'course_id':'rook-bishop','action':'move','value':'a1a4'})
    assert stale.status_code==409
    duplicate=c.post('/api/foundations/action',json={'revision':done['revision'],'course_id':'rook-bishop','action':'move','value':'a1a4'})
    assert duplicate.status_code==409
    nexts=send(c,done,'next','rook-bishop');switched=send(c,nexts,'start','promotion');resumed=send(c,switched,'start','rook-bishop')
    assert resumed['active']==nexts['active']
    raw=copy.deepcopy(dict(server.get_state('INTRO-QA')));c.get('/api/foundations');assert dict(server.get_state('INTRO-QA'))==raw

def test_simultaneous_moves_have_one_completion(foundation):
    c,server=foundation;s=send(c,c.get('/api/foundations').json(),'start','rook-bishop')
    body={'revision':s['revision'],'course_id':'rook-bishop','action':'move','value':'a1a4'}
    def request(_):return TestClient(c.app,headers=dict(c.headers)).post('/api/foundations/action',json=body).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:statuses=list(pool.map(request,range(2)))
    assert sorted(statuses)==[200,409]
    assert c.get('/api/foundations').json()['courses'][0]['completed']==1
