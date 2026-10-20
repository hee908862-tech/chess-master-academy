"""Opt-in against the named disposable loopback app only; never production."""
import json
import chess
import psycopg
from pathlib import Path
import secrets
import subprocess
import time
import urllib.request
BASE='http://127.0.0.1:18080'
CONTAINER='cma-predeploy-app'
info=json.loads(subprocess.check_output(['docker','inspect',CONTAINER],text=True))[0]
assert info['HostConfig']['Memory']==536870912
assert info['Config']['Image']=='cma-interactive:review'
assert any(e.startswith('DATABASE_URL=') and '@127.0.0.1:55432/cma_predeploy' in e for e in info['Config']['Env'])

def api(path,body=None,token=None):
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    req=urllib.request.Request(BASE+'/api/'+path,json.dumps(body).encode() if body is not None else None,headers)
    with urllib.request.urlopen(req,timeout=15) as r:return json.load(r)
for _ in range(120):
    try:api('health');break
    except Exception:time.sleep(.25)
else:raise AssertionError('health timeout')
token=api('register',{'code':'STUDYIMAGE-'+secrets.token_hex(4),'pin':'temporary-study-pin'})['token']
before=api('me',token=token)['state']
branch=api('study/position',{'moves':['e2e4'],'engine':True},token);assert branch['reply']
assert api('me',token=token)['state']==before
catalog=api('study/openings',token=token);assert len(catalog['courses'])==27 and catalog['reference_count']==3865
moves=['e2e4','e7e6','d2d4','d7d5','e4e5','c7c5']
explore=api('study/openings/position',{'course_id':'french-advance','moves':moves},token)
assert 'd4' in explore['note']['comment']
recall=api('study/openings/position',{'course_id':'french-advance','moves':moves,'mode':'recall'},token)
assert recall['options']==[] and recall['note'] is None
saved=api('study/openings/save',{'course_id':'french-advance','moves':moves,'mode':'recall','orientation':'black','revision':0},token)
subprocess.run(['docker','restart',CONTAINER],check=True,stdout=subprocess.DEVNULL)
for _ in range(120):
    try:api('health');break
    except Exception:time.sleep(.25)
else:raise AssertionError('restart timeout')
assert api('study/openings',token=token)['saved']==saved
state=api('me',token=token)['state'];state.pop('opening_study',None);assert state==before
# Seed only this uniquely named disposable QA diagnosis to reproduce reported Qc3.
probe_code=('OZELQIMAGE-'+secrets.token_hex(4)).upper()
probe=api('register',{'code':probe_code,'pin':'temporary-study-pin'})['token']
api('journey/start',{'mode':'balanced'},probe)
row=next(json.loads(line) for line in Path('puzzles_lichess.jsonl').open() if '"OZElq"' in line)
b=chess.Board(row['fen']);b.push_uci(row['moves'][0])
with psycopg.connect('postgresql://cma:temporary-local-only@127.0.0.1:55432/cma_predeploy') as conn:
    state=json.loads(conn.execute('SELECT state FROM journey_progress WHERE code=%s',(probe_code,)).fetchone()[0])
    active=state['active'];item=active['items'][active['index']]
    item.update(puzzle_id='OZElq',fen=b.fen(),line=row['moves'][1:],competency='capture',band=[1200,1800],tags=row['themes'])
    active.update(fen=b.fen(),offset=0,correct=0,submitted=[],played=[],phase='question')
    conn.execute('UPDATE journey_progress SET state=%s WHERE code=%s',(json.dumps(state),probe_code))
judged=api('journey/action',{'session_id':active['session_id'],'revision':active['revision'],'action':'move','move':'d2c3'},probe)['feedback']
assert judged['outcome']=='verified_error',judged
inspect=json.loads(subprocess.check_output(['docker','inspect',CONTAINER],text=True))[0]
peak=subprocess.check_output(['docker','exec',CONTAINER,'cat','/sys/fs/cgroup/memory.peak'],text=True).strip()
print(json.dumps({'conditions':'local image 1CPU/512MiB, PostgreSQL17 loopback, temporary account','ozelq_balanced_512m':judged['engine_evidence'],'courses':27,'references':3865,'actual_engine_reply':branch['reply'],'read_only_branch':'PASS','recall_no_answers':'PASS','bookmark_restart_restore':'PASS','game_state_unchanged':'PASS','oom_killed':inspect['State']['OOMKilled'],'memory_peak_bytes':int(peak)},indent=2))
