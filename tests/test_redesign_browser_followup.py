"""Isolated local Chromium/API checks; mobile sizes are emulation, not devices."""
import secrets
import pytest
from playwright.sync_api import sync_playwright, expect
from test_qa_browser import site

@pytest.fixture
def isolated(site):
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        context=browser.new_context()
        page=context.new_page();page.set_default_timeout(10000)
        page.goto(site[0])
        yield page,context
        browser.close()

@pytest.mark.parametrize('width,height',[(1366,768),(360,800),(390,844)])
def test_guest_link_logout_reload_owner_resume(isolated,site,width,height):
    page,context=isolated;page.set_viewport_size(dict(width=width,height=height))
    page.locator('#flowBasicsStart').click()
    expect(page.locator('#learn')).to_have_class(__import__('re').compile(r'\bactive\b'))
    page.wait_for_function("token && localStorage.getItem('cma_guest_token')===token")
    expect(page.locator('#foundationWorkspace')).to_be_visible(timeout=20000)
    before=page.evaluate("api('/foundations')")
    guest=page.evaluate('token')
    other=context.new_page();other.goto(site[0]);other.wait_for_function('!!token')
    page.evaluate("cmaNavigation.go('profile/account')")
    page.get_by_role('button',name='계정 전환',exact=True).click()
    code='BROWSER-'+secrets.token_hex(5);pin=secrets.token_urlsafe(16)
    page.locator('#codeField').fill(code);page.locator('#pinField').fill(pin);page.locator('#signup').click()
    page.wait_for_function("localStorage.getItem('chess_token')===token && localStorage.getItem('cma_identity')==='account'")
    expect(page.locator('#home')).to_have_class(__import__('re').compile(r'\bactive\b'))
    account_before=page.evaluate("api('/foundations')")
    page.evaluate("cmaNavigation.go('profile/account')")
    page.get_by_role('button',name='이 브라우저의 게스트 기록을 계정에 별도 연결',exact=True).click()
    page.wait_for_function("!localStorage.getItem('cma_guest_token')")
    other.wait_for_function("token===''")
    assert context.request.get(site[0]+'/api/foundations',headers={'Authorization':'Bearer '+guest}).status==401
    resume=page.locator('#guestAccountAccess').get_by_role('button',name=__import__('re').compile('이어하기$'))
    resume.click();page.wait_for_function("localStorage.getItem('cma_identity')==='linked'")
    assert page.evaluate("api('/foundations')")==before
    delegated=page.evaluate('token')
    other.reload();other.wait_for_function("localStorage.getItem('cma_linked_token')===token")
    page.evaluate("cmaNavigation.go('profile/account')");page.locator('#signout').click()
    page.wait_for_function("token===''");other.wait_for_function("token===''")
    page.reload();page.wait_for_function("token===''")
    assert context.request.get(site[0]+'/api/foundations',headers={'Authorization':'Bearer '+delegated}).status==401
    page.evaluate("cmaNavigation.go('profile/account')")
    page.locator('#codeField').fill(code);page.locator('#pinField').fill(pin);page.locator('#signin').click()
    page.wait_for_function("localStorage.getItem('chess_token')===token && !!token")
    expect(page.locator('#home')).to_have_class(__import__('re').compile(r'\bactive\b'))
    assert page.evaluate("api('/foundations')")==account_before
    page.evaluate("cmaNavigation.go('profile/account')");resume.click()
    page.wait_for_function("localStorage.getItem('cma_identity')==='linked'")
    assert page.evaluate("api('/foundations')")==before
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')

@pytest.mark.parametrize('width,height',[(1366,768),(360,800),(390,844)])
def test_en_passant_demo_readonly_and_selection(isolated,site,width,height):
    page,_=isolated;page.set_viewport_size(dict(width=width,height=height))
    page.locator('#flowBasicsStart').click()
    expect(page.locator('#learn')).to_have_class(__import__('re').compile(r'\bactive\b'))
    page.wait_for_function('!!token')
    page.evaluate("cmaNavigation.go('learn/basics')")
    if not page.locator('#foundationCourseList').evaluate('(e)=>e.open'):page.locator('#foundationCourseList > summary').click()
    page.locator('#foundation-open-en-passant').click()
    expect(page.locator('#foundationDemoStart')).to_be_visible()
    before=page.evaluate("api('/foundations')")
    writes=[];page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
    page.locator('#foundationDemoStart').click()
    expect(page.locator('#foundationBoard [aria-label^="d7 흑 폰"]')).to_have_count(1)
    expect(page.locator('#foundationBoard [aria-label^="d5 흑 폰"]')).to_have_count(1)
    expect(page.locator('#foundationDemoStart')).to_be_visible()
    pawn=page.locator('#foundationBoard [aria-label^="e5 백 폰"]')
    pawn.click();expect(page.locator('#foundationBoard .selected')).to_have_count(1)
    pawn.click();expect(page.locator('#foundationBoard .selected')).to_have_count(0)
    assert page.evaluate("api('/foundations')")==before and writes==[]
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')

from test_qa_browser import page, TASK, open_page, square

def drag(page,source,target):
    source.scroll_into_view_if_needed()
    a=source.bounding_box();b=target.bounding_box()
    page.mouse.move(a['x']+a['width']/2,a['y']+a['height']/2);page.mouse.down()
    page.mouse.move(b['x']+b['width']/2,b['y']+b['height']/2,steps=12);page.mouse.up()

@pytest.mark.parametrize('width,height',[(1366,768),(360,800),(390,844)])
def test_drag_promotion_cancel_and_delayed_reply(page,site,width,height):
    page.set_viewport_size(dict(width=width,height=height))
    page.route('**/api/v9/course/start',lambda r:r.fulfill(json=TASK))
    requests=[];page.route('**/api/v9/course/move',lambda r:requests.append(r))
    open_page(page,site);page.evaluate("tab('learn');cmaOpenV9Course('quietMove')")
    page.locator('#v9CourseStart').click()
    source=square(page,'v9CourseBoard','d7');target=square(page,'v9CourseBoard','d8')
    drag(page,source,target)
    expect(page.locator('#cmaPromotionModal')).to_be_visible()
    page.keyboard.press('Escape')
    expect(page.locator('.drag-ghost')).to_have_count(0)
    assert not requests
    drag(page,source,target)
    page.locator('#cmaPromotionModal').get_by_role('button',name=__import__('re').compile('룩')).click()
    for _ in range(50):
        if requests:break
        page.wait_for_timeout(20)
    assert len(requests)==1 and requests[0].request.post_data_json['move']=='d7d8r'
    page.wait_for_timeout(300)
    assert len(requests)==1
    requests[0].fulfill(json=dict(correct=True,solved=True,done=True,completed_fen=TASK['fen'].replace('6k1/3P1pp1','3R2k1/5pp1'),reply=None,message='완료',correct_count=15,total=15,mastered=True))
    expect(page.locator('#v9CourseMessage')).to_contain_text('15/15')
    expect(page.locator('.drag-ghost')).to_have_count(0)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')

@pytest.mark.parametrize('width,height',[(1366,768),(360,800),(390,844)])
def test_scoped_result_reasons_and_buttons_fit(isolated,site,width,height):
    page,_=isolated;page.set_viewport_size(dict(width=width,height=height))
    page.locator('#flowActivityChoices > summary').click()
    page.locator('#guestAccess').get_by_role('button',name='실력 진단',exact=True).click()
    expect(page.locator('#diagnosis')).to_have_class(__import__('re').compile(r'\bactive\b'))
    report=page.evaluate("""async()=>{let s=await api('/journey/start','POST',{mode:'domain',competency:'mate'});while(s.phase!=='complete')s=await api('/journey/action','POST',{session_id:s.session_id,revision:s.revision,action:s.phase==='question'?'skip':'next'});return s.report;}""")
    assert report['diagnostic_scope']['level']=='domain' and 'internal_skill' not in report
    page.reload();page.evaluate("tab('diagnosis')")
    expect(page.locator('#journeyResults')).to_contain_text('미응답')
    assert page.locator('#journeyResults').inner_text().strip()
    for button in page.locator('#journeyResults button').all():
        if button.is_visible():
            button.scroll_into_view_if_needed();box=button.bounding_box()
            assert box['x']>=-1 and box['x']+box['width']<=width+1
            assert button.evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')

@pytest.mark.parametrize('width,height',[(1366,768),(360,800),(390,844)])
def test_diagnosis_repeat_selection_preserves_session(isolated,site,width,height):
    page,_=isolated;page.set_viewport_size(dict(width=width,height=height))
    page.locator('#flowActivityChoices > summary').click()
    page.locator('#guestAccess').get_by_role('button',name='실력 진단',exact=True).click()
    expect(page.locator('#diagnosis')).to_have_class(__import__('re').compile(r'\bactive\b'))
    active=page.evaluate("api('/journey/start','POST',{mode:'quick'})")
    page.reload();page.evaluate("tab('diagnosis')")
    before=page.evaluate("api('/journey')")
    cell=square(page,'journeyBoard',active['question']['legal'][0][:2])
    writes=[];page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
    cell.click();expect(page.locator('#journeyBoard .selected')).to_have_count(1)
    cell.click();expect(page.locator('#journeyBoard .selected')).to_have_count(0)
    assert page.evaluate("api('/journey')")==before and not writes
