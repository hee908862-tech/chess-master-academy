"""Real local image HTTP, cold/warm measurements and lost-response recovery.
Requires the explicitly named disposable Docker container and loopback port.
"""
import http.client
import json
import secrets
import subprocess
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

BASE='http://127.0.0.1:18080'

def request(path,body=None,token=None):
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    req=urllib.request.Request(BASE+'/api/'+path,json.dumps(body).encode() if body is not None else None,headers)
    with urllib.request.urlopen(req,timeout=15) as response:return json.load(response)

def account():
    code=('IMAGE-'+secrets.token_hex(4)).upper()
    return request('register',{'code':code,'pin':'temporary-image-pin'})['token']

def memory():
    probe="from pathlib import Path; p=next(p for p in Path('/proc').iterdir() if p.name.isdigit() and (p/'cmdline').exists() and b'/usr/local/bin/uvicorn\\x00server:app\\x00' in (p/'cmdline').read_bytes()); print((p/'status').read_text())"
    text=subprocess.check_output(['docker','exec','cma-predeploy-app','python','-c',probe],text=True)
    return {line.split(':')[0]:line.split(':')[1].strip() for line in text.splitlines() if line.startswith(('VmRSS:','VmHWM:'))}

def timed(path,body,token):
    start=time.perf_counter();result=request(path,body,token)
    return {'path':path,'seconds':round(time.perf_counter()-start,4)},result

for _ in range(600):
    try:request('health');break
    except Exception:time.sleep(.1)
else:raise AssertionError('Initial image health timeout (60 seconds)')
a,b,warm,lost=account(),account(),account(),account()
output={'conditions':'Docker app 1 CPU/512MiB, PG 1 CPU/512MiB, loopback HTTP, unique temporary accounts, single sample','memory_before':memory()}
with ThreadPoolExecutor(max_workers=4) as pool:
    cold=pool.submit(timed,'journey/start',{},a)
    other=[pool.submit(timed,path,body,b) for path,body in [('me',None),('onboarding',None),('game/new',{'color':'white'})]]
    output['cold'],active=cold.result()
    output['concurrent']=[f.result()[0] for f in other]
output['warm'],_=timed('journey/start',{},warm)
output['memory_after']=memory()
# A real TCP relay waits for upstream commit, then loses the response entirely.
committed=threading.Event();committed_session=[]
class DropResponse(BaseHTTPRequestHandler):
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        saved=request('journey/start',body,lost)
        committed_session.append(saved['session_id']);committed.set()
        self.close_connection=True # no HTTP status/body delivered to client
    def log_message(self,*args):pass
proxy=ThreadingHTTPServer(('127.0.0.1',0),DropResponse)
thread=threading.Thread(target=proxy.serve_forever,daemon=True);thread.start()
try:
    req=urllib.request.Request(f'http://127.0.0.1:{proxy.server_port}/',b'{}',{'Content-Type':'application/json'})
    try:
        urllib.request.urlopen(req,timeout=15)
        raise AssertionError('Response should be lost')
    except http.client.RemoteDisconnected:pass
    assert committed.wait(1)
    restored=request('journey',token=lost)['active']
    assert restored['session_id']==committed_session[0]
    try:request('journey/start',{},lost);raise AssertionError('Duplicate start accepted')
    except urllib.error.HTTPError as error:assert error.code==409
finally:proxy.shutdown();proxy.server_close();thread.join()
output['lost_response_recovery']='PASS: actual TCP disconnect after commit; GET restores same session; repeat POST 409'
# Persist one action, restart only the disposable app, resume same session/revision.
saved=request('journey/action',{'session_id':active['session_id'],'revision':active['revision'],'action':'skip'},a)
restart_begin=time.perf_counter()
subprocess.run(['docker','restart','cma-predeploy-app'],check=True,stdout=subprocess.DEVNULL)
output['restart_command_seconds']=round(time.perf_counter()-restart_begin,4)
assert output['restart_command_seconds']<5,'Idle app should gracefully stop without the 10-second kill deadline'
for _ in range(600):
    try:request('health');break
    except Exception:time.sleep(.1)
else:raise AssertionError('Restart health timeout')
assert request('journey',token=a)['active']==saved
output['process_restart_resume']='PASS: same saved diagnostic session/revision after actual image process restart'
# Finish the persisted diagnosis, begin linked training, save a hint, then restart again.
s=saved
while s['phase']!='complete':
    if s['phase']=='question':s=request('journey/action',{'session_id':s['session_id'],'revision':s['revision'],'action':'skip'},a)
    s=request('journey/action',{'session_id':s['session_id'],'revision':s['revision'],'action':'next'},a)
report=s['report'];item=report['items'][0]
linked=request('learning/from-diagnosis',{'report_id':report['id'],'item_id':item['id']},a)
t=linked['active']
training=request('learning/action',{'session_id':t['session_id'],'revision':t['revision'],'action':'hint'},a)
subprocess.run(['docker','restart','cma-predeploy-app'],check=True,stdout=subprocess.DEVNULL)
for _ in range(600):
    try:request('health');break
    except Exception:time.sleep(.1)
else:raise AssertionError('Training restart health timeout')
assert request('learning/dashboard',token=a)['active']==training
again=request('learning/from-diagnosis',{'report_id':report['id'],'item_id':item['id']},a)
assert again['active']==training and again['path']['id']==linked['path']['id']
output['training_restart_resume']='PASS: saved hint/session/revision retained; repeated bridge returns same path/task'
print(json.dumps(output,ensure_ascii=False,indent=2))
