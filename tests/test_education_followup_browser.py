import secrets
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page
from test_education_browser import enter,start,ready

@pytest.mark.parametrize('switch',[True,False])
def test_old_history_failure_does_not_change_new_screen(page,site,switch):
 enter(page,site);start(page)
 page.get_by_role('button',name='현재 시도 기록하고 마치기',exact=True).click();ready(page)
 page.locator('#educationBody summary').filter(has_text='보관한 교육 결과').click()
 page.evaluate("""()=>{window.baseEduApi=api;window.rejectHistory=null;api=async(...args)=>args[0].startsWith('/education/history/')?new Promise((resolve,reject)=>rejectHistory=()=>reject(new Error('OLD HISTORY FAILURE'))):baseEduApi(...args);}""")
 page.get_by_role('button',name='이 기록의 관찰·이유 보기',exact=True).click();page.wait_for_function('rejectHistory!==null')
 if switch:
  page.evaluate("async code=>{const r=await baseEduApi('/register','POST',{code,pin:'temporary-history-pin'});token=r.token;tab('learn');}",'EDUERR-'+secrets.token_hex(4));ready(page)
 else:page.evaluate("tab('home')")
 before=page.locator('#educationStatus').text_content();page.evaluate('rejectHistory()');page.wait_for_timeout(100)
 assert page.locator('#educationStatus').text_content()==before


def test_prior_context_in_review_has_two_marked_squares_not_answer(page,site):
 enter(page,site);start(page)
 expect(page.locator('#educationBody')).to_contain_text('상대 직전 수: f8 → b4 (Bb4)')
 expect(page.locator('#educationBoard .opponent-move')).to_have_count(2)
 assert 'opponent-move' in page.locator('#educationBoard [aria-label^="f8 "]').get_attribute('class').split()
 assert '상대 직전 수' in page.locator('#educationBoard [aria-label^="b4 "]').get_attribute('aria-label')
 assert '상대 직전 수' not in page.locator('#educationBoard [aria-label^="c3 "]').get_attribute('aria-label')
 assert page.get_by_role('button',name='수업 예시 c3a2').count()==0
 from pathlib import Path
 Path('docs/qa-education').mkdir(exist_ok=True,parents=True)
 page.locator('#educationPaths').screenshot(path='docs/qa-education/prior-context-review.png')
