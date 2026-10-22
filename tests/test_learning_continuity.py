"""Saved progress, explicit switching, stale writes and independently scoped entry paths."""
import copy
import json
import sqlite3
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_learning import setup, post, action, solution
from test_journey import attach, saved, act
from test_onboarding import api
from onboarding_server import RULES


def test_saved_switch_resume_keeps_help_and_rejects_late_moves(setup):
    c, ns, legacy, path = setup
    a = post(c, 'start', {'fresh': True})
    a = action(c, a, 'hint')
    before = copy.deepcopy(c.get('/api/learning/dashboard').json())
    assert c.post('/api/learning/start', json={'fresh': True}).status_code == 409
    assert c.get('/api/learning/dashboard').json()['active'] == before['active']
    b = post(c, 'start', {'fresh': True, 'pause_session_id': a['session_id'], 'pause_revision': a['revision']})
    assert a['card_id'] != b['card_id']
    stale = {'session_id': a['session_id'], 'revision': a['revision'], 'action': 'move', 'move': solution(a)}
    assert c.post('/api/learning/action', json=stale).status_code == 409
    # A new client represents reload; both states are persisted, not just in JS.
    reloaded = TestClient(c.app, headers={'Authorization': 'A'})
    assert reloaded.get('/api/learning/dashboard').json()['active']['session_id'] == b['session_id']
    resumed = post(reloaded, 'resume', {'session_id': a['session_id'], 'active_id': b['session_id'], 'active_revision': b['revision']})
    assert resumed['fen'] == a['fen'] and resumed['session_id'] == a['session_id']
    assert resumed['revision'] > a['revision']
    assert c.post('/api/learning/action', json=stale).status_code == 409
    done = action(c, resumed, 'move', solution(resumed))
    assert done['outcome']['status'] == 'hinted_success'
    other = TestClient(c.app, headers={'Authorization': 'B'})
    assert other.post('/api/learning/resume', json={'session_id': b['session_id']}).status_code == 404
    assert len(reloaded.get('/api/learning/dashboard').json()['paused']) == 1


def test_same_card_start_is_resume_without_exposure_or_help_reset(setup):
    c, _, _, path = setup
    a = action(c, post(c, 'start', {'fresh': True}), 'hint')
    def raw():
        with sqlite3.connect(path) as db:
            return json.loads(db.execute("SELECT state FROM learning_progress WHERE code='A'").fetchone()[0])
    before = raw()
    assert post(c, 'start', {'card_id': a['card_id']}) == a
    after=raw()
    exposure=after['cards'][a['card_id']]['exposure']
    prior=before['cards'][a['card_id']]['exposure']
    for day in exposure:exposure[day]['last_at']=prior[day]['last_at']
    assert after == before


def test_starting_level_persists_rules_retries_and_preserves_history(api):
    c, server = api
    state = server.get_state('INTRO-QA'); state['games'] = [{'sentinel': True}]
    server.save_state('INTRO-QA', state)
    s = c.post('/api/starting-level', json={'choice': 'rules', 'revision': 0}).json()
    assert s['defer_auto'] is False
    assert c.post('/api/starting-level', json={'choice': 'experienced', 'revision': 0}).status_code == 409
    # Retry is not a diagnosis/attempt and does not increment the lesson step.
    s = c.post('/api/starting-level/move', json={'revision': s['revision'], 'step': 0, 'move': 'a1a2'}).json()
    assert not s['correct'] and s['rules_step'] == 0
    for i, exercise in enumerate(RULES):
        s = c.post('/api/starting-level/move', json={'revision': s['revision'], 'step': i, 'move': exercise[3]}).json()
        assert s['correct'] and s['rules_step'] == i + 1
    assert c.get('/api/starting-level').json()['rules_step'] == 4
    assert server.get_state('INTRO-QA')['games'] == [{'sentinel': True}]
    assert not server.get_state('INTRO-QA').get('puzzle_results')


def test_entry_selection_and_reports_cannot_mix_with_balanced_growth(setup):
    c, ns, legacy, path = attach(setup)
    legacy['learner_start'] = {'choice': 'rules', 'rules_step': 0}
    assert c.post('/api/journey/start', json={'mode': 'entry'}).status_code == 409
    legacy['learner_start'] = {'choice': 'beginner'}
    s = c.post('/api/journey/start', json={'mode': 'entry'}).json()
    assert 1 <= s['total'] <= 6 and s['version'] == 'journey-entry-v1'
    rows = saved(path)['active']['items']
    assert all(600 <= x['rating'] < 1000 and len(x['line']) <= 5 for x in rows)
    assert s['starting_conditions']['self_choice'] == 'beginner'
    legacy['learner_start'] = {'choice': 'experienced'}
    # Choice changes don't alter an in-flight assessment.
    assert c.get('/api/journey').json()['active'] == s
    while s['phase'] != 'complete':
        s = act(c, s, 'skip') if s['phase'] == 'question' else act(c, s, 'next')
    assert 'snapshot' not in s['report']
    assert s['report']['starting_conditions']['self_choice'] == 'beginner'
    s = c.post('/api/journey/start', json={'mode': 'entry'}).json()
    assert s['total'] == 24 and s['version'] == 'journey-v5'
    assert s['starting_conditions']['self_choice'] == 'experienced'
    assert {tuple(x['band']) for x in saved(path)['active']['items']} == {(600,1200),(1200,1800)}


def test_application_easier_same_slot_and_retention_preparation(setup, monkeypatch):
    import learning_server as learning
    from test_growth_cycle import finish_diagnosis
    from test_journey import post as journey_post
    c, ns, legacy, path = attach(setup)
    report = finish_diagnosis(c, journey_post(c, 'start', {'mode': 'balanced'}), path)
    task = next(t for t in report['training_plan'] if t['kind'] == 'application')
    learner = setup[0]
    def raw():
        with sqlite3.connect(path) as db:
            return json.loads(db.execute("SELECT state FROM learning_progress WHERE code='A'").fetchone()[0])
    # Highest available candidate makes a strictly easier real candidate available.
    monkeypatch.setattr(learning.secrets, 'choice', lambda rows:max(rows,key=lambda row:row[0]['rating']))
    body={'report_id':report['id'],'item_id':task['id']}
    r=learner.post('/api/learning/cycle/start',json=body);assert r.status_code==200,r.text
    a=r.json();assert 600<=a['rating']<=1200
    request={**body,'session_id':a['session_id'],'revision':a['revision'],'card_id':a['card_id']}
    b=learner.post('/api/learning/cycle/easier',json=request)
    assert b.status_code==200,b.text
    b=b.json();assert b['rating']<a['rating'] and b['card_id']!=a['card_id']
    state=raw();cycle=state['cycles'][report['id']]
    assert not cycle['completed'] and cycle['cards'][task['id']]==b['card_id']
    assert cycle['replacements'][0]['session']['id']==a['session_id']
    assert learner.post('/api/learning/cycle/easier',json=request).status_code==409
    assert learner.post('/api/learning/action',json={'session_id':a['session_id'],'revision':a['revision'],'action':'hint'}).status_code==409
    for move in state['cards'][b['card_id']]['line'][::2]:
        b=action(learner,b,'move',move)
        if b['done']:break
    assert len(raw()['cycles'][report['id']]['completed'])==1
    # Recommended practice doesn't satisfy the separate unaided retention gate.
    gate=c.get('/api/journey').json()['rechecks'][task['competency']]
    assert not gate['eligible'] and gate['ready_at'] is None
    item=next(i for i in report['items'] if i['id']==task['item_id'])
    r=learner.post('/api/learning/retention/start',json={'report_id':report['id'],'item_id':item['id']})
    assert r.status_code==200,r.text
    s=r.json();assert s['mode']=='verify' and s['assessment_scope']=='full_line'
    state=raw()
    for move in state['cards'][s['card_id']]['line'][::2]:
        s=action(learner,s,'move',move)
        if s['done']:break
    gate=c.get('/api/journey').json()['rechecks'][task['competency']]
    assert not gate['eligible'] and gate['ready_at'] is not None
    assert len(raw()['cycles'][report['id']]['completed'])==1


def test_no_lower_candidate_preserves_everything(setup, monkeypatch):
    import learning_server as learning
    from test_growth_cycle import finish_diagnosis
    from test_journey import post as journey_post
    c, ns, legacy, path = attach(setup)
    report=finish_diagnosis(c,journey_post(c,'start',{'mode':'balanced'}),path)
    task=next(t for t in report['training_plan'] if t['kind']=='application')
    learner=setup[0];body={'report_id':report['id'],'item_id':task['id']}
    s=learner.post('/api/learning/cycle/start',json=body).json()
    before=learner.get('/api/learning/dashboard').json()
    monkeypatch.setattr(learning,'LIB',{})
    r=learner.post('/api/learning/cycle/easier',json={**body,'session_id':s['session_id'],'revision':s['revision'],'card_id':s['card_id']})
    assert r.status_code==409 and '교체하지 않았습니다' in r.json()['detail']
    assert learner.get('/api/learning/dashboard').json()==before


import pytest
@pytest.mark.parametrize('choice',[None,'unsure','later'])
def test_unknown_or_skipped_level_never_defaults_to_medium(setup,choice):
    c,ns,legacy,path=attach(setup)
    if choice:legacy['learner_start']={'choice':choice}
    response=c.post('/api/journey/start',json={'mode':'entry'})
    assert response.status_code==200,response.text
    assert response.json()['version']=='journey-entry-v1'
    assert all(600<=i['rating']<1000 for i in saved(path)['active']['items'])


def test_latest_gentle_is_separate_from_prior_standard_cycle(setup):
    from test_growth_cycle import finish_diagnosis
    from test_journey import post as jp
    c,ns,legacy,path=attach(setup)
    standard=finish_diagnosis(c,jp(c,'start',{'mode':'balanced'}),path)
    # Existing earned completion ledger, scoped to this isolated test DB.
    with sqlite3.connect(path) as db:
        state=json.loads(db.execute('SELECT state FROM learning_progress').fetchone()[0]) if db.execute('SELECT count(*) FROM learning_progress').fetchone()[0] else {'cards':{},'attempts':[],'seen':[],'intervals':[1,3,7],'active':None}
        state['cycles']={standard['id']:{'cards':{},'completed':{t['id']:{'position':t['id']} for t in standard['training_plan']}}}
        db.execute('INSERT OR REPLACE INTO learning_progress(code,state) VALUES(?,?)',('A',json.dumps(state)))
    latest=finish_diagnosis(c,jp(c,'start',{'mode':'gentle'}),path)
    status=c.get('/api/journey').json()
    assert status['latest']==latest and status['cycle_report']==standard
    assert status['cycle']['report_id']==standard['id'] and status['cycle']['completed']==5
    assert 'snapshot' not in latest
