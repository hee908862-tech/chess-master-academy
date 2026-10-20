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
