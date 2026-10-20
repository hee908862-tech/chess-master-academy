"""Fake accounts only: reset transaction, generation barrier, reads and preservation."""
import json
import threading
from concurrent.futures import ThreadPoolExecutor
import pytest
from test_runtime_isolation import runtime

PIN='local-runtime-9384'

def seed(server):
    for code in ('RUNTIME-A','RUNTIME-B'):
        state=server.blank_state();state['completed_lessons']=['keep'];state['onboarding_v1']={'status':'completed'}
        server.save_state(code,state)
        with server.db() as c:
            for table in ('journey_progress','learning_progress'):
                server.execute(c,f'INSERT INTO {table}(code,state) VALUES(?,?)',(code,json.dumps({'sentinel':code})))

def snapshot(server,code):
    with server.db() as c:
        return [tuple(r) for table in ('progress','journey_progress','learning_progress') for r in server.execute(c,f'SELECT state FROM {table} WHERE code=?',(code,)).fetchall()]

def reset(client,revision=0):
    return client.post('/api/profile/reset',json={'pin':PIN,'confirmation':'초기화','revision':revision})

def test_reset_all_domains_isolated_and_duplicate_safe(runtime):
    server,(a,b)=runtime;seed(server);other=snapshot(server,'RUNTIME-B')
    assert a.get('/api/me').json()['reset_revision']==0
    assert reset(a).status_code==200
    assert snapshot(server,'RUNTIME-A')==[(json.dumps(server.blank_state(),ensure_ascii=False),)]
    assert snapshot(server,'RUNTIME-B')==other
    assert a.get('/api/onboarding').json()['status']=='not_started'
    assert a.get('/api/journey').json()['active'] is None
    assert a.get('/api/learning/dashboard').json()['cards']==[]
    state=server.get_state('RUNTIME-A');state['completed_lessons']=['new'];server.save_state('RUNTIME-A',state)
    assert reset(a).status_code==409
    assert server.get_state('RUNTIME-A')['completed_lessons']==['new']
    assert a.get('/api/me').json()['reset_revision']==1
    assert a.post('/api/login',json={'code':'RUNTIME-A','pin':PIN}).status_code==200

@pytest.mark.parametrize('change,status',[({'pin':'incorrect'},403),({'confirmation':'삭제'},400),({'revision':9},409)])
def test_reset_rejection_preserves_everything(runtime,change,status):
    server,(a,b)=runtime;seed(server);before=snapshot(server,'RUNTIME-A')
    data={'pin':PIN,'confirmation':'초기화','revision':0};data.update(change)
    assert a.post('/api/profile/reset',json=data).status_code==status
    assert snapshot(server,'RUNTIME-A')==before

def test_reset_rolls_back_all_domains(runtime,monkeypatch):
    server,(a,b)=runtime;seed(server);before=snapshot(server,'RUNTIME-A');execute=server.execute
    def broken(conn,query,args=()):
        if query.startswith('DELETE FROM learning_progress'):raise RuntimeError('injected reset failure')
        return execute(conn,query,args)
    monkeypatch.setattr(server,'execute',broken)
    assert reset(a).status_code==500
    assert snapshot(server,'RUNTIME-A')==before
    assert a.get('/api/me').json()['reset_revision']==0

def test_reset_blocks_pre_reset_inflight_write(runtime,monkeypatch):
    server,(a,b)=runtime;entered=threading.Event();release=threading.Event();save=server.save_state
    def delayed(code,state):
        if state.get('active_game'):
            entered.set();assert release.wait(5)
        return save(code,state)
    monkeypatch.setattr(server,'save_state',delayed)
    with ThreadPoolExecutor(2) as pool:
        pending=pool.submit(a.post,'/api/game/new',json={'color':'white'})
        assert entered.wait(3)
        try:assert reset(a).status_code==200
        finally:release.set()
        assert pending.result().status_code==409
    assert server.get_state('RUNTIME-A')['active_game'] is None

def test_concurrent_reset_once(runtime):
    server,(a,b)=runtime;seed(server)
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:reset(a).status_code,range(2)))
    assert sorted(results)==[200,409]
    assert a.get('/api/me').json()['reset_revision']==1

def test_dashboard_read_does_not_write_or_wait_on_sqlite_writer(runtime):
    import sqlite3
    server,(a,b)=runtime
    lock=sqlite3.connect(server.SQLITE_FILE);lock.execute('BEGIN IMMEDIATE')
    try:assert a.get('/api/learning/dashboard').status_code==200
    finally:lock.rollback();lock.close()
    with server.db() as c:assert server.execute(c,'SELECT * FROM learning_progress').fetchall()==[]
