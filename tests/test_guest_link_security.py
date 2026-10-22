import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from test_runtime_isolation import runtime
from guest_access import shared_limit, SESSION_TTL


def test_link_revokes_anonymous_and_binds_resume_to_owner_session(runtime):
    server,(owner,other)=runtime
    guest=TestClient(server.app)
    data=guest.post('/api/guest/start').json()
    header={'Authorization':'Bearer '+data['token']}
    guest.headers.update(header)
    another_tab=TestClient(server.app,headers=header)
    assert another_tab.get('/api/me').status_code==200  # pre-link reload
    with server.db() as c:
        before=server.execute(c,'SELECT state FROM progress WHERE code=?',(data['code'],)).fetchone()['state']
    for _ in range(2):assert owner.post('/api/guest/link',json={'guest_token':data['token']}).status_code==200
    assert guest.get('/api/me').status_code==401
    assert another_tab.get('/api/foundations').status_code==401
    assert guest.post('/api/game/new',json={'color':'white'}).status_code==401
    assert other.post('/api/guest/link',json={'guest_token':data['token']}).status_code==409
    assert other.post('/api/guest/resume',json={'id':data['code']}).status_code==404
    delegated=owner.post('/api/guest/resume',json={'id':data['code']}).json()
    resumed=TestClient(server.app,headers={'Authorization':'Bearer '+delegated['token']})
    assert resumed.get('/api/me').status_code==200
    assert resumed.post('/api/guest/resume',json={'id':data['code']}).status_code==403
    assert owner.post('/api/logout').status_code==200
    assert resumed.get('/api/me').status_code==401  # independent delegate rejected
    # Re-login from another device: existing namespace, never overwrite account state.
    PIN = "local-runtime-9384"
    new=TestClient(server.app)
    logged=new.post('/api/login',json={'code':'RUNTIME-A','pin':PIN})
    assert logged.status_code==200
    new.headers['Authorization']='Bearer '+logged.json()['token']
    again=new.post('/api/guest/resume',json={'id':data['code']}).json()
    resumed.headers['Authorization']='Bearer '+again['token']
    assert resumed.get('/api/me').status_code==200
    parent_hash=hashlib.sha256(logged.json()['token'].encode()).hexdigest()
    with server.db() as c:
        server.execute(c,'UPDATE sessions SET created=? WHERE token_hash=?',(int(time.time())-SESSION_TTL-1,parent_hash))
        assert server.execute(c,'SELECT state FROM progress WHERE code=?',(data['code'],)).fetchone()['state']==before
    assert new.get('/api/me').status_code==401
    assert resumed.get('/api/me').status_code==401


def test_db_budget_atomic_shared_and_no_proxy_identity(runtime):
    server,_=runtime
    def call(_):
        try:shared_limit(vars(server),'concurrent-test',5,60);return 200
        except HTTPException as exc:return exc.status_code
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(call,range(12)))
    assert results.count(200)==5 and results.count(429)==7
    client=TestClient(server.app)
    for _ in range(11):
        assert client.post('/api/guest/start',headers={'X-Forwarded-For':'forged'}).status_code==200
    shared_limit(vars(server),'independent',1,60)
    with pytest.raises(HTTPException) as error:shared_limit(vars(server),'independent',1,60)
    assert error.value.headers.get('Retry-After')
