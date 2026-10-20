"""Opt-in local disposable 1CPU/512MiB image; not production."""
import json
import secrets
import subprocess
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from repertoire_content import CORE,lesson
BASE='http://127.0.0.1:18080';CONTAINER='cma-predeploy-app'
info=json.loads(subprocess.check_output(['docker','inspect',CONTAINER],text=True))[0]
assert info['HostConfig']['Memory']==536870912 and info['HostConfig']['NanoCpus']==1000000000
assert info['Config']['Image']=='cma-interactive:review'
assert any(e.startswith('DATABASE_URL=') and '@127.0.0.1:55432/cma_predeploy' in e for e in info['Config']['Env'])
def api(path,body=None,token=None):
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    req=urllib.request.Request(BASE+'/api/'+path,json.dumps(body).encode() if body is not None else None,headers)
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
def ready():
    for _ in range(120):
        try:api('health');return
        except Exception:time.sleep(.25)
    raise AssertionError('health timeout')
ready();token=api('register',{'code':'REPIMAGE-'+secrets.token_hex(5),'pin':'temporary-local-pin'})['token']
bookmark=api('study/openings/save',{'course_id':'sicilian-alapin','moves':['e2e4'],'mode':'recall','orientation':'black','revision':0},token)
diagnosis=api('journey/start',{'mode':'balanced'},token)
before=api('me',token=token)['state']
data=api('repertoire',token=token)
def action(name,**kw):
    global data
    data=api('repertoire/action',{'action':name,'revision':data['revision'],'attempt_id':(data.get('active') or {}).get('id'),**kw},token)
    return data
for course in CORE:
    action('select',selected=[course])
    for side in ['white','black']:
        action('start',lesson_id=course,mode='recall',side=side)
        while data['active']['phase']=='playing':
            r=data['active'];assert r['guidance'] is None and not r['options']
            line=next(line for line in lesson(course)['branches'].values() if line[:len(r['moves'])]==r['moves'])
            action('move',move=line[len(r['moves'])])
        action('finish')
action('select',selected=['london-qb6']);action('start',lesson_id='london-qb6',mode='learn')
while len(data['active']['moves'])<10:
    r=data['active'];action('move',move=lesson('london-qb6')['branches']['main'][len(r['moves'])])
saved=data
subprocess.run(['docker','restart',CONTAINER],check=True,stdout=subprocess.DEVNULL);ready()
assert api('repertoire',token=token)==saved
assert api('study/openings',token=token)['saved']==bookmark
assert api('journey',token=token)['active']==diagnosis
state=api('me',token=token)['state'];state.pop('opening_repertoire_v1',None);assert state==before
out=Path('docs/qa-repertoire');out.mkdir(exist_ok=True,parents=True)
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    for width in [390,1280]:
        page=browser.new_page(viewport={'width':width,'height':950})
        page.add_init_script('localStorage.setItem("chess_token",'+json.dumps(token)+');')
        page.goto(BASE);page.evaluate("tab('opening')")
        page.get_by_role('button',name='레퍼토리 선택·이어하기',exact=True).click()
        expect(page.locator('#repertoireBody')).to_contain_text('자기 c5 폰에 막혀')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        page.locator('#repertoire').screenshot(path=str(out/f'image-learn-{width}.png'))
        page.close()
    browser.close()
inspect=json.loads(subprocess.check_output(['docker','inspect',CONTAINER],text=True))[0]
print(json.dumps({'source_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'image':inspect['Image'],'core_white_black_completions':14,'restart_restore':'PASS','bookmark_and_active_diagnosis_preserved':'PASS','other_progress_unchanged':'PASS','browser':'Chromium390/1280 actual image APIs','oom_killed':inspect['State']['OOMKilled'],'memory_peak_bytes':int(subprocess.check_output(['docker','exec',CONTAINER,'cat','/sys/fs/cgroup/memory.peak'],text=True))},indent=2))
