import json,secrets
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import page,site,open_page

def foundation(page,site):
 open_page(page,site)
 page.evaluate("async code=>{const r=await api('/register','POST',{code,pin:'focus-test-123'});token=r.token;localStorage.setItem('chess_token',token);await cmaFoundations.load();const d=await api('/foundations');await api('/foundations/action','POST',{action:'start',course_id:'rook-bishop',revision:d.revision,step:0,value:''});await cmaFoundations.load();tab('learn/basics/practice');}",'FOCUS-'+secrets.token_hex(5))
 expect(page.locator('body')).to_have_class(__import__('re').compile('focus-foundation'))

@pytest.mark.parametrize('size',[(360,800),(390,844),(1280,720),(1366,768),(320,650),(844,390)])
def test_foundation_focused_bounds_and_readonly_details(page,site,size):
 page.set_viewport_size({'width':size[0],'height':size[1]});foundation(page,site)
 before=page.evaluate("api('/foundations')");writes=[]
 page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
 detail=page.locator('#foundationExplanation');detail.locator('summary').first.click()
 expect(page.locator('#foundationFeedback')).to_be_visible()
 detail.press('Escape');expect(detail).not_to_have_attribute('open','')
 expect(detail.locator('summary').first).to_be_focused()
 assert writes==[];assert page.evaluate("api('/foundations')")==before
 board=page.locator('#foundationBoard').bounding_box();status=page.locator('#foundationLive').bounding_box()
 assert board['width']>=280 and page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
 if size in [(360,800),(390,844),(1280,720),(1366,768)]:
  assert board['y']+board['height']<=size[1]
  assert status['y']+status['height']<=size[1]
 page.locator('#foundationBoard [aria-label^="a1 "]').click();page.locator('#foundationBoard [aria-label^="a4 "]').click()
 expect(page.locator('#foundationOutcome')).to_contain_text('단계 완료')
 expect(page.locator('#foundationNext')).to_contain_text('다음 단계')
 if size[1]>=720:assert page.locator('#foundationNext').bounding_box()['y']<size[1]-44
 Path('docs/qa-focus-interface/captures').mkdir(parents=True,exist_ok=True)
 page.wait_for_timeout(350) # Only settle animation for the evidence image.
 page.screenshot(path=f'docs/qa-focus-interface/captures/foundation-{size[0]}-{size[1]}.png',full_page=True)
