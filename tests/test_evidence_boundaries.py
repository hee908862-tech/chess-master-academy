"""Bidirectional line overlap and version/scope-separated evidence regressions."""
import json
import sqlite3
import chess
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
import journey_server as journey
import learning_server as learning
from competencies import line_positions, position_key, VERSION
from test_learning import setup


def synthetic(pid, first, moves):
    b=chess.Board(); b.push_uci(first)
    return {'id':pid,'fen':b.fen(),'moves':moves,'themes':['quietMove'],'rating':900}


def snapshot(p):
    b=chess.Board(p['fen']);b.push_uci(p['moves'][0])
    return {'puzzle_id':p['id'],'fen':b.fen(),'line':p['moves'][1:],
            'tags':p['themes'],'rating':900,'prior':p['moves'][0],'version':VERSION}


def pair(kind):
    if kind=='suffix': return learning.LIB['VEfqe'],learning.LIB['d4kK3']
    return (synthetic('trans-A','g1f3',['g8f6','g2g3','g7g6','f1g2']),
            synthetic('trans-B','g2g3',['g7g6','g1f3','g8f6','f1g2']))


def save_learning(path,state):
    with sqlite3.connect(path) as db:
        db.execute('INSERT OR REPLACE INTO learning_progress(code,state) VALUES(?,?)',('A',json.dumps(state)))


def learning_state(cards=None,attempts=None):
    return {'schema':1,'cards':cards or {},'attempts':attempts or [],'seen':[],
            'intervals':[1,3,7],'active':None}


@pytest.mark.parametrize('selector',['journey','learning'])
@pytest.mark.parametrize('kind',['suffix','convergence'])
@pytest.mark.parametrize('reverse',[False,True])
def test_full_line_overlap_both_orders_preserves_nonoverlapping_similar_problem(setup,monkeypatch,selector,kind,reverse):
    c,ns,legacy,path=setup;legacy.clear()
    source,candidate=pair(kind)
    if reverse: source,candidate=candidate,source
    old,new=snapshot(source),snapshot(candidate)
    old_positions=line_positions(old['fen'],old['line'])
    assert old_positions & line_positions(new['fen'],new['line'])
    if kind=='convergence':
        assert position_key(old['fen']) not in line_positions(new['fen'],new['line'])
        assert position_key(new['fen']) not in old_positions
    control=synthetic('similar-new','h2h3',['a7a6','a2a3','h7h6','a1a2'])
    fresh=snapshot(control)
    assert not old_positions.intersection(line_positions(fresh['fen'],fresh['line']))
    card={'id':'old-card','fen':old['fen'],'line':old['line'],'tags':old['tags'],
          'category':'calculation','due':'2020-01-01','title':'old','source':'fixture','successes':0}
    save_learning(path,learning_state({'old-card':card}))
    if selector=='learning':
        monkeypatch.setattr(learning,'LIB',{candidate['id']:candidate,control['id']:control})
        response=c.post('/api/learning/start',json={'fresh':True,'mode':'verify'})
        assert response.status_code==200,response.text
        assert response.json()['card_id']=='puzzle-similar-new'
    else:
        monkeypatch.setattr(journey,'inventory',lambda:{'calculation':[new,fresh]})
        app=FastAPI();journey.attach_journey(app,ns)
        client=TestClient(app,headers={'Authorization':'A'})
        response=client.post('/api/journey/start',json={'mode':'targeted','competency':'calculation'})
        assert response.status_code==200,response.text
        with sqlite3.connect(path) as db:
            state=json.loads(db.execute('SELECT state FROM journey_progress').fetchone()[0])
        assert [i['puzzle_id'] for i in state['active']['items']]==['similar-new']


def test_position_identity_ignores_clocks_but_preserves_chess_rights():
    b=chess.Board();original=b.fen()
    changed=original.rsplit(' ',2)[0]+' 99 87'
    assert line_positions(original,[])==line_positions(changed,[])
    assert line_positions(original,[])!=line_positions(original.replace(' w ',' b '),[])
    assert line_positions(original,[])!=line_positions(original.replace(' KQkq ',' - '),[])
    ep='4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1'
    assert line_positions(ep,[])!=line_positions(ep.replace(' d6 ',' - '),[])
    # An unusable EP marker conveys no legal right and normalizes to '-'.
    no_ep='4k3/8/8/3p4/8/8/8/4K3 w - d6 0 1'
    assert line_positions(no_ep,[])==line_positions(no_ep.replace(' d6 ',' - '),[])


def attempt(i,success,version=VERSION,scope='full_line',category='calculation'):
    result={'card_id':f'card-{i}','position':f'position-{i}','at':f'2026-10-{i+1:02d}T00:00:00+00:00',
            'category':category,'success':success,'independent_kind':'novel','mode':'verify',
            'fresh':True,'status':'unaided_first_success' if success else 'not_yet','helped':False}
    if version is not None:result['competency_version']=version
    if scope is not None:result['assessment_scope']=scope
    return result


def test_old_first_move_success_does_not_inflate_full_line_or_fake_decline(setup):
    c,ns,legacy,path=setup
    rows=[attempt(i,True,version=None,scope=None) for i in range(5)]
    rows += [attempt(i+5,True,version='competency-v1',scope='first_move') for i in range(5)]
    rows += [attempt(i+10,True,scope='first_move') for i in range(5)]
    rows += [attempt(15,True),attempt(16,False)]
    state=learning_state(attempts=rows);save_learning(path,state)
    dashboard=c.get('/api/learning/dashboard').json()
    skill=next(s for s in dashboard['skills'] if s['id']=='calculation')
    assert skill['count']==17 and skill['distinct']==2
    assert skill['recent'] is None and skill['previous'] is None and not skill['trend_available']
    assert dashboard['recommended'] is None
    groups={(g['version'],g['assessment_scope']):g for g in skill['groups']}
    assert groups[(VERSION,'first_move')]['recent']==100
    assert groups[('competency-v1','first_move')]['recent']==100
    assert groups[('unrecorded','unrecorded')]['recent'] is None
    with sqlite3.connect(path) as db:
        assert json.loads(db.execute('SELECT state FROM learning_progress').fetchone()[0])['attempts']==rows
    # Five current full-line positions now support one rate, never a cross-scope trend.
    rows += [attempt(17,False),attempt(18,False),attempt(19,False)]
    save_learning(path,learning_state(attempts=rows))
    dashboard=c.get('/api/learning/dashboard').json();skill=next(s for s in dashboard['skills'] if s['id']=='calculation')
    assert skill['recent']==20 and skill['recent_n']==5
    assert skill['previous'] is None and not skill['trend_available']
    assert dashboard['recommended']=='calculation'


def test_only_matching_scope_version_windows_support_trend_and_priority(setup):
    c,ns,legacy,path=setup
    rows=[attempt(i,i>=5) for i in range(10)]
    rows += [attempt(i+10,False,scope='first_move',category='mate') for i in range(10)]
    save_learning(path,learning_state(attempts=rows))
    d=c.get('/api/learning/dashboard').json();skill=next(s for s in d['skills'] if s['id']=='calculation')
    assert skill['previous']==0 and skill['recent']==100 and skill['trend_available']
    assert skill['previous_n']==skill['recent_n']==5
    assert d['recommended'] is None # First-move failures cannot rank full-line competencies.
    # Repeated positions do not supply another denominator, nor may engine play join it.
    repeated=[{**attempt(i,True),'position':'same'} for i in range(10)]
    engine=[{**attempt(i+10,False),'mode':'situation_verify'} for i in range(5)]
    save_learning(path,learning_state(attempts=repeated+engine))
    d=c.get('/api/learning/dashboard').json();skill=next(s for s in d['skills'] if s['id']=='calculation')
    assert skill['distinct']==1 and skill['recent'] is None and not skill['trend_available']
    assert d['recommended'] is None


@pytest.mark.parametrize('version,scope',[(None,None),('competency-v1','full_line'),(VERSION,'first_move')])
def test_incomparable_failure_does_not_override_due_order(setup,version,scope):
    from test_learning import post
    c,ns,legacy,path=setup
    first=post(c,'start',{'fresh':True});second=post(c,'start',{'fresh':True})
    with sqlite3.connect(path) as db:
        state=json.loads(db.execute('SELECT state FROM learning_progress').fetchone()[0])
        row=attempt(0,False,version,scope);row['card_id']=second['card_id']
        state['attempts'].append(row)
        db.execute('UPDATE learning_progress SET state=?',(json.dumps(state),))
    route=post(c,'path',{})
    assert route['path']['source_card']==first['card_id']
