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
 if width==390:
  page.keyboard.press('Shift+Tab');expect(page.locator('#academyNavigationDialog button').last).to_be_focused()
  page.keyboard.press('Tab');expect(page.locator('#academyNavigationDialog button').first).to_be_focused()
 else:
  assert not page.locator('#academyNavigationDialog').evaluate("e=>e.matches(':modal')")
 page.keyboard.press('Escape');expect(button).to_be_focused()
 button.click();page.locator('[data-academy="tactics"]').click()
 expect(page.locator('#learn')).to_have_class('view active')
 expect(page.locator('#academyTactics')).to_have_attribute('open','')
 expect(page.locator('#learning-location')).to_contain_text('전술 과목')
 page.locator('#learn .feature-toolbar button').click();expect(page.locator('#featureHelpDialog')).to_be_visible()
 page.keyboard.press('Shift+Tab');expect(page.locator('#featureHelpDialog button')).to_be_focused()
 page.keyboard.press('Escape');expect(page.locator('#learn .feature-toolbar button')).to_be_focused()
 page.locator('#learn-hub-back').click();page.locator('#learn-saved').click();expect(page.locator('#academyResume')).to_be_focused()
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


@pytest.mark.parametrize('width',[390,1280])
def test_academy_disclosure_preserves_review_branch_and_pending_engine(page,site,width):
 import chess
 page.set_viewport_size({'width':width,'height':950});login(page,site)
 page.route('**/api/games/history',lambda r:r.fulfill(json=[{'index':0,'color':'white','plies':1,'result':'loss'}]))
 b=chess.Board();b.push_uci('e2e4')
 original={'color':'white','moves':[{'uci':'e2e4','san':'e4','side':'백','after_fen':b.fen(),'centipawn_loss':0,'category':'참고','comment':'원본'}]}
 page.route('**/api/games/review/0',lambda r:r.fulfill(json=original))
 page.evaluate("tab('review')");expect(page.locator('#reviewLoad')).to_be_enabled();page.locator('#reviewLoad').click();expect(page.locator('#reviewStep')).to_contain_text('0 / 1')
 page.locator('#reviewBranchStart').click();expect(page.locator('#reviewBranchStatus')).to_contain_text('양쪽')
 click_move(page,'reviewBoard','d2d4');expect(page.locator('#reviewStep')).to_contain_text('분기 1')
 nav=page.locator('.mobile-nav' if width==390 else '.nav').locator('[data-tab="learn"]')
 expect(page.locator('.cma-motion-ghost')).to_have_count(0)
 board=page.locator('#reviewBoard').inner_html()
 for close in ['escape','outside']:
  nav.click();expect(page.locator('#academyNavigationDialog')).to_be_visible();expect(page.locator('#review')).to_have_class('view active')
  if close=='escape':page.keyboard.press('Escape')
  else:page.mouse.click(2,2)
  expect(nav).to_be_focused();expect(page.locator('#reviewStep')).to_contain_text('분기 1')
  assert page.locator('#reviewBoard').inner_html()==board
 page.evaluate("""() => {const old=api;api=(path,method,body)=>path==='/study/position'&&body.engine?new Promise(resolve=>window.releaseReviewEngine=resolve):old(path,method,body);} """)
 page.get_by_role('button',name='현재 차례 엔진 응수',exact=True).click();expect(page.locator('#reviewBranchStatus')).to_contain_text('계산 중')
 for close in ['escape','outside']:
  nav.click()
  if close=='escape':page.keyboard.press('Escape')
  else:page.mouse.click(2,2)
  expect(page.locator('#review')).to_have_class('view active');expect(page.locator('#reviewBranchStatus')).to_contain_text('계산 중')
 b=chess.Board();b.push_uci('d2d4');b.push_uci('d7d5')
 page.evaluate('d=>window.releaseReviewEngine(d)',{'fen':b.fen(),'legal':[m.uci() for m in b.legal_moves],'terminal':False,'reply':'d7d5'})
 expect(page.locator('#reviewStep')).to_contain_text('분기 2')
 assert page.evaluate('v5Review')==original
 nav.click();page.locator('[data-academy="tactics"]').click();expect(page.locator('#learn')).to_have_class('view active')


@pytest.mark.parametrize('entry',['menu','hub'])
def test_rules_first_explicit_tactics_survives_delayed_foundations(page,site,entry):
 login(page,site);page.evaluate("api('/starting-level','POST',{choice:'rules',revision:0})")
 data=page.evaluate("api('/foundations')");assert data['rules_first']
 page.evaluate("""() => {const old=api;api=(path,...args)=>path==='/foundations'?new Promise(resolve=>window.releaseFoundations=resolve):old(path,...args);} """)
 if entry=='menu':
  page.locator('.nav [data-tab="learn"]').click();page.locator('[data-academy="tactics"]').click()
 else:
  page.evaluate("tab('learn')");page.locator('#learn-choice-tactics').click()
 expect(page.locator('#academyTactics')).to_have_attribute('open','')
 page.evaluate('data=>window.releaseFoundations(data)',data)
 expect(page.locator('#foundationStatus')).to_have_text(data['scope'])
 expect(page.locator('#academyTactics')).to_have_attribute('open','')
 expect(page.locator('#learning-location')).to_contain_text('전술 과목')


def test_challenge_review_last_selected_result_wins_reverse_response(page,site):
 login(page,site)
 state={'revision':0,'active':None,'history':[{'id':x,'score':n,'solved':0,'hinted_solved':0} for x,n in [('A',10),('B',20)]]}
 page.route('**/api/challenge',lambda r:r.fulfill(json=state))
 page.evaluate("tab('puzzle')");page.locator('#puzzleModeChallenge').click();expect(page.locator('#challengeHistory button')).to_have_count(2)
 page.evaluate("""() => {const old=api;window.reviewResolvers={};api=(path,...args)=>path.startsWith('/challenge/review/')?new Promise(resolve=>window.reviewResolvers[path.split('/').pop()]=resolve):old(path,...args);} """)
 page.locator('#challengeHistory button').nth(0).click();page.locator('#challengeHistory button').nth(1).click()
 def result(id):return {'id':id,'items':[{'correct':False,'points':0,'hinted':False,'reason':'결과 '+id,'submitted':[],'frames':[{'fen':'6k1/8/8/8/8/8/8/4K3 w - - 0 1','san':'fixture','solver':False}],'source':'UI fixture'}]}
 page.evaluate('d=>window.reviewResolvers.B(d)',result('B'));expect(page.locator('#challengeReview')).to_contain_text('결과 B')
 page.locator('#puzzleModeChallenge').focus();before=page.evaluate('scrollY')
 page.evaluate('d=>window.reviewResolvers.A(d)',result('A'));page.wait_for_timeout(100)
 expect(page.locator('#challengeReview')).to_contain_text('결과 B');expect(page.locator('#challengeReview')).not_to_contain_text('결과 A')
 expect(page.locator('#puzzleModeChallenge')).to_be_focused();assert page.evaluate('scrollY')==before
