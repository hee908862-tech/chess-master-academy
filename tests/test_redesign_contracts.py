import copy
import chess
from fastapi.testclient import TestClient
from test_runtime_isolation import runtime
from test_learning import setup
from test_journey import attach, post, act, saved
import guest_access


def test_guest_all_services_restore_and_non_destructive_link(runtime):
    server,(a,b)=runtime
    guest_access.LIMITER.rows.clear()
    anonymous=TestClient(server.app)
    start=anonymous.post('/api/guest/start');assert start.status_code==200,start.text
    credential=start.json()['token'];code=start.json()['code']
    anonymous.headers['Authorization']='Bearer '+credential
    for endpoint in ['/api/me','/api/foundations','/api/journey','/api/learning/dashboard','/api/repertoire','/api/education']:
        response=anonymous.get(endpoint);assert response.status_code==200,(endpoint,response.text)
    course=anonymous.get('/api/foundations').json()
    r=anonymous.post('/api/foundations/action',json={'action':'start','course_id':'en-passant','revision':course['revision'],'step':0})
    assert r.status_code==200,r.text
    before=copy.deepcopy(server.get_state('RUNTIME-A'))
    guest_before=copy.deepcopy(server.get_state(code))
    for _ in range(2):
        linked=a.post('/api/guest/link',json={'guest_token':credential});assert linked.status_code==200,linked.text
    assert len(a.get('/api/guest/links').json()['items'])==1
    assert b.post('/api/guest/link',json={'guest_token':credential}).status_code==409
    assert b.post('/api/guest/resume',json={'id':code}).status_code==404
    resumed=a.post('/api/guest/resume',json={'id':code});assert resumed.status_code==200
    other=TestClient(server.app,headers={'Authorization':'Bearer '+resumed.json()['token']})
    assert other.get('/api/foundations').json()['active']==r.json()['active']
    assert server.get_state('RUNTIME-A')==before
    assert server.get_state(code)==guest_before
    game=anonymous.post('/api/game/new',json={'color':'white'})
    assert game.status_code==200,game.text
    assert other.get('/api/game').json()['active'] is True


def test_guest_rate_limit_is_separate_from_grading():
    limiter=guest_access.Limiter()
    limiter.take('a',1,60)
    import pytest
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as e:limiter.take('a',1,60)
    assert e.value.status_code==429
    limiter.take('b',1,60)


def test_scope_blueprints_and_full_scoped_report_without_total(setup):
    c,ns,old,path=attach(setup)
    blueprint=c.get('/api/journey/blueprint').json()
    assert [r['questions'] for r in blueprint['levels']]==[24,8,4]
    s=post(c,'start',{'mode':'domain','competency':'mate'})
    assert s['total']==8
    rows=saved(path)['active']['items']
    assert {i['competency'] for i in rows}=={'mate'}
    assert [sum(i['band']==band for i in rows) for band in [[600,1200],[1200,1800]]]==[4,4]
    while s['phase']!='complete':
        row=saved(path)['active']['items'][s['index']]
        for u in row['line'][::2]:
            s=act(c,s,'move',u)
            if s['phase']=='feedback':break
        s=act(c,s,'next')
    r=s['report']
    assert r['diagnostic_scope']=={'level':'domain','competency':'mate','topic':None}
    assert 'internal_skill' not in r
    assert next(a for a in r['areas'] if a['id']=='mate')['performance']['score']==3000
    assert next(a for a in r['areas'] if a['id']=='capture')['performance']['score'] is None
    assert r['snapshot']['diagnostic_scope']==r['diagnostic_scope']


def test_subskill_exact_tag_and_reject_unsupported_scope(setup):
    c,_,_,path=attach(setup)
    assert c.post('/api/journey/start',json={'mode':'subskill','competency':'strategy','topic':'anything'}).status_code==409
    assert c.post('/api/journey/start',json={'mode':'subskill','competency':'mate','topic':'fork'}).status_code==422
    s=post(c,'start',{'mode':'subskill','competency':'mate','topic':'mateIn1'})
    assert s['total']==4
    assert all('mateIn1' in r['tags'] for r in saved(path)['active']['items'])
    assert c.post('/api/journey/start',json={'mode':'domain','competency':'mate'}).status_code==409


def test_mate_precedence_and_hypothetical_king_attacks(runtime):
    server,_=runtime
    board=chess.Board('6k1/3P1pp1/p6p/8/1p6/1P1Q3P/P5PK/2qq4 w - - 0 1')
    for promotion in ['q','r']:
        b=board.copy();b.push_uci('d7d8'+promotion)
        result=server.serialize_board(b)
        assert result['checkmate'] and result['check'] and not result['stalemate']
        assert result['mate_explanation']['available']
        assert result['mate_explanation']['legal_replies']==0
