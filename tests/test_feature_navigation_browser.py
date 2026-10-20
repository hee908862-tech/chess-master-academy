import json
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page
from test_study_browser import login,click_move

@pytest.mark.parametrize('width',[390,1280])
def test_navigation_help_no_mutations_and_opening_layout(page,site,width):
 page.set_viewport_size({'width':width,'height':950});login(page,site)
 posts=[];errors=[]
 page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
 page.on('pageerror',lambda e:errors.append(str(e)))
 nav=page.locator('.mobile-nav' if width==390 else '.nav')
 button=nav.locator('[data-tab="learn"]');button.focus();page.keyboard.press('Enter')
 expect(page.locator('#academyNavigationDialog')).to_be_visible()
 page.keyboard.press('Shift+Tab');expect(page.locator('#academyNavigationDialog button').last).to_be_focused()
 page.keyboard.press('Tab');expect(page.locator('#academyNavigationDialog button').first).to_be_focused()
 page.keyboard.press('Escape');expect(button).to_be_focused()
 button.click();page.locator('[data-academy="tactics"]').click()
 expect(page.locator('#learn')).to_have_class('view active')
 expect(page.locator('#academyTactics')).to_have_attribute('open','')
 expect(page.locator('#academyLocation')).to_contain_text('전술 훈련')
 page.locator('#learn .feature-toolbar button').click();expect(page.locator('#featureHelpDialog')).to_be_visible()
 page.keyboard.press('Shift+Tab');expect(page.locator('#featureHelpDialog button')).to_be_focused()
 page.keyboard.press('Escape');expect(page.locator('#learn .feature-toolbar button')).to_be_focused()
 page.locator('[data-academy-choice="resume"]').click();expect(page.locator('#academyResume')).to_be_focused()
 assert not posts,posts
 page.evaluate("tab('opening')");expect(page.locator('#studyCourse option')).to_have_count(55)
 page.locator('#studyCourse').select_option('london-core');expect(page.locator('#studyOpeningBoard .sq')).to_have_count(64)
 page.locator('#opening .feature-jumps').get_by_role('button',name='착수 해설').click();expect(page.locator('#studyExplanation')).to_be_focused()
 expect(page.locator('#openingStudy')).to_contain_text('55개 해설 강의')
 expect(page.locator('#openingStudy')).to_contain_text('192개 주요 착수 해설')
 assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
 out=Path('docs/qa-navigation');out.mkdir(exist_ok=True)
 page.screenshot(path=str(out/f'opening-{width}.png'),full_page=True)
 page.evaluate("tab('learn')");button.click();page.screenshot(path=str(out/f'menu-{width}.png'))
 assert not errors,errors

@pytest.mark.parametrize('width',[390,1280])
def test_challenge_actual_server_restore_mistake_review(page,site,width):
 page.set_viewport_size({'width':width,'height':950});login(page,site)
 page.evaluate("tab('puzzle')");page.locator('#puzzleModeChallenge').click();expect(page.locator('#challengeStart')).to_be_enabled()
 page.locator('#challengeStart').click();expect(page.locator('#challengeProgress')).to_contain_text('목숨 3')
 page.locator('#challengeHint').click();expect(page.locator('#challengeHintText')).to_contain_text('현재 기준 수')
 hint=page.locator('#challengeHintText').inner_text().split(': ')[1]
 click_move(page,'challengeBoard',hint)
 expect(page.locator('#challengeFinish')).to_be_enabled()
 page.reload();page.evaluate("tab('puzzle')");page.locator('#puzzleModeChallenge').click();expect(page.locator('#challengeProgress')).to_contain_text('목숨 3')
 # Leave, return and end without inventing client-side score.
 page.evaluate("tab('training');tab('puzzle')");expect(page.locator('#challengeFinish')).to_be_enabled()
 page.locator('#challengeFinish').click();expect(page.locator('#challengeProgress')).to_contain_text('종료')
 page.locator('#challengeHistory button').first.click()
 expect(page.locator('#challengeReview')).not_to_be_empty()
 page.locator('#challengeStart').click();expect(page.locator('#challengeProgress')).to_contain_text('목숨 3')
 for i in range(3):
  page.locator('#challengeNext').click();expect(page.locator('#challengeProgress')).to_contain_text(f'목숨 {2-i}')
  if i<2:page.locator('#challengeNext').click();expect(page.locator('#challengeNext')).to_contain_text('건너뛰기')
 page.locator('#challengeHistory button').first.click();expect(page.locator('.challenge-review-item')).to_have_count(3)
 expect(page.locator('#challengeReviewBoard0 .sq')).to_have_count(64)
 assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
 out=Path('docs/qa-navigation');out.mkdir(exist_ok=True);page.screenshot(path=str(out/f'challenge-{width}.png'),full_page=True)


def test_delayed_challenge_submit_navigation_reload_and_duplicate(page,site):
 login(page,site);page.evaluate("tab('puzzle')");page.locator('#puzzleModeChallenge').click();expect(page.locator('#challengeStart')).to_be_enabled()
 page.locator('#challengeStart').click();expect(page.locator('#challengeProgress')).to_contain_text('목숨 3')
 pending=[];page.route('**/api/challenge/action',lambda route:pending.append(route))
 page.locator('#challengeNext').click();expect(page.locator('#challengeNext')).to_be_disabled()
 assert len(pending)==1
 body=pending[0].request.post_data_json
 page.evaluate("tab('home')")
 with page.expect_response(lambda r:r.url.endswith('/challenge/action')):pending[0].continue_()
 page.unroute('**/api/challenge/action')
 page.evaluate("tab('puzzle')");expect(page.locator('#challengeProgress')).to_contain_text('목숨 2')
 # A replayed network request cannot consume another life.
 status=page.evaluate("async body => {const r=await fetch('/api/challenge/action',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},body:JSON.stringify(body)});return r.status;}",body)
 assert status==409
 page.reload();page.evaluate("tab('puzzle')");page.locator('#puzzleModeChallenge').click();expect(page.locator('#challengeProgress')).to_contain_text('목숨 2')


def test_challenge_promotion_cancel_on_navigation_and_underpromotion_ui(page,site):
 login(page,site)
 state={'revision':1,'history':[],'active':{'id':'ui-only-promotion','level':'입문','index':0,'phase':'playing','score':0,'lives':3,'feedback':'승격 UI fixture','hinted':False,'hint':None,'started_at':'fixture','total':10,'fen':'6k1/P7/8/8/8/8/8/4K3 w - - 1 2','side':'white','legal':['a7a8q','a7a8r','a7a8b','a7a8n'],'rating':1000,'themes':[],'puzzle_id':'fixture'}}
 page.route('**/api/challenge',lambda r:r.fulfill(json=state))
 submitted=[]
 def action(r):
  submitted.append(r.request.post_data_json);r.fulfill(json=state)
 page.route('**/api/challenge/action',action)
 page.evaluate("tab('puzzle')");page.locator('#puzzleModeChallenge').click();expect(page.locator('#challengeBoard .sq:enabled')).to_have_count(64)
 click_move(page,'challengeBoard','a7a8');expect(page.locator('.cma-promotion-modal')).to_be_visible()
 page.keyboard.press('Escape');expect(page.locator('.cma-promotion-modal')).to_be_hidden();assert not submitted
 click_move(page,'challengeBoard','a7a8');page.get_by_role('button',name='승격 선택 취소',exact=True).click();expect(page.locator('.cma-promotion-modal')).to_be_hidden();assert not submitted
 click_move(page,'challengeBoard','a7a8');page.evaluate("tab('home');tab('puzzle')");expect(page.locator('.cma-promotion-modal')).to_be_hidden();assert not submitted
 click_move(page,'challengeBoard','a7a8');page.get_by_role('button',name='나이트',exact=False).last.click()
 expect(page.locator('.cma-promotion-modal')).to_be_hidden()
 assert len(submitted)==1 and submitted[0]['move']=='a7a8n'


def test_study_promotion_cancel_restores_board_controls(page,site):
 """Controlled promotion position tests UI cancellation, not opening theory."""
 login(page,site)
 position={'fen':'6k1/P7/8/8/8/8/8/4K3 w - - 1 2','legal':['a7a8q','a7a8r','a7a8b','a7a8n'],'terminal':False,'reply':None}
 page.route('**/api/study/position',lambda r:r.fulfill(json=position))
 page.evaluate("tab('opening')");expect(page.locator('#studyOpeningBoard .sq:enabled')).to_have_count(64)
 click_move(page,'studyOpeningBoard','a7a8');expect(page.locator('#cmaPromotionModal')).to_be_visible()
 page.keyboard.press('Escape');expect(page.locator('#cmaPromotionModal')).to_be_hidden()
 expect(page.locator('#studyOpeningBoard .sq:enabled')).to_have_count(64)
 click_move(page,'studyOpeningBoard','a7a8');page.get_by_role('button',name='승격 선택 취소',exact=True).click()
 expect(page.locator('#studyOpeningBoard .sq:enabled')).to_have_count(64)
