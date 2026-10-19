"""Production db/auth path: controlled cold work, contention, retries and CAS."""
import copy
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import chess
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
import journey_server as journey
import learning_server as learning


@pytest.fixture
def runtime(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_URL','');monkeypatch.setenv('SQLITE_FILE',str(tmp_path/'initial.sqlite'))
    import server
    monkeypatch.setattr(server,'DATABASE_URL','')
    monkeypatch.setattr(server,'SQLITE_FILE',str(tmp_path/'runtime.sqlite'))
    monkeypatch.setattr(server,'STOCKFISH_PATH','')
    server.initdb()
    with server.db() as conn:
        for table in ['learning_progress','journey_progress']:
            server.execute(conn,f'CREATE TABLE IF NOT EXISTS {table} (code TEXT PRIMARY KEY,state TEXT NOT NULL)')
    clients=[]
    for account in ['RUNTIME-A','RUNTIME-B']:
        c=TestClient(server.app,raise_server_exceptions=False)
        r=c.post('/api/register',json={'code':account,'pin':'local-runtime-9384'})
        assert r.status_code==200,r.text
        c.headers['Authorization']='Bearer '+r.json()['token'];clients.append(c)
    server.DB_TIMINGS.clear()
    return server,clients


def small_pool():
    p=next(p for p in journey.LIB.values() if 600<=p['rating']<1200 and len(p['moves'])>=4)
    b=chess.Board(p['fen']);b.push_uci(p['moves'][0])
    return {'calculation':[{'puzzle_id':p['id'],'fen':b.fen(),'line':p['moves'][1:],
        'tags':p['themes'],'rating':p['rating'],'prior':p['moves'][0],'version':journey.VERSION}]}


def test_cold_work_does_not_hold_production_db_or_block_other_account(runtime,monkeypatch,tmp_path):
    server,(a,b)=runtime;entered=threading.Event();release=threading.Event();pool=small_pool()
    monkeypatch.setattr(journey,'_prepared',None);monkeypatch.setattr(journey,'INDEX_PATH',tmp_path/'missing.gz')
    def build():
        entered.set();assert release.wait(5);return pool
    monkeypatch.setattr(journey,'build_inventory',build)
    with ThreadPoolExecutor(max_workers=4) as executor:
        cold=executor.submit(a.post,'/api/journey/start',json={})
        assert entered.wait(2)
        try:
            assert executor.submit(b.get,'/api/me').result(timeout=1).status_code==200
            assert executor.submit(b.get,'/api/onboarding').result(timeout=1).status_code==200
            assert executor.submit(b.post,'/api/game/new',json={'color':'white'}).result(timeout=1).status_code==200
            again=executor.submit(a.post,'/api/journey/start',json={}).result(timeout=1)
            assert again.status_code==503 and again.headers['retry-after']=='2'
            assert executor.submit(a.get,'/api/journey').result(timeout=1).json()['active'] is None
        finally:release.set()
        result=cold.result(timeout=3);assert result.status_code==200,result.text
    restored=a.get('/api/journey').json()['active']
    assert restored['session_id']==result.json()['session_id']
    assert a.post('/api/journey/start',json={}).status_code==409
    assert any(t['kind']=='write_gate' for t in server.DB_TIMINGS)


def test_database_busy_is_bounded_and_read_retry_preserves_state(runtime,monkeypatch):
    server,(a,b)=runtime;monkeypatch.setattr(server,'DB_LOCK_TIMEOUT',.05)
    state=server.get_state('RUNTIME-A');state['completed_lessons']=['preserved'];server.save_state('RUNTIME-A',state)
    lock=sqlite3.connect(server.SQLITE_FILE);lock.execute('BEGIN IMMEDIATE')
    try:
        result=a.post('/api/game/new',json={'color':'white'})
        assert result.status_code==503,result.text
        assert result.headers['retry-after']=='2'
        assert b.get('/api/me').status_code==200
        assert server.get_state('RUNTIME-A')['active_game'] is None
    finally:lock.rollback();lock.close()
    assert a.post('/api/game/new',json={'color':'white'}).status_code==200
    assert server.get_state('RUNTIME-A')['completed_lessons']==['preserved']
    assert any(t.get('wait_ms',0)>=40 for t in server.DB_TIMINGS)


def test_preparation_failure_has_no_reservation_and_can_retry(runtime,monkeypatch,tmp_path):
    server,(a,b)=runtime;pool=small_pool();calls=[]
    monkeypatch.setattr(journey,'_prepared',None);monkeypatch.setattr(journey,'INDEX_PATH',tmp_path/'missing.gz')
    def build():
        calls.append(1)
        if len(calls)==1:raise OSError('controlled unavailable corpus')
        return pool
    monkeypatch.setattr(journey,'build_inventory',build)
    assert a.post('/api/journey/start',json={}).status_code==503
    assert a.get('/api/journey').json()['active'] is None
    assert a.post('/api/journey/start',json={}).status_code==200
    assert len(calls)==2


def test_cross_module_reservation_is_atomic_with_real_wrapper(runtime,monkeypatch):
    server,(a,b)=runtime;pool=small_pool();pid=pool['calculation'][0]['puzzle_id']
    monkeypatch.setattr(journey,'inventory',lambda:pool)
    monkeypatch.setattr(learning,'LIB',{pid:journey.LIB[pid]})
    with ThreadPoolExecutor(max_workers=2) as executor:
        jobs=[executor.submit(a.post,'/api/journey/start',json={}),executor.submit(a.post,'/api/learning/start',json={'fresh':True})]
        results=[j.result(timeout=5) for j in jobs]
    assert sorted(r.status_code for r in results)==[200,409],[r.text for r in results]


def test_concurrent_progress_compare_and_swap_without_global_mutex(runtime):
    server,(a,b)=runtime
    snapshots=[server.get_state('RUNTIME-A') for _ in range(4)]
    for i,s in enumerate(snapshots):s['practice']={'attempt':i}
    def save(s):
        try:server.save_state('RUNTIME-A',s);return 200
        except HTTPException as exc:return exc.status_code
    with ThreadPoolExecutor(max_workers=4) as executor:
        assert sorted(executor.map(save,snapshots))==[200,409,409,409]
    assert len(server.get_state('RUNTIME-A')['games'])==0


def test_prebuilt_index_matches_corpus_and_stale_index_rebuilds(monkeypatch,tmp_path):
    import gzip
    import hashlib
    from competencies import COMPETENCIES
    pool=small_pool();row=pool['calculation'][0]
    data={'policy':journey.INDEX_POLICY,'corpus_sha256':hashlib.sha256(journey.DATA_FILE.read_bytes()).hexdigest(),
          'items':{row['puzzle_id']:row},'pools':{c:[row['puzzle_id']] if c=='calculation' else [] for c,v in COMPETENCIES.items() if v['measured']}}
    path=tmp_path/'index.gz'
    with gzip.open(path,'wt') as f:json.dump(data,f)
    monkeypatch.setattr(journey,'INDEX_PATH',path);monkeypatch.setattr(journey,'_prepared',None)
    def unexpected():raise AssertionError('matching index must not rebuild')
    monkeypatch.setattr(journey,'build_inventory',unexpected)
    assert journey.inventory()['calculation']==[row]
    data['corpus_sha256']='stale'
    with gzip.open(path,'wt') as f:json.dump(data,f)
    monkeypatch.setattr(journey,'_prepared',None);monkeypatch.setattr(journey,'build_inventory',lambda:pool)
    assert journey.inventory()==pool
