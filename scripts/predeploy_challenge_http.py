"""Bounded HTTP persistence probe; only the named disposable local container."""
import json,secrets,subprocess,time,urllib.request,urllib.error
BASE='http://127.0.0.1:18080';CONTAINER='cma-predeploy-app'
info=json.loads(subprocess.check_output(['docker','inspect',CONTAINER],text=True))[0]
assert info['HostConfig']['Memory']==536870912 and info['Config']['Image']=='cma-interactive:review'
assert any('@127.0.0.1:55432/cma_predeploy' in e for e in info['Config']['Env'])
def api(path,body=None,token=None):
 h={'Content-Type':'application/json'}
 if token:h['Authorization']='Bearer '+token
 req=urllib.request.Request(BASE+'/api/'+path,json.dumps(body).encode() if body is not None else None,h)
 with urllib.request.urlopen(req,timeout=15) as r:return json.load(r)
token=api('register',{'code':'CHALLENGEIMAGE-'+secrets.token_hex(4),'pin':'temporary-challenge-pin'})['token']
before=api('me',token=token)
s=api('challenge',token=token);assert s['active'] is None
s=api('challenge/action',{'action':'start','revision':s['revision']},token)
s=api('challenge/action',{'action':'hint','revision':s['revision'],'session_id':s['active']['id']},token)
body={'action':'move','move':s['active']['hint'],'revision':s['revision'],'session_id':s['active']['id']}
s=api('challenge/action',body,token)
try:api('challenge/action',body,token);raise AssertionError('duplicate accepted')
except urllib.error.HTTPError as e:assert e.code==409
subprocess.run(['docker','restart',CONTAINER],check=True,stdout=subprocess.DEVNULL)
for _ in range(120):
 try:api('health');break
 except Exception:time.sleep(.25)
else:raise AssertionError('restart timeout')
assert api('challenge',token=token)==s
s=api('challenge/action',{'action':'finish','revision':s['revision'],'session_id':s['active']['id']},token)
assert s['active']['phase']=='ended' and len(s['history'])==1
assert api('challenge/review/'+s['active']['id'],token=token)['id']==s['active']['id']
after=api('me',token=token);assert after['state']==before['state'] and after['stats']==before['stats']
other=api('register',{'code':'CHALLENGEOTHER-'+secrets.token_hex(4),'pin':'temporary-challenge-pin'})['token']
assert api('challenge',token=other)['active'] is None
inspect=json.loads(subprocess.check_output(['docker','inspect',CONTAINER],text=True))[0]
peak=subprocess.check_output(['docker','exec',CONTAINER,'cat','/sys/fs/cgroup/memory.peak'],text=True).strip()
print(json.dumps({'challenge_start_hint_move':'PASS','duplicate_409':'PASS','restart_restore':'PASS','separate_account':'PASS','normal_stats_unchanged':'PASS','oom_killed':inspect['State']['OOMKilled'],'memory_peak_bytes':int(peak)},indent=2))
