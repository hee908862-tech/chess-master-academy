"""Persisted new-version points with isolated synthetic SQLite, no operating accounts."""
import copy
import json
import sqlite3
from datetime import datetime,timedelta,timezone
import pytest
import journey_server as journey
from test_learning import setup
from test_journey import attach,post,saved,act
from solving_score import VERSION

FEN='7k/8/5K2/8/6Q1/8/8/8 w - - 0 1'


def seed(client,path,clock,partial=False,legacy=False):
    s=post(client,'start',{'mode':'targeted','competency':'mate'})
    state=saved(path);active=state['active']
    line=['g4g3','h8h7','g3g7'] if partial else ['g4g7']
    row={**active['items'][0],'id':'isolated-score-item','puzzle_id':'isolated-score-puzzle','fen':FEN,'line':line,
         'position_keys':[], 'rating':1200,'competency':'mate','tags':['mateIn2' if partial else 'mateIn1'],
         'prior':'g3g4','independent':True,'app_new':True,'helped':False,'first_attempt':True,'shown_at':clock[0].isoformat()}
    active.update(items=[row],index=0,total=1,fen=FEN,offset=0,correct=0,submitted=[],played=[],reply='g3g4')
    if legacy:active.pop('solving_score_version',None)
    # Preserve an original historical report sentinel, never reinterpret it.
    state['results']=[{'id':'legacy-result','version':'legacy','items':[],'score':3000}]
    with sqlite3.connect(path) as db:db.execute('UPDATE journey_progress SET state=? WHERE code=?',(json.dumps(state),'A'));db.commit()
    return client.get('/api/journey').json()['active']


def event(seq,ms,**extra):
    return {'version':'solving-time-v1','stream_id':'isolatedstream','seq':seq,'active_ms':ms,
            'prepared':True,'interrupted':False,'limited':False,**extra}


def submit(c,s,payload,move='g4g7',action='move'):
    return post(c,'action',{'session_id':s['session_id'],'revision':s['revision'],'action':action,'move':move,'solving_time':payload})


@pytest.mark.parametrize('case,seconds,expected',[
    ('fast',10,3000),('slow',90,2850),('wrong',10,1),('partial',10,713),
    ('unknown',10,None),('interrupted',10,2850),('missing',10,None),('underreported',100,None)])
def test_actual_saved_score_changes_with_time_and_reloads(case,seconds,expected,setup,monkeypatch):
    clock=[datetime(2026,1,1,tzinfo=timezone.utc)];monkeypatch.setattr(journey,'now',lambda:clock[0])
    c,ns,old,path=attach(setup);old.clear();before=copy.deepcopy(old)
    s=seed(c,path,clock,partial=case=='partial')
    body={'session_id':s['session_id'],'revision':s['revision'],'item_id':s['question']['id']}
    first=post(c,'prepare',body);assert post(c,'prepare',body)==first
    early=c.post('/api/journey/action',json={'session_id':s['session_id'],'revision':0,'action':'move','move':'g4g7','solving_time':event(1,10)})
    assert early.status_code==409 and saved(path)['active']['items'][0].get('submitted') is None
    clock[0]+=timedelta(seconds=3+seconds)
    if case=='unknown':monkeypatch.setattr(journey,'prove_mate_alternative',lambda *a: {'status':'unknown','reason':'mate_proof_budget'});monkeypatch.setattr(journey,'verify_loss',lambda *a:None)
    payload=None if case=='missing' else event(1,1 if case=='underreported' else seconds*1000,interrupted=case=='interrupted')
    s=submit(c,s,payload,move='g4g3' if case in ('wrong','unknown','partial') else 'g4g7')
    if case=='partial':
        assert s['phase']=='question';clock[0]+=timedelta(seconds=10)
        s=submit(c,s,event(2,20000),action='skip',move=None)
    assert s['phase']=='feedback'
    item_value=s['feedback']['solving_score'];assert item_value['final_score']==expected,item_value
    frozen=s['feedback']['solving_time'];clock[0]+=timedelta(seconds=900)
    assert c.get('/api/journey').json()['active']['feedback']['solving_time']==frozen
    s=act(c,s,'next');assert s['phase']=='complete'
    result=s['report'];assert result['solving_score']['final_score']==expected,result['solving_score']
    assert result['solving_score']['version']==VERSION
    again=c.get('/api/journey').json()['latest'];assert again['solving_score']==result['solving_score']
    stored=saved(path);assert stored['results'][0]=={'id':'legacy-result','version':'legacy','items':[],'score':3000}
    assert old==before
    if case in ('fast','slow'):assert item_value['base_points']==2850 and item_value['time_adjustment']==expected-2850
    if case=='unknown':assert item_value['A'] is None


def test_legacy_active_keeps_original_timing_and_no_new_score(setup,monkeypatch):
    clock=[datetime(2026,1,1,tzinfo=timezone.utc)];monkeypatch.setattr(journey,'now',lambda:clock[0])
    c,_,_,path=attach(setup);s=seed(c,path,clock,legacy=True)
    assert c.post('/api/journey/prepare',json={'session_id':s['session_id'],'revision':0,'item_id':s['question']['id']}).status_code==409
    clock[0]+=timedelta(seconds=5)
    s=post(c,'action',{'session_id':s['session_id'],'revision':s['revision'],'action':'move','move':'g4g7','thinking_time':{'version':'thinking-time-v1','stream_id':'legacyclock','seq':1,'active_ms':5000}})
    assert 'solving_score' not in s['feedback']
    assert saved(path)['active']['items'][0]['thinking_time']['active_ms']==5000
    s=act(c,s,'next');assert 'solving_score' not in s['report']


def test_owned_prepare_and_revision_do_not_reset(setup,monkeypatch):
    clock=[datetime(2026,1,1,tzinfo=timezone.utc)];monkeypatch.setattr(journey,'now',lambda:clock[0])
    c,_,_,path=attach(setup);s=seed(c,path,clock)
    body={'session_id':s['session_id'],'revision':0,'item_id':s['question']['id']}
    assert c.post('/api/journey/prepare',json=body,headers={'Authorization':'B'}).status_code==409
    first=post(c,'prepare',body);clock[0]+=timedelta(seconds=50)
    assert post(c,'prepare',body)==first
    assert c.post('/api/journey/prepare',json={**body,'revision':1}).status_code==409


def test_engine_wait_is_not_scored_and_fixed_denominator_is_saved(setup,monkeypatch):
    clock=[datetime(2026,1,1,tzinfo=timezone.utc)];monkeypatch.setattr(journey,'now',lambda:clock[0])
    c,_,old,path=attach(setup);old.clear();s=seed(c,path,clock)
    post(c,'prepare',{'session_id':s['session_id'],'revision':0,'item_id':s['question']['id']})
    clock[0]+=timedelta(seconds=13)
    def proof(*args):
        clock[0]+=timedelta(seconds=27)
        return {'status':'unknown','reason':'mate_proof_budget'}
    monkeypatch.setattr(journey,'prove_mate_alternative',proof)
    monkeypatch.setattr(journey,'verify_loss',lambda *a:None)
    s=submit(c,s,event(1,10000),move='g4g3')
    assert s['feedback']['solving_time']['active_ms']==10000
    assert s['feedback']['solving_score']['final_score'] is None
    s=act(c,s,'next')
    assert s['report']['solving_score']['item_count']==1
    comparison=s['report']['solving_score']['comparison']
    assert comparison['target_policy_version']=='authored-target-v1'
    assert comparison['answer_policy']=='goal-alternatives-v1' and len(comparison['question_set_sha256'])==64
    assert c.get('/api/journey').json()['latest']['solving_score']==s['report']['solving_score']


def test_new_initial_freeze_stores_new_score_and_old_baseline_is_untouched():
    from initial_profile import freeze
    from solving_score import item_score
    from test_initial_profile import report,real_rows
    rows=real_rows()
    for row in rows:
        row.update(independent=True,app_new=True,helped=False,first_attempt=True,
                   solving_time={'version':'solving-time-v1','status':'interrupted','active_ms':1000,'flags':['interrupted']})
        row['solving_score']=item_score(row)
    r=report(rows);r['solving_score_version']=VERSION
    state={'results':[r],'active':None,'initial_profile':{'version':'initial-profile-v1','corpus':r['corpus_sha256'],'solving_score_version':VERSION}}
    freeze(state,'2026-01-01T00:00:00+00:00')
    before=copy.deepcopy(state)
    assert 'solving_score' in state['initial_profile']['baseline']
    assert state['initial_profile']['baseline']['solving_score']['assigned_count']==48
    freeze(state,'later');assert state==before
    legacy={'results':[r],'active':None,'initial_profile':{'corpus':r['corpus_sha256']}}
    freeze(legacy,'old')
    assert 'solving_score' not in legacy['initial_profile']['baseline']


@pytest.mark.parametrize('second,expected',[('wrong',1501),('unknown',None)])
def test_saved_same_denominator_includes_failed_and_unresolved_items(second,expected,setup,monkeypatch):
    clock=[datetime(2026,1,1,tzinfo=timezone.utc)];monkeypatch.setattr(journey,'now',lambda:clock[0])
    c,_,old,path=attach(setup);old.clear();s=seed(c,path,clock)
    state=saved(path);row=copy.deepcopy(state['active']['items'][0])
    row.update(id='second-item',puzzle_id='second-puzzle',fen='7k/5K2/8/8/6Q1/8/8/8 w - - 0 1')
    state['active']['items'].append(row);state['active']['total']=2
    with sqlite3.connect(path) as db:db.execute('UPDATE journey_progress SET state=? WHERE code=?',(json.dumps(state),'A'));db.commit()
    s=c.get('/api/journey').json()['active']
    for index in range(2):
        post(c,'prepare',{'session_id':s['session_id'],'revision':s['revision'],'item_id':s['question']['id']})
        clock[0]+=timedelta(seconds=13)
        if index and second=='unknown':
            monkeypatch.setattr(journey,'prove_mate_alternative',lambda *a:{'status':'unknown','reason':'mate_proof_budget'})
            monkeypatch.setattr(journey,'verify_loss',lambda *a:None)
        s=submit(c,s,event(1,10000),move='g4g7' if index==0 else 'g4g3')
        assert s['phase']=='feedback'
        s=act(c,s,'next')
    result=s['report']['solving_score'];assert result['final_score']==expected,result
    assert result['item_count']==result['assigned_count']==2
    if second=='wrong':assert result['A']==result['B']==.5
    assert c.get('/api/journey').json()['latest']['solving_score']==result
