import json,secrets,urllib.request,subprocess,hashlib
from pathlib import Path
import psycopg
url='http://127.0.0.1:18080/api/'
info=json.loads(subprocess.check_output(['docker','inspect','cma-predeploy-app'],text=True))[0]
assert info['HostConfig']['Memory']==536870912 and info['HostConfig']['NanoCpus']==1000000000
assert info['Config']['Image']=='cma-interactive:review'
code=('FLOWIMAGE-'+secrets.token_hex(4)).upper()
token=None
def api(path,body=None):
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    r=urllib.request.Request(url+path,json.dumps(body).encode() if body is not None else None,headers)
    with urllib.request.urlopen(r,timeout=30) as response:return json.load(response)
def saved():
    with psycopg.connect('postgresql://cma:temporary-local-only@127.0.0.1:55432/cma_predeploy') as db:
        return json.loads(db.execute('SELECT state FROM journey_progress WHERE code=%s',(code,)).fetchone()[0])
api('health');token=api('register',{'code':code,'pin':'temporary-flow-image'})['token']
old=api('me')['state'];s=api('journey/start',{'mode':'balanced'});total=s['total']
while s['phase']!='complete':
    body={'session_id':s['session_id'],'revision':s['revision']}
    if s['phase']=='feedback':body['action']='next'
    elif s['index']==0:
        active=saved()['active'];body.update(action='move',move=active['items'][0]['line'][active['offset']])
    else:body['action']='skip'
    s=api('journey/action',body)
before=saved();d=api('journey');assert saved()==before and d['latest']==before['results'][-1]
e=d['learning_evidence'][d['latest']['id']]
assert e[next(iter(e))]['label']=='전체 수순 성공'
assert len(e)==total
assert all('미응답' in v['label'] for v in list(e.values())[1:])
item=d['latest']['items'][0]
learn=api('learning/from-diagnosis',{'report_id':d['latest']['id'],'item_id':item['id']})
assert learn['active']['learning_link']['item_id']==item['id']
assert api('me')['state']==old
print(json.dumps({'image':info['Image'],'cpus':1,'memory':info['HostConfig']['Memory'],'actual_balanced_total':total,'completed_first_and_skipped_rest':True,'observation_get_storage_unchanged':True,'training_source_link':True,'legacy_state_unchanged':True},indent=2))

from playwright.sync_api import sync_playwright,expect
out=Path('docs/qa-evidence-flow');out.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    page=browser.new_page();page.add_init_script('localStorage.setItem("chess_token",'+json.dumps(token)+')')
    page.goto('http://127.0.0.1:18080/')
    for width in (390,1280):
        page.set_viewport_size({'width':width,'height':950})
        page.evaluate("tab('diagnosis')")
        expect(page.locator('.growth-plan')).to_be_visible()
        expect(page.locator('.learning-observation').first).to_contain_text('미응답')
        expect(page.locator('#diagnosis')).to_have_attribute('aria-busy','false')
        page.locator('.growth-task').first.screenshot(path=str(out/f'actual-recommendation-{width}.png'))
        page.evaluate("tab('home')")
        expect(page.locator('#journeyHomeOpen')).to_contain_text('훈련 이어하기')
        page.screenshot(path=str(out/f'actual-home-{width}.png'))
        page.locator(('.mobile-nav' if width==390 else '.nav')+' [data-tab="learn"]').click()
        page.screenshot(path=str(out/f'actual-menu-{width}.png'))
        page.keyboard.press('Escape')
    browser.close()
