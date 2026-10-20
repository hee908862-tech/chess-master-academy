import json,secrets,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
base='http://127.0.0.1:18080'
# Guard the same bounded disposable environment as the HTTP regression probes.
import subprocess
info=json.loads(subprocess.check_output(['docker','inspect','cma-predeploy-app'],text=True))[0]
assert info['HostConfig']['Memory']==536870912 and info['Config']['Image']=='cma-interactive:review'
assert any('@127.0.0.1:55432/cma_predeploy' in e for e in info['Config']['Env'])
req=urllib.request.Request(base+'/api/register',json.dumps({'code':'GUIDEIMAGE-'+secrets.token_hex(4),'pin':'temporary-guide-pin'}).encode(),{'Content-Type':'application/json'})
token=json.load(urllib.request.urlopen(req))['token']
out=Path('docs/qa-navigation');out.mkdir(exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
 results=[]
 for width in [390,1280]:
  page=b.new_page(viewport={'width':width,'height':950});page.set_default_timeout(10000)
  page.add_init_script(f"localStorage.setItem('chess_token',{json.dumps(token)});localStorage.setItem('cma_prefs',JSON.stringify({{soundOn:false}}));")
  page.route('**/api/onboarding',lambda r:r.fulfill(json={'status':'completed','version':1}))
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(base);page.wait_for_timeout(500)
  for id in ['home','learn','diagnosis','training','opening','review','puzzle','play','profile','help']:
   page.evaluate('(id)=>tab(id)',id);page.wait_for_timeout(250)
   calls=[]
   def record(r):
    if r.method=='POST':calls.append(r.url)
   page.on('request',record)
   button=page.locator('#'+id+' > header.feature-toolbar button');button.click();expect(page.locator('#featureHelpDialog')).to_be_visible()
   page.keyboard.press('Escape');expect(button).to_be_focused();page.remove_listener('request',record)
   assert not calls,(id,calls)
  nav=page.locator('.mobile-nav' if width==390 else '.nav').locator('[data-tab="learn"]')
  nav.click();expect(page.locator('#academyNavigationDialog')).to_be_visible();page.keyboard.press('Shift+Tab');expect(page.locator('#academyNavigationDialog button').last).to_be_focused();page.keyboard.press('Tab');expect(page.locator('#academyNavigationDialog button').first).to_be_focused();page.mouse.click(2,2);expect(page.locator('#academyNavigationDialog')).not_to_be_visible();expect(nav).to_be_focused()
  page.evaluate("tab('training')");page.locator('#learningFresh').click();expect(page.locator('#learningBoard .sq')).to_have_count(64)
  page.locator('#training .feature-jumps').get_by_role('button',name='개념·해설과 수순',exact=True).click();expect(page.locator('#learningDetails')).to_be_focused()
  assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
  page.screenshot(path=str(out/f'training-{width}.png'),full_page=True)
  assert not errors,errors
  results.append({'width':width,'help_screens':10,'help_post_requests':0,'escape_focus':'PASS','menu_outside_click_focus':'PASS','menu_tab_focus_loop':'PASS','actual_training_board_and_explanation':'PASS','page_errors':errors})
  page.close()
 b.close()
print(json.dumps(results,indent=2))
