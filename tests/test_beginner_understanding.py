"""Isolated SQLite/API, legal move coverage and legacy progress preservation."""
import copy
from concurrent.futures import ThreadPoolExecutor
import chess
from fastapi.testclient import TestClient
from test_foundations import foundation, send
from test_onboarding import api
from foundation_content import COURSES
from beginner_content import INTRO, INTRO_ID, OVERLAYS, validate_intro, lesson_teaching
from foundation_server import KEY


def initial(c):
    return send(c,c.get('/api/foundations').json(),'start',INTRO_ID)


def solve(c,s):
    t=s['active'];step=INTRO['steps'][t['step']]
    if t['kind']=='identify':return send(c,s,'identify',INTRO_ID,'a1')
    if t['kind']=='demo':return send(c,s,'observe',INTRO_ID)
    return send(c,s,'move',INTRO_ID,{'guided':'a1a4','independent':'a1c1','transfer':'d4f4'}[t['phase']])


def test_content_and_all_legacy_exercises_have_visible_prerequisites():
    validate_intro()
    assert len(COURSES)==10 and sum(len(c['steps']) for c in COURSES)==26
    for course in COURSES:
        assert len(OVERLAYS[course['id']])==len(course['steps'])
        for t in OVERLAYS[course['id']]:assert all(t.get(k) for k in ('name','symbol','rule','prior','action'))


def test_new_first_flow_observed_is_not_independent_and_get_is_read_only(foundation):
    c,server=foundation
    before=copy.deepcopy(dict(server.get_state('INTRO-QA')))
    d=c.get('/api/foundations').json();assert d['recommended']==INTRO_ID and not d['introduction']['started']
    assert dict(server.get_state('INTRO-QA'))==before
    s=initial(c)
    for index in range(6):
        assert s['active']['step_id']==INTRO['steps'][index]['id']
        s=solve(c,s)
        assert s['active']['solved']
        if index<5:s=send(c,s,'next',INTRO_ID)
    assert s['completed']==0 and s['total']==10
    assert s['introduction']['done'] and s['recommended']=='rook-bishop'
    assert [x['result'] for x in s['introduction']['checks']]==['recognised','observed','observed','guided','first_unaided','first_unaided']
    assert c.get('/api/foundations').json()['active']==s['active']
    after=dict(server.get_state('INTRO-QA'));after.pop(KEY);assert after==before


def test_every_legal_rook_alternative_is_accepted_and_reconstructs_board(foundation):
    c,server=foundation
    for index in (4,5):
        step=INTRO['steps'][index];board=chess.Board(step['fen'])
        for move in list(board.legal_moves):
            if move.from_square!=chess.parse_square(step['source']):continue
            state=server.get_state('INTRO-QA');state[KEY]={'revision':0,'active':INTRO_ID,'courses':{INTRO_ID:{'index':index,'ply':0,'completed_steps':[]}}};server.save_state('INTRO-QA',state)
            s=c.get('/api/foundations').json()
            assert not s['active']['visual']['arrows']
            s=send(c,s,'move',INTRO_ID,move.uci());expected=board.copy();expected.push(move)
            assert s['active']['solved'] and s['active']['fen']==expected.fen()
            assert c.get('/api/foundations').json()['active']['fen']==expected.fen()
            assert s['active']['visual']['played_moves']==[move.uci()]


def test_error_feedback_is_not_first_unaided_and_wrong_piece_not_accepted(foundation):
    c,server=foundation
    state=server.get_state('INTRO-QA');state[KEY]={'revision':0,'active':INTRO_ID,'courses':{INTRO_ID:{'index':5,'ply':0,'completed_steps':[]}}};server.save_state('INTRO-QA',state)
    s=c.get('/api/foundations').json();fen=s['active']['fen']
    for move in ('d4d7','d4e5','g1f1'):
        s=send(c,s,'move',INTRO_ID,move);assert not s['active']['solved'] and s['active']['fen']==fen
    s=send(c,s,'move',INTRO_ID,'d4d5');assert s['active']['check_result']=='retry_with_feedback'
    assert s['introduction']['checks'][0]['attempts']==4


def test_old_active_and_completed_remain_separate_from_optional_new_checks(foundation):
    c,server=foundation
    state=server.get_state('INTRO-QA')
    courses={x['id']:{'index':len(x['steps'])-1,'ply':len(x['steps'][-1].get('line',[])),'completed_steps':list(range(len(x['steps']))),'done':True,'solved':True} for x in COURSES}
    state[KEY]={'revision':9,'active':'rook-bishop','courses':courses}
    state['active_game']={'sentinel':'keep'};state['journey_sentinel']={'score':3000,'active':'keep'}
    server.save_state('INTRO-QA',state);before=copy.deepcopy(dict(server.get_state('INTRO-QA')))
    old=c.get('/api/foundations').json();assert old['completed']==10 and old['recommended'] is None
    assert not old['introduction']['started'] and old['introduction']['checks']==[]
    s=send(c,old,'start',INTRO_ID);s=solve(c,s);s=send(c,s,'start','rook-bishop')
    assert s['active']==old['active'] and s['completed']==10
    raw=dict(server.get_state('INTRO-QA'))
    assert {k:v for k,v in raw[KEY]['courses'].items() if k!=INTRO_ID}==before[KEY]['courses']
    assert {k:v for k,v in raw.items() if k!=KEY}=={k:v for k,v in before.items() if k!=KEY}
    # Preserve an actually unfinished multi-ply legacy lesson, too.
    state=server.get_state('INTRO-QA');state[KEY]['courses']['opening-turns']={'index':0,'ply':2,'completed_steps':[]};state[KEY]['active']='opening-turns';server.save_state('INTRO-QA',state)
    old=c.get('/api/foundations').json();s=send(c,old,'start',INTRO_ID);s=send(c,s,'start','opening-turns');assert s['active']==old['active']


def test_intro_revision_duplicates_auth_and_review_history(foundation):
    c,server=foundation;s=initial(c)
    body={'revision':s['revision'],'course_id':INTRO_ID,'step':0,'action':'identify','value':'a1'}
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes=list(pool.map(lambda _:TestClient(c.app,headers=dict(c.headers)).post('/api/foundations/action',json=body).status_code,range(2)))
    assert sorted(codes)==[200,409]
    s=c.get('/api/foundations').json();assert len(s['introduction']['checks'])==1
    assert TestClient(c.app).post('/api/foundations/action',json=body).status_code==401
    s=send(c,s,'review',INTRO_ID);s=solve(c,s)
    assert len(s['introduction']['checks'])==2 and s['introduction']['checks'][0]['run']==0 and s['introduction']['checks'][1]['run']==1
    client=TestClient(c.app);token=client.post('/api/register',json={'code':'INTRO-ISOLATED','pin':'isolated-test-only'}).json()['token'];client.headers['Authorization']='Bearer '+token
    assert client.get('/api/foundations').json()['introduction']['checks']==[]
    assert client.post('/api/foundations/action',json=body).status_code==409


def test_teaching_picture_keeps_learner_color_before_and_after_move():
    from foundation_content import BY_ID
    step=BY_ID['mate-stalemate']['steps'][1]
    assert lesson_teaching('mate-stalemate',1,step,chess.Board(step['fen']))['symbol']=='k'
    step=BY_ID['rook-bishop']['steps'][0];board=chess.Board(step['fen']);board.push_uci('a1a4')
    assert lesson_teaching('rook-bishop',0,step,board)['symbol']=='R'
