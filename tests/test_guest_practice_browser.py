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
 guest.locator('#guestBoard [aria-label^="c1 "]').click();guest.locator('#guestBoard [aria-label^="g5 "]').click()
 expect(guest.locator('#guestOutcome')).to_contain_text('실습 목표 확인')
 guest.locator('#guestNext').click();guest.get_by_role('button',name='한 수 체크메이트 예제',exact=True).click()
 expect(guest.locator('#guestHint')).to_be_enabled();expect(guest.locator('#guestReason')).to_be_hidden()
 assert 'g6 → g7' not in guest.locator('#guestActivity').inner_text()
 guest.locator('#guestHint').click();expect(guest.locator('#guestOutcome')).to_contain_text('g6 → g7')
 guest.locator('#guestBoard [aria-label^="g6 "]').click();guest.locator('#guestBoard [aria-label^="g7 "]').click()
 expect(guest.locator('#guestOutcome')).to_contain_text('안내를 보고')
 assert writes==[]
 assert guest.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
 Path('docs/qa-focus-interface/captures').mkdir(parents=True,exist_ok=True)
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
