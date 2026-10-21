from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import page,site

@pytest.mark.parametrize('width',[390,1280])
def test_guest_examples_are_ephemeral_and_do_not_write(page,site,width):
 context=page.context.browser.new_context(viewport={'width':width,'height':844})
 guest=context.new_page();writes=[]
 guest.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
 guest.goto(site[0]);guest.locator('#firstEntry').get_by_role('button',name='기초·예제 퍼즐도 저장 없이 체험').click()
 guest.get_by_role('button',name='비숍은 대각선으로',exact=True).click()
 guest.locator('#guestBoard [aria-label^="c1 "]').focus();guest.keyboard.press('Enter')
 expect(guest.locator('#guestBoard [aria-label^="c1 "]')).to_be_focused()
 guest.locator('#guestBoard [aria-label^="g5 "]').focus();guest.keyboard.press('Enter')
 expect(guest.locator('#guestOutcome')).to_contain_text('실습 목표 확인')
 guest.locator('#guestNext').click();guest.get_by_role('button',name='한 수 체크메이트 예제',exact=True).click()
 expect(guest.locator('#guestHint')).to_be_enabled();expect(guest.locator('#guestReason')).to_be_hidden()
 assert 'g6 → g7' not in guest.locator('#guestActivity').inner_text()
 guest.locator('#guestHint').click();expect(guest.locator('#guestOutcome')).to_contain_text('g6 → g7')
 guest.locator('#guestBoard [aria-label^="g6 "]').click();guest.locator('#guestBoard [aria-label^="g7 "]').click()
 expect(guest.locator('#guestOutcome')).to_contain_text('안내를 보고')
 board=guest.locator('#guestBoard').bounding_box()
 assert board['y']+board['height']<844
 assert writes==[]
 assert guest.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
 Path('docs/qa-focus-interface/captures').mkdir(parents=True,exist_ok=True)
 guest.wait_for_timeout(350) # Capture settled common piece animation; verdict assertions above remain immediate.
 guest.screenshot(path=f'docs/qa-focus-interface/captures/guest-{width}.png',full_page=True)
 guest.locator('#guestContinue').click();expect(guest.locator('#codeField')).to_be_visible()
 assert writes==[]
 guest.reload();assert guest.locator('#guestBoard .sq').count()==0
 guest.evaluate("tab('guestPractice')");expect(guest.locator('#guestChoices button')).to_have_count(3)
 guest.get_by_role('button',name='비숍은 대각선으로',exact=True).click()
 guest.reload();expect(guest.locator('#guestChoices button')).to_have_count(3)
 expect(guest.locator('#guestActivity')).to_be_hidden()
 assert writes==[]
 context.close()


def test_guest_load_failure_retry_and_late_exit_are_readonly(page,site):
 context=page.context.browser.new_context();p=context.new_page();writes=[]
 p.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
 p.route('**/assets/guest-examples.json',lambda r:r.fulfill(status=503,body='unavailable'))
 p.goto(site[0]);p.locator('#firstEntry').get_by_role('button',name='기초·예제 퍼즐도 저장 없이 체험').click()
 expect(p.locator('#guestRetry')).to_be_visible();expect(p.locator('#guestBoard .sq')).to_have_count(0)
 p.unroute('**/assets/guest-examples.json');pending=[]
 p.route('**/assets/guest-examples.json',lambda r:pending.append(r))
 p.locator('#guestRetry').click();expect(p.locator('#guestLoad')).to_contain_text('불러오는 중')
 for _ in range(100):
  if pending:break
  p.wait_for_timeout(10)
 assert len(pending)==1
 p.locator('#guestExit').click();pending[0].fulfill(path='public/guest-examples.json')
 expect(p.locator('#home')).to_have_class('view active')
 expect(p.locator('#guestBoard .sq')).to_have_count(0)
 p.unroute('**/assets/guest-examples.json')
 p.locator('#firstEntry').get_by_role('button',name='기초·예제 퍼즐도 저장 없이 체험').click()
 expect(p.locator('#guestChoices button')).to_have_count(3)
 p.get_by_role('button',name='비숍은 대각선으로',exact=True).click()
 p.go_back();expect(p.locator('#home')).to_have_class('view active')
 p.go_forward();expect(p.locator('#guestChoices button')).to_have_count(3)
 expect(p.locator('#guestActivity')).to_be_hidden();assert writes==[]
 context.close()
