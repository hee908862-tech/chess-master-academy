import copy
import json
import sqlite3
import chess
import learning_server
from diagnostic_blueprint import training_recommendations
from test_learning import setup, action


def report(rows):
    return {'id':'scoped-test','version':'diagnostic-blueprint-v1','diagnostic_scope':{'level':'domain','competency':'calculation'},'items':[
        {'id':str(n),'competency':'calculation','tags':['fork'],'outcome':outcome,**extra}
        for n,(outcome,extra) in enumerate(rows)]}


def test_late_error_not_first_two_and_multiple_weaknesses():
    r=report([('completed',{}),('completed',{}),('verified_error',{}),('partial_execution',{'correct_plies':1,'tags':['pin']})])
    tasks=training_recommendations(r)['tasks']
    assert [t['item_id'] for t in tasks]==['2','3']
    assert all(t['intent']=='weakness' and t['reason'] for t in tasks)
    r['items'][2]['competency']='mate'
    assert [t['item_id'] for t in training_recommendations(r)['tasks']]==['3']


def test_success_uncertainty_help_and_insufficient_observation():
    r=report([('completed',{}),('completed',{})])
    assert training_recommendations(r)['tasks'][0]['intent']=='maintenance'
    for status in ['unverified_alternative','not_answered','equivalent_alternative']:
        r=report([(status,{'helped':True}),(status,{})])
        assert training_recommendations(r)['tasks']==[]
        assert training_recommendations(r)['needs_more']
    assert not training_recommendations(report([('completed',{})]))['tasks']
    r=report([('completed',{}),('completed',{'helped':True})])
    assert training_recommendations(r)['tasks'][0]['item_id']=='1'
    r['diagnostic_scope']['topic']='pin'
    assert training_recommendations(r)['tasks']==[]


def prepared(setup):
    client,ns,_,path=setup
    puzzle=next(p for p in learning_server.LIB.values() if 'mateIn1' in p['themes'])
    board=chess.Board(puzzle['fen']);board.push_uci(puzzle['moves'][0])
    r={'id':'scoped','version':'diagnostic-blueprint-v1','diagnostic_scope':{'level':'subskill','competency':'mate','topic':'mateIn1'},
       'items':[{'id':'late','competency':'mate','tags':['mateIn1'],'outcome':'verified_non_mate','fen':board.fen(),'line':puzzle['moves'][1:],'puzzle_id':puzzle['id']}]}
    ns['journey_report']=lambda *_:copy.deepcopy(r)
    return client,path,{'report_id':'scoped','item_id':'late'}


def test_exact_skill_new_candidate_and_duplicate_completion(setup):
    c,path,body=prepared(setup)
    response=c.post('/api/learning/scoped/start',json=body)
    assert response.status_code==200,response.text
    state=response.json()
    assert state['selection']['overlap']==['mateIn1']
    assert c.post('/api/learning/scoped/start',json=body).json()['session_id']==state['session_id']
    with sqlite3.connect(path) as db:
        stored=json.loads(db.execute("SELECT state FROM learning_progress WHERE code='A'").fetchone()[0])
    card=stored['cards'][state['card_id']]
    first=next(v for v in stored['cards'].values() if v.get('diagnosis'))
    assert card['puzzle_id']!=first['puzzle_id']
    for move in card['line'][::2]:
        previous=copy.deepcopy(state)
        state=action(c,state,'move',move)
        if state['done']:break
    assert state['done']
    duplicate=c.post('/api/learning/action',json={'session_id':previous['session_id'],'revision':previous['revision'],'action':'move','move':move})
    assert duplicate.status_code==409
    assert c.post('/api/learning/scoped/start',json=body).json()['done']
    with sqlite3.connect(path) as db:
        final=json.loads(db.execute("SELECT state FROM learning_progress WHERE code='A'").fetchone()[0])
    assert len(final['attempts'])==1 and len(final['scoped_completed'])==1
    assert not final.get('cycles')


def test_missing_candidate_no_unrelated_substitution(setup,monkeypatch):
    c,_,body=prepared(setup)
    monkeypatch.setattr(learning_server,'LIB',{})
    response=c.post('/api/learning/scoped/start',json=body)
    assert response.status_code==409
    assert c.get('/api/learning/dashboard').json()['active'] is None
