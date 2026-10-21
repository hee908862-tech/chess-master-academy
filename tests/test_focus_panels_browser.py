"""Normal Chromium, disposable local accounts; panels never mutate learning state."""
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import page,site
from test_study_browser import login

@pytest.mark.parametrize('width',[320,390,1280])
def test_training_panels_and_info_preserve_current_task(page,site,width):
 page.set_viewport_size({'width':width,'height':844});login(page,site)
 page.evaluate("tab('training')");page.locator('#learningFresh').click()
 expect(page.locator('#learningBoard .sq')).to_have_count(64)
 before=page.evaluate("api('/learning/dashboard')");writes=[]
 page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
 page.get_by_role('button',name='훈련 선택 · 저장 활동 · 기록',exact=True).click()
 expect(page.locator('#trainingLibrary')).to_be_visible()
 expect(page.locator('#learningBoard')).to_be_hidden()
 page.get_by_role('button',name='현재 훈련으로',exact=True).click()
 expect(page.locator('#learningTitle')).to_be_focused()
 expect(page.locator('#learningBoard')).to_be_visible()
 assert writes==[]
 assert page.evaluate("api('/learning/dashboard')")['active']==before['active']
 page.evaluate("tab('profile')")
 expect(page.locator('#profileInformation')).to_be_visible()
 expect(page.locator('#codeField')).to_be_hidden()
 page.get_by_role('button',name='표시 · 학습 설정',exact=True).click()
 expect(page.locator('#boardThemeSelect')).to_be_visible()
 expect(page.locator('#learningIntervals')).to_be_visible()
 expect(page.locator('#profileSettings')).to_be_focused()
 page.locator('#profileSections').get_by_role('button',name='계정 연결',exact=True).click()
 expect(page.locator('#codeField')).to_be_hidden()
 expect(page.locator('#boardThemeSelect')).to_be_hidden()
 page.get_by_role('button',name='계정 기록 관리',exact=True).click()
 expect(page.locator('#resetProfileV5')).to_be_visible() # Never click reset.
 page.go_back();expect(page.locator('#codeField')).to_be_hidden()
 page.reload();expect(page.locator('#codeField')).to_be_hidden()
 assert writes==[]
 assert page.evaluate("api('/learning/dashboard')")['active']==before['active']
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
 Path('docs/qa-focus-interface/captures').mkdir(parents=True,exist_ok=True)
 page.screenshot(path=f'docs/qa-focus-interface/captures/account-{width}.png',full_page=True)


def test_existing_saved_resume_uses_same_task_without_writes(page,site):
 login(page,site);page.evaluate("tab('training')");page.locator('#learningFresh').click()
 expect(page.locator('#learningBoard .sq')).to_have_count(64)
 saved=page.evaluate("api('/learning/dashboard')")['active'];writes=[]
 page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
 page.get_by_role('button',name='훈련 선택 · 저장 활동 · 기록',exact=True).click()
 page.get_by_role('button',name='현재 훈련 이어하기',exact=True).click()
 expect(page.locator('#learningBoard')).to_be_visible();expect(page.locator('#learningTitle')).to_be_focused()
 assert page.evaluate("api('/learning/dashboard')")['active']==saved
 assert writes==[]


def test_settings_direct_reload_delayed_read_and_retry(page,site):
 login(page,site);page.evaluate("api('/learning/settings','POST',{intervals:[2,5,11]})")
 page.evaluate("tab('profile/settings')")
 expect(page.locator('#learningIntervals')).to_have_value('2,5,11')
 pending=[];writes=[];page.route('**/api/learning/dashboard',lambda r:pending.append(r))
 page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
 page.reload();expect(page.locator('#learningSaveIntervals')).to_be_disabled()
 expect(page.locator('#learningIntervals')).to_have_value('')
 for _ in range(100):
  if len(pending)>=2:break
  page.wait_for_timeout(10)
 assert len(pending)>=1
 for route in list(pending):route.fulfill(response=route.fetch())
 expect(page.locator('#learningSaveIntervals')).to_be_enabled()
 expect(page.locator('#learningIntervals')).to_have_value('2,5,11')
 assert writes==[]
 page.unroute('**/api/learning/dashboard')
 page.route('**/api/learning/dashboard',lambda r:r.fulfill(status=503,json={'detail':'settings read failed'}))
 page.locator('#learningSettingsRetry').click()
 expect(page.locator('#learningSettingsStatus')).to_contain_text('settings read failed')
 expect(page.locator('#learningSaveIntervals')).to_be_disabled()
 page.unroute('**/api/learning/dashboard');page.locator('#learningSettingsRetry').click()
 expect(page.locator('#learningIntervals')).to_have_value('2,5,11');expect(page.locator('#learningSaveIntervals')).to_be_enabled()
 assert writes==[]


def test_settings_late_account_read_and_save_do_not_replace_new_identity(page,site):
 import secrets
 login(page,site);page.evaluate("tab('profile/settings')");expect(page.locator('#learningSaveIntervals')).to_be_enabled()
 pending=[];page.route('**/api/learning/settings',lambda r:pending.append(r))
 page.locator('#learningIntervals').fill('2,6');page.locator('#learningSaveIntervals').click()
 expect(page.locator('#learningSaveIntervals')).to_be_disabled()
 for _ in range(100):
  if pending:break
  page.wait_for_timeout(10)
 assert len(pending)==1
 b=page.request.post(site[0]+'/api/register',data={'code':'SET-'+secrets.token_hex(5),'pin':'settings-test-123'}).json()
 page.request.post(site[0]+'/api/learning/settings',headers={'Authorization':'Bearer '+b['token']},data={'intervals':[3,8]})
 page.evaluate("t=>{token=t;localStorage.setItem('chess_token',t);tab('profile/settings')}",b['token'])
 expect(page.locator('#learningIntervals')).to_have_value('3,8');expect(page.locator('#learningSaveIntervals')).to_be_enabled()
 pending[0].fulfill(status=503,json={'detail':'old account failure'})
 expect(page.locator('#learningSettingsStatus')).not_to_contain_text('old account failure')
 expect(page.locator('#learningIntervals')).to_have_value('3,8')
 assert page.evaluate("api('/learning/dashboard')")['intervals']==[3,8]


def test_guest_alternative_keyboard_focus_without_injected_refocus(page,site):
 context=page.context.browser.new_context();p=context.new_page();writes=[]
 p.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
 p.goto(site[0]);p.locator('#firstEntry').get_by_role('button',name='기초·예제 퍼즐도 저장 없이 체험').click()
 p.get_by_role('button',name='비숍은 대각선으로',exact=True).click()
 p.locator('#guestBoard [aria-label^="c1 "]').focus();p.keyboard.press('Enter')
 p.keyboard.press('ArrowRight');p.keyboard.press('ArrowUp');p.keyboard.press('Enter')
 expect(p.locator('#guestOutcome')).to_contain_text('목표와 달라요')
 expect(p.locator('#guestBoard [aria-label^="d2 "]')).to_be_focused()
 p.keyboard.press('ArrowLeft');p.keyboard.press('ArrowDown');p.keyboard.press('Enter')
 for _ in range(4):p.keyboard.press('ArrowRight');p.keyboard.press('ArrowUp')
 p.keyboard.press('Enter');expect(p.locator('#guestOutcome')).to_contain_text('실습 목표 확인')
 expect(p.locator('#guestOutcome')).to_be_focused();assert writes==[]
 context.close()


def test_settings_late_read_after_actual_account_login_is_ignored(page,site):
 import secrets
 a=login(page,site);page.evaluate("api('/learning/settings','POST',{intervals:[2,5]})")
 code=('SET-READ-'+secrets.token_hex(4)).upper();pin='settings-read-123'
 b=page.request.post(site[0]+'/api/register',data={'code':code,'pin':pin}).json()
 page.request.post(site[0]+'/api/learning/settings',headers={'Authorization':'Bearer '+b['token']},data={'intervals':[3,8]})
 pending=[]
 def read(route):
  if route.request.headers.get('authorization')=='Bearer '+a:pending.append(route)
  else:route.fulfill(response=route.fetch())
 page.route('**/api/learning/dashboard',read)
 page.evaluate("tab('profile/settings')");expect(page.locator('#learningSaveIntervals')).to_be_disabled()
 for _ in range(100):
  if pending:break
  page.wait_for_timeout(10)
 assert pending
 # /me updates user before auth() finishes restoring /game and navigating home.
 # Hold that boundary deliberately; do not mistake identity arrival for login completion.
 game_reads=[]
 def game_read(route):
  if route.request.headers.get('authorization')=='Bearer '+a:route.continue_()
  else:game_reads.append(route)
 page.route('**/api/game',game_read)
 page.evaluate("tab('profile/account')");page.get_by_role('button',name='계정 전환',exact=True).click();page.locator('#codeField').fill(code);page.locator('#pinField').fill(pin);page.locator('#signin').click()
 page.wait_for_function('c=>user?.code===c',arg=code)
 expect(page.locator('#profile')).to_be_visible()
 for _ in range(100):
  if game_reads:break
  page.wait_for_timeout(10)
 assert game_reads
 for r in game_reads:r.fulfill(response=r.fetch())
 expect(page).to_have_url(__import__('re').compile(r'#home$'))
 page.evaluate("tab('profile/settings')");expect(page.locator('#learningIntervals')).to_have_value('3,8')
 for r in pending:r.fulfill(response=r.fetch())
 expect(page.locator('#learningIntervals')).to_have_value('3,8');expect(page.locator('#learningSaveIntervals')).to_be_enabled()
 expect(page.locator('#profileSettings')).to_be_visible()


def test_training_first_read_error_remains_visible_without_board(page,site):
 login(page,site);page.route('**/api/learning/dashboard',lambda r:r.fulfill(status=503,json={'detail':'first training read unavailable'}))
 page.evaluate("tab('training')")
 expect(page.locator('#trainingSelectionStatus')).to_contain_text('first training read unavailable')
 expect(page.locator('#trainingSelectionStatus')).to_be_visible()
 expect(page.locator('#learningRefresh')).to_be_visible()
 page.unroute('**/api/learning/dashboard');page.locator('#learningRefresh').click()
 expect(page.locator('#learningFresh')).to_be_visible()
 assert page.evaluate("api('/learning/dashboard')")['active'] is None


def test_puzzle_choice_closes_only_after_new_session_success(page,site):
 login(page,site);page.evaluate("tab('puzzle')")
 page.locator('#v9PuzzleStart').click()
 expect(page.locator('#v9PuzzleBoard .sq')).to_have_count(64)
 expect(page.locator('#focusPuzzleSelection')).not_to_have_attribute('open','')
 expect(page.locator('#v9PuzzleMeta')).to_be_focused()
 labels=page.locator('#v9PuzzleBoard .sq').evaluate_all('(cells)=>cells.map(c=>c.getAttribute("aria-label"))')
 page.locator('#focusPuzzleSelection > summary').click()
 page.route('**/api/v9/puzzle/start',lambda r:r.fulfill(status=503,json={'detail':'controlled start failure'}))
 page.locator('#v9PuzzleStart').click()
 expect(page.locator('#v9PuzzleMessage')).to_contain_text('controlled start failure')
 expect(page.locator('#focusPuzzleSelection')).to_have_attribute('open','')
 expect(page.locator('#v9PuzzleBoard .sq')).to_have_count(0)


def test_settings_same_route_during_save_keeps_pending_owner(page,site):
 login(page,site);page.evaluate("tab('profile/settings')");expect(page.locator('#learningSaveIntervals')).to_be_enabled()
 pending=[];page.route('**/api/learning/settings',lambda r:pending.append(r))
 page.locator('#learningIntervals').fill('2,6');page.locator('#learningSaveIntervals').click()
 page.evaluate("tab('profile/settings')")
 expect(page.locator('#learningSaveIntervals')).to_be_disabled();expect(page.locator('#learningIntervals')).to_have_value('2,6')
 for _ in range(100):
  if pending:break
  page.wait_for_timeout(10)
 assert len(pending)==1
 pending[0].fulfill(response=pending[0].fetch())
 expect(page.locator('#learningSaveIntervals')).to_be_enabled()
 expect(page.locator('#learningSettingsStatus')).to_contain_text('저장했습니다')
 assert page.evaluate("api('/learning/dashboard')")['intervals']==[2,6]
