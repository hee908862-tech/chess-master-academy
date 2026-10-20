"""Opt-in disposable local container verification. Never targets production."""
import json
import secrets
import subprocess
import time
import urllib.request

CONTAINER='cma-predeploy-app'
info=json.loads(subprocess.check_output(['docker','inspect',CONTAINER],text=True))[0]
assert info['HostConfig']['Memory']==536870912
assert info['HostConfig']['NanoCpus']==1000000000
assert info['Config']['Image']=='cma-interactive:review'
assert any(e.startswith('DATABASE_URL=') and '@127.0.0.1:55432/cma_predeploy' in e for e in info['Config']['Env'])
BASE='http://127.0.0.1:18080/api/'

def api(path,body=None,token=None):
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    with urllib.request.urlopen(urllib.request.Request(BASE+path,json.dumps(body).encode() if body is not None else None,headers),timeout=60) as r:return json.load(r)

for _ in range(120):
    try:api('health');break
    except OSError:time.sleep(.25)
code='FOUNDATION-'+secrets.token_hex(4).upper()
token=api('register',{'code':code,'pin':'temporary-local-pin'})['token']
journey=api('journey/start',{'mode':'balanced'},token)
learning=api('learning/start',{'fresh':True},token)
api('v9/course/start',{'theme':'mateIn1','level':'입문'},token)
course=api('v9/session/course',token=token)
s=api('foundations',token=token)
s=api('foundations/action',{'action':'start','course_id':'opening-turns','revision':s['revision']},token)
s=api('foundations/action',{'action':'move','course_id':'opening-turns','revision':s['revision'],'value':'e2e4'},token)
assert not s['active']['solved'] and 'e5' in s['active']['feedback']
subprocess.run(['docker','restart',CONTAINER],check=True,stdout=subprocess.DEVNULL)
for _ in range(120):
    try:api('health');break
    except OSError:time.sleep(.25)
assert api('foundations',token=token)==s
assert api('journey',token=token)['active']==journey
assert api('learning/dashboard',token=token)['active']==learning
assert api('v9/session/course',token=token)==course
assert api('me',token=token)['stats']['courses_completed']==0
second=api('register',{'code':'FOUND-OTHER-'+secrets.token_hex(3).upper(),'pin':'temporary-local-pin'})['token']
assert api('foundations',token=second)['active'] is None
inspect=json.loads(subprocess.check_output(['docker','inspect',CONTAINER],text=True))[0]
print(json.dumps({'image':inspect['Image'],'conditions':'local 1CPU/512MiB PostgreSQL17; unique temporary accounts','foundation_partial_line_restart_restore':'PASS','diagnosis_learning_course_preserved':'PASS','no_training_credit':'PASS','account_separation':'PASS','oom_killed':inspect['State']['OOMKilled']},indent=2))
