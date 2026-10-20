"""Explicit opt-in integration checks against disposable, loopback PostgreSQL only.
Run: CMA_TEST_PG_URL=postgresql://...@127.0.0.1:55432/cma_predeploy python -m pytest -q scripts/predeploy_postgres.py
Never consumes DATABASE_URL from the invoking environment.
"""
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
url=os.environ.get('CMA_TEST_PG_URL','')
target=urlparse(url)
if target.hostname not in ('127.0.0.1','localhost') or target.path!='/cma_predeploy':
    raise RuntimeError('Requires explicit loopback disposable cma_predeploy database')
os.environ['DATABASE_URL']=url
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json
import secrets
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import psycopg
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
import server
import journey_server as journey
from journey_evidence import CUED,UNCUED,JOURNEY_VERSION,additional_plan
from competencies import VERSION


def account():
    code=('PG-'+secrets.token_hex(5)).upper()
    c=TestClient(server.app,raise_server_exceptions=False)
    r=c.post('/api/register',json={'code':code,'pin':'temporary-local-pin'})
    assert r.status_code==200,r.text
    c.headers['Authorization']='Bearer '+r.json()['token']
    return c,code


def state(table,code):
    with server.db() as db:
        row=server.execute(db,f'SELECT state FROM {table} WHERE code=?',(code,)).fetchone()
        return json.loads(row['state']) if row else None


def post(c,path,body):
    r=c.post('/api/'+path,json=body);assert r.status_code==200,r.text
    return r.json()


def test_real_pg_settings_and_two_account_concurrency():
    with server.db() as db:
        assert db.info.host=='127.0.0.1'
        assert db.info.get_parameters()['connect_timeout']=='5'
        assert db.execute('SHOW lock_timeout').fetchone()['lock_timeout']=='2s'
        assert db.execute('SHOW statement_timeout').fetchone()['statement_timeout']=='8s'
    a,ac=account();b,bc=account()
    journey.inventory()
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs=[pool.submit(a.post,'/api/journey/start',json={}),pool.submit(b.post,'/api/journey/start',json={}),
              pool.submit(b.post,'/api/login',json={'code':bc,'pin':'temporary-local-pin'}),
              pool.submit(a.post,'/api/game/new',json={'color':'white'})]
        responses=[job.result(timeout=15) for job in jobs]
    assert responses[2].status_code==responses[3].status_code==200
    for c,r in zip((a,b),responses[:2]):
        assert r.status_code in (200,409),r.text
        if not c.get('/api/journey').json()['active']:post(c,'journey/start',{})
    assert a.get('/api/journey').json()['active']['session_id']!=b.get('/api/journey').json()['active']['session_id']
    assert a.get('/api/me').status_code==b.get('/api/onboarding').status_code==200


def test_same_account_two_tabs_start_and_save_are_atomic():
    c,code=account()
    with ThreadPoolExecutor(max_workers=2) as pool:
        rs=list(pool.map(lambda _:c.post('/api/journey/start',json={}),range(2)))
    assert sorted(r.status_code for r in rs)==[200,409]
    s=c.get('/api/journey').json()['active']
    body={'session_id':s['session_id'],'revision':s['revision'],'action':'skip'}
    with ThreadPoolExecutor(max_workers=2) as pool:
        rs=list(pool.map(lambda _:c.post('/api/journey/action',json=body),range(2)))
    assert sorted(r.status_code for r in rs)==[200,409]
    saved=state('journey_progress',code)
    assert saved['active']['revision']==1 and len(saved['active']['items'])==s['total']
    snapshots=[server.get_state(code) for _ in range(3)]
    def save(i):
        snapshots[i]['completed_lessons']=[str(i)]
        try:server.save_state(code,snapshots[i]);return 200
        except HTTPException as e:return e.status_code
    with ThreadPoolExecutor(max_workers=3) as pool:assert sorted(pool.map(save,range(3)))==[200,409,409]


def test_advisory_lock_timeout_503_and_safe_retry():
    c,code=account()
    with psycopg.connect(url) as lock:
        lock.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',('chess-evidence:'+code,))
        start=time.monotonic();r=c.post('/api/journey/start',json={});elapsed=time.monotonic()-start
        assert r.status_code==503 and r.headers['retry-after']=='2',r.text
        assert 1.8<=elapsed<5,elapsed
        print('observed_lock_timeout_seconds',round(elapsed,3))
        assert c.get('/api/journey').json()['active'] is None
    s=post(c,'journey/start',{})
    assert c.get('/api/journey').json()['active']['session_id']==s['session_id']
    assert c.post('/api/journey/start',json={}).status_code==409


def test_statement_timeout_rolls_back_all_writes():
    c,code=account();before=server.get_state(code)
    start=time.monotonic()
    with pytest.raises(HTTPException) as error:
        with server.db() as db:
            server.execute(db,'UPDATE progress SET state=? WHERE code=?',('{}',code))
            server.execute(db,'SELECT pg_sleep(10)')
    assert error.value.status_code==503
    elapsed=time.monotonic()-start
    assert 7.8<=elapsed<11
    print('observed_statement_timeout_seconds',round(elapsed,3))
    assert server.get_state(code)==before and c.get('/api/me').status_code==200


def test_connection_timeout_is_503_and_then_recovers(monkeypatch):
    c,_=account();stop=threading.Event()
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen()
    def stalled_handshake():
        conn,_=listener.accept()
        with conn:stop.wait(10)
    worker=threading.Thread(target=stalled_handshake,daemon=True);worker.start()
    try:
        with monkeypatch.context() as patch:
            patch.setattr(server,'DATABASE_URL',f'postgresql://local:local@127.0.0.1:{listener.getsockname()[1]}/cma_predeploy')
            start=time.monotonic();r=c.get('/api/me');elapsed=time.monotonic()-start
            assert r.status_code==503 and 4.5<=elapsed<8,(r.text,elapsed)
            print('observed_connect_timeout_seconds',round(elapsed,3))
    finally:stop.set();listener.close();worker.join(2)
    assert c.get('/api/me').status_code==200


def test_legacy_session_records_and_training_survive_reinitialization():
    c,code=account()
    legacy=server.get_state(code);legacy['completed_lessons']=['legacy-lesson'];legacy['assessment_history']=[{'version':'v1','score':42}]
    server.save_state(code,legacy)
    old_attempt={'card_id':'legacy-card','position':'legacy-position','at':'2020-01-01T00:00:00+00:00',
        'category':'mate','success':True,'independent_kind':'novel','mode':'verify','fresh':True,
        'status':'unaided_first_success','helped':False,'competency_version':'competency-v1','assessment_scope':'first_move'}
    old_learning={'schema':1,'cards':{},'attempts':[old_attempt],'seen':[],'intervals':[1,3,7],'active':None}
    with server.db() as db:server.execute(db,'INSERT INTO learning_progress(code,state) VALUES(?,?)',(code,json.dumps(old_learning)))
    s=post(c,'journey/start',{'mode':'targeted','competency':'mate'})
    original=state('journey_progress',code)
    old_report={'id':'legacy-result','version':'journey-v2','areas':[],'items':[]}
    original['results'].append(old_report)
    original['active']['version']='journey-v2'
    original['active'].pop('measurement_scope',None)
    original['active'].pop('competency_version',None)
    with server.db() as db:server.execute(db,'UPDATE journey_progress SET state=? WHERE code=?',(json.dumps(original),code))
    server.initdb() # Additive initialization must not rewrite saved JSON.
    assert state('journey_progress',code)==original
    s=c.get('/api/journey').json()['active'];assert s['measurement_scope']=='legacy_cued_execution'
    while s['phase']!='complete':
        if s['phase']=='question':s=post(c,'journey/action',{'session_id':s['session_id'],'revision':s['revision'],'action':'skip'})
        s=post(c,'journey/action',{'session_id':s['session_id'],'revision':s['revision'],'action':'next'})
    assert state('journey_progress',code)['results'][0]==old_report
    report=s['report'];item=report['items'][0]
    linked=post(c,'learning/from-diagnosis',{'report_id':report['id'],'item_id':item['id']})
    training=post(c,'learning/action',{'session_id':linked['active']['session_id'],'revision':linked['active']['revision'],'action':'hint'})
    before=state('learning_progress',code);server.initdb()
    assert state('learning_progress',code)==before
    assert before['attempts']==[old_attempt]
    skill=next(s for s in c.get('/api/learning/dashboard').json()['skills'] if s['id']=='mate')
    assert skill['distinct']==0 and skill['groups'][0]['reference_only']
    assert c.get('/api/learning/dashboard').json()['active']==training
    again=post(c,'learning/from-diagnosis',{'report_id':report['id'],'item_id':item['id']})
    assert again['active']==training and again['path']['id']==linked['path']['id']
    assert server.get_state(code)['completed_lessons']==['legacy-lesson']
    assert server.get_state(code)['assessment_history']==[{'version':'v1','score':42}]


def test_pg_restored_evidence_scopes_remain_separate():
    c,code=account()
    def result(scope,n):return {'id':scope,'version':JOURNEY_VERSION,'competency_version':VERSION,
        'measurement_scope':scope,'areas':[{'id':'mate','count':3,'full_success':n}],'items':[]}
    reports=[result(CUED,2),result(UNCUED,1),{**result(CUED,0),'version':'journey-v2'}]
    with server.db() as db:server.execute(db,'INSERT INTO journey_progress(code,state) VALUES(?,?)',
        (code,json.dumps({'active':None,'results':reports,'reserved':[]})))
    assert c.get('/api/journey').json()['additional']['mate']['band']==[1200,1800]
    restored=state('journey_progress',code)['results']
    assert additional_plan(restored,'mate',UNCUED)['band']==[900,1500]
    assert restored==reports


def test_cross_module_reservations_share_pg_account_lock(monkeypatch):
    import learning_server as learning
    c,code=account()
    row=next(p for p in journey.inventory()['calculation'] if 600<=p['rating']<1200)
    monkeypatch.setattr(journey,'inventory',lambda:{'calculation':[row]})
    monkeypatch.setattr(learning,'LIB',{row['puzzle_id']:journey.LIB[row['puzzle_id']]})
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(c.post,'/api/journey/start',json={}),pool.submit(c.post,'/api/learning/start',json={'fresh':True})]
        responses=[j.result(timeout=10) for j in jobs]
    assert sorted(r.status_code for r in responses)==[200,409],[r.text for r in responses]


def test_reset_atomic_duplicate_and_inflight_generation(monkeypatch):
    a,code=account();b,other=account()
    state_a=server.blank_state();state_a['completed_lessons']=['preserve-until-reset'];server.save_state(code,state_a)
    with server.db() as conn:
        for table in ('journey_progress','learning_progress'):
            server.execute(conn,f'INSERT INTO {table}(code,state) VALUES(?,?)',(code,json.dumps({'sentinel':'old'})))
    body={'pin':'temporary-local-pin','confirmation':'초기화','revision':0}
    execute=server.execute
    def fail(conn,query,args=()):
        if query.startswith('DELETE FROM learning_progress'):raise RuntimeError('controlled rollback')
        return execute(conn,query,args)
    monkeypatch.setattr(server,'execute',fail)
    assert a.post('/api/profile/reset',json=body).status_code==500
    assert state('progress',code)['completed_lessons']==['preserve-until-reset']
    assert state('journey_progress',code)=={'sentinel':'old'}
    monkeypatch.setattr(server,'execute',execute)
    entered=threading.Event();release=threading.Event();save=server.save_state
    def delayed(c,s):
        if c==code and s.get('active_game'):entered.set();assert release.wait(8)
        return save(c,s)
    monkeypatch.setattr(server,'save_state',delayed)
    with ThreadPoolExecutor(3) as pool:
        pending=pool.submit(a.post,'/api/game/new',json={'color':'white'})
        assert entered.wait(4)
        try:
            resets=[pool.submit(a.post,'/api/profile/reset',json=body) for _ in range(2)]
            assert sorted(r.result().status_code for r in resets)==[200,409]
        finally:release.set()
        assert pending.result().status_code==409
    assert state('progress',code)==server.blank_state()
    assert state('journey_progress',code) is None and state('learning_progress',code) is None
    assert b.get('/api/me').json()['reset_revision']==0
    assert a.get('/api/me').json()['reset_revision']==1


def test_growth_balanced_cycle_unlock_and_preserved_snapshots():
    c,code=account()
    s=post(c,'journey/start',{'mode':'balanced'})
    assert s['total']==24 and 'competency' not in s['question']
    while s['phase']!='complete':
        s=post(c,'journey/action',{'session_id':s['session_id'],'revision':s['revision'],'action':'skip'})
        s=post(c,'journey/action',{'session_id':s['session_id'],'revision':s['revision'],'action':'next'})
    report=s['report'];assert report['snapshot']['version']=='growth-v1'
    before=state('journey_progress',code)
    observed=c.get('/api/journey').json()
    assert len(observed['learning_evidence'][report['id']])==24
    assert all(row['label']=='미응답 · 수행 미관찰' for row in observed['learning_evidence'][report['id']].values())
    assert state('journey_progress',code)==before and observed['latest']==report
    assert c.post('/api/journey/start',json={'mode':'balanced'}).status_code==409
    for task in report['training_plan']:
        body={'report_id':report['id'],'item_id':task['id']}
        t=post(c,'learning/cycle/start',body)
        card=state('learning_progress',code)['cards'][t['card_id']]
        for move in card['line'][::2]:
            t=post(c,'learning/action',{'session_id':t['session_id'],'revision':t['revision'],'action':'move','move':move})
            if t['done']:break
        assert t['done']
        assert c.post('/api/learning/cycle/start',json=body).status_code==409
    status=c.get('/api/journey').json();assert status['cycle']['unlocked'] and status['cycle']['completed']==5
    post(c,'journey/start',{'mode':'balanced'})
    assert c.get('/api/journey').json()['latest']==report


def test_real_image_engine_analysis_persists_without_rating():
    import game_analysis
    c,code=account();legacy=server.get_state(code)
    game={'moves':['e2e4','e7e5','g1f3','b8c6'],'color':'black','ended':'2026-10-20T12:00:00+00:00','assistance':{'version':1,'complete':True,'events':[]}}
    legacy['games']=[game];server.save_state(code,legacy);key=game_analysis.game_key(game)
    post(c,'games/analysis/'+key,{})
    for _ in range(400):
        result=c.get('/api/games/analysis').json()['games'][0]
        if result['status'] not in ('queued','running'):break
        time.sleep(.05)
    assert result['status'] in ('complete','partial'),result
    assert result['user_moves']==2 and result['rating'] is None and result['engine'].startswith('Stockfish')
    assert c.get('/api/games/analysis').json()['average'] is None
    assert server.get_state(code)['games']==[game]


def test_internal_rating_real_engine_persists_and_legacy_is_not_rewritten():
    c,code=account();legacy=server.get_state(code)
    legacy['games']=[{'moves':['e2e4','e7e5'],'color':'white','result':'draw','ended':'2020-01-01'}]
    server.save_state(code,legacy);before=server.get_state(code)['games'][0]
    first=c.get('/api/games/analysis').json();assert first['app_rating']['series']=={}
    assert first['games'][0]['app_rating']['eligible'] is False
    assert server.get_state(code)['games'][0]==before
    g=post(c,'game/new',{'color':'black','difficulty':5,'time_mode':'bullet'})
    move=g['board']['legal'][0]
    post(c,'game/move',{'from_sq':move['from'],'to_sq':move['to'],'session_id':g['session_id']})
    post(c,'game/resign',{})
    saved=server.get_state(code);rated=saved['games'][-1]['app_rating']
    assert rated['eligible'] and rated['after']<rated['before'] and rated['time_mode']=='bullet'
    assert saved['app_ratings']['bullet']['games']==1
    assert c.post('/api/game/resign').status_code==400
    server.initdb()
    assert server.get_state(code)==saved
    assert c.get('/api/games/analysis').json()['app_rating']['series']['bullet']['games']==1


def test_opening_bookmark_and_readonly_branch_pg():
    c,code=account();before=server.get_state(code)
    response=post(c,'study/position',{'moves':['e2e4','c7c5'],'engine':True})
    assert response['reply'] and server.get_state(code)==before
    data={'course_id':'sicilian-najdorf','moves':['e2e4','c7c5'],'mode':'recall','orientation':'black','revision':0}
    saved=post(c,'study/openings/save',data)
    assert saved['revision']==1
    assert c.post('/api/study/openings/save',json={**data,'moves':[]}).status_code==409
    server.initdb()
    assert c.get('/api/study/openings').json()['saved']==saved
    after=server.get_state(code);after.pop('opening_study');assert after==before


def test_starting_choice_cas_and_learning_switch_preserve_pg_records():
    c,code=account()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda choice:c.post('/api/starting-level',json={'choice':choice,'revision':0}),['beginner','experienced']))
    assert sorted(r.status_code for r in results)==[200,409]
    assert c.get('/api/starting-level').json()['revision']==1
    a=post(c,'learning/start',{'fresh':True})
    a=post(c,'learning/action',{'session_id':a['session_id'],'revision':a['revision'],'action':'hint'})
    body={'fresh':True,'pause_session_id':a['session_id'],'pause_revision':a['revision']}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:c.post('/api/learning/start',json=body),range(2)))
    assert sorted(r.status_code for r in results)==[200,409]
    b=c.get('/api/learning/dashboard').json()['active']
    restored=post(c,'learning/resume',{'session_id':a['session_id'],'active_id':b['session_id'],'active_revision':b['revision']})
    assert restored['fen']==a['fen'] and restored['hint_level']==a['hint_level']
    assert restored['revision']>a['revision']
    assert c.post('/api/learning/action',json={'session_id':a['session_id'],'revision':a['revision'],'action':'hint'}).status_code==409
    assert len(state('learning_progress',code)['paused'])==1
    before=state('learning_progress',code)
    c.get('/api/learning/dashboard')
    assert state('learning_progress',code)==before
    post(c,'learning/exposure',{'session_id':restored['session_id'],'active_revision':restored['revision']})
    after=state('learning_progress',code)
    assert after['active']==before['active']
    assert after['cards'][restored['card_id']]['exposure']!=before['cards'][restored['card_id']]['exposure']
    assert c.get('/api/starting-level').json()['revision']==1


def test_foundations_pg_cas_restore_and_record_isolation():
    c,code=account()
    stored=server.get_state(code);stored['v9_course']={'existing':'preserve'};server.save_state(code,stored)
    before=state('progress',code)
    s=c.get('/api/foundations').json()
    s=post(c,'foundations/action',{'action':'start','course_id':'rook-bishop','revision':s['revision']})
    move={'action':'move','course_id':'rook-bishop','revision':s['revision'],'value':'a1a4'}
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses=list(pool.map(lambda _:c.post('/api/foundations/action',json=move).status_code,range(2)))
    assert sorted(statuses)==[200,409]
    s=c.get('/api/foundations').json();assert s['courses'][0]['completed']==1
    server.initdb()
    assert c.get('/api/foundations').json()==s
    after=state('progress',code);after.pop('foundation_v1');assert after==before
    other,_=account();assert other.get('/api/foundations').json()['completed']==0


def test_challenge_pg_atomic_score_isolation_restore():
    c,code=account();before=state('progress',code)
    s=c.get('/api/challenge').json()
    s=post(c,'challenge/action',{'action':'start','revision':s['revision']})
    body={'action':'next','revision':s['revision'],'session_id':s['active']['id']}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:c.post('/api/challenge/action',json=body).status_code,range(2)))
    assert sorted(results)==[200,409]
    s=c.get('/api/challenge').json();assert s['active']['lives']==2 and s['active']['score']==0
    server.initdb();assert c.get('/api/challenge').json()==s
    after=state('progress',code);after.pop('puzzle_challenge_v1');assert after==before
    other,_=account();assert other.get('/api/challenge').json()['active'] is None


def test_repertoire_pg_cas_and_unrelated_records_preserved():
    from repertoire_server import KEY
    client,code=account();other,other_code=account()
    baseline=server.get_state(code);baseline['opening_study']={'revision':9,'course_id':'sicilian-alapin','moves':['e2e4'],'mode':'recall','orientation':'black'};server.save_state(code,baseline)
    before=dict(server.get_state(code))
    data=client.get('/api/repertoire').json()
    data=post(client,'repertoire/action',{'action':'select','revision':data['revision'],'selected':['london-core']})
    data=post(client,'repertoire/action',{'action':'start','revision':data['revision'],'lesson_id':'london-core','mode':'recall'})
    body={'action':'hint','revision':data['revision'],'attempt_id':data['active']['id']}
    with ThreadPoolExecutor(2) as executor:results=list(executor.map(lambda _:client.post('/api/repertoire/action',json=body),range(2)))
    assert sorted(r.status_code for r in results)==[200,409]
    data=client.get('/api/repertoire').json();assert data['active']['hints']==1
    restored=dict(server.get_state(code));restored.pop(KEY);assert restored==before
    assert other.get('/api/repertoire').json()['active'] is None
    data=post(client,'repertoire/action',{'action':'retry','revision':data['revision'],'attempt_id':data['active']['id']})
    assert data['active']['hints']==1 and not data['metrics']['london-core']['first_recall']['clean']
