"""Local Chromium emulation; no production browser or real-device claim."""
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright, expect
from test_qa_browser import site
from test_journey_browser import question

@pytest.mark.parametrize('width',[320,360,390,430,768,900,1024,1280])
def test_responsive_boards_long_copy_and_last_result(site,width):
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':width,'height':900},is_mobile=width<768,has_touch=width<768)
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.add_init_script("localStorage.setItem('chess_token',"+repr(site[1])+");")
        task=question();task['question']['goal']='상대 응수를 확인하고 이어서 직접 두세요. '+('d7d8n-e8f7-'*12)
        task['question']['label']='메이트 수순 · 한국어 설명과 긴 날짜 2026-10-19T23:59:59.999999+00:00'
        page.route('**/api/onboarding',lambda r:r.fulfill(json={'status':'completed','version':1}))
        page.route('**/api/journey',lambda r:r.fulfill(json={'active':task,'latest':None,'results':[],'competencies':[]}))
        page.goto(site[0]);page.evaluate("tab('diagnosis')")
        try:expect(page.locator('#journeyBoard .sq')).to_have_count(64)
        except AssertionError as error:
            page.screenshot(path=f'/tmp/cma-responsive-failure-{width}.png',full_page=True)
            message=page.locator('#journeyMessage').text_content()
            raise AssertionError(f'{error}; journey status={message}; page errors={errors}') from error
        expect(page.locator('#journeyBoard [aria-label^="e3 "]')).to_have_attribute('aria-label','e3 흑 룩')
        for view in ['diagnosis','profile','help']:
            page.evaluate('tab('+repr(view)+')');page.wait_for_timeout(100)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),(width,view,page.evaluate('document.documentElement.scrollWidth'))
        page.evaluate("tab('diagnosis')")
        directory=Path(__file__).resolve().parents[1]/'docs/qa-responsive';directory.mkdir(exist_ok=True)
        page.screenshot(path=str(directory/f'diagnosis-{width}.png'),full_page=True)
        page.locator('#journeyBoard [aria-label^="e3 "]').focus()
        assert page.locator('#journeyBoard [aria-label^="e3 "]').evaluate("e=>getComputedStyle(e).outlineStyle")!='none'
        # Final feedback exposes a clear result action, not another-question wording.
        task.update(index=1,phase='feedback',feedback={'submitted':['e3h3'],'expected':['e3h3'],'correct_plies':1,'total_plies':1})
        page.locator('#journeyRefresh').click();expect(page.locator('#journeyNext')).to_have_text('결과 보기')
        page.evaluate("tab('training')")
        page.locator('#learningFresh').click()
        expect(page.locator('#learningBoard .sq')).to_have_count(64)
        expect(page.locator('#learningFresh')).to_be_enabled()
        page.evaluate("document.getElementById('learningExplanation').textContent='긴 수순 '+'Nxf7+ d8=Q# '.repeat(20);document.getElementById('userBadge').textContent='QA20261019ABCDEFGHIJKLMNOP';")
        page.locator('#learningDetails').evaluate('e=>e.open=true')
        expected='긴 수순 '+('Nxf7+ d8=Q# '*20)
        actual=page.locator('#learningExplanation').text_content()
        assert actual==expected and len(actual)==len(expected) and 'NaN' not in actual
        expect(page.locator('#learningExplanation')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        page.screenshot(path=str(directory/f'training-{width}.png'),full_page=True)
        if width in (900,1024):
            assert page.locator('#learningDetails').bounding_box()['width']>=300
        browser.close()


def test_reset_failure_recovers_button_and_cancel_sends_nothing(site):
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page();page.add_init_script("localStorage.setItem('chess_token',"+repr(site[1])+");")
        page.route('**/api/onboarding',lambda r:r.fulfill(json={'status':'completed','version':1}))
        requests=[]
        def fail(route):
            requests.append(route.request.post_data_json)
            route.fulfill(status=503,json={'detail':'기록 저장소가 지연되고 있습니다.'})
        page.route('**/api/profile/reset',fail)
        page.goto(site[0]);page.evaluate("tab('profile/data')")
        page.locator('#resetPinV5').fill('fake-test-only');page.locator('#resetConfirmV5').fill(' 초기화 ')
        page.once('dialog',lambda d:d.dismiss());page.locator('#resetProfileV5').click()
        expect(page.locator('#resetStatusV5')).to_contain_text('취소');assert not requests
        page.once('dialog',lambda d:d.accept());page.locator('#resetProfileV5').click()
        expect(page.locator('#resetStatusV5')).to_contain_text('완료는 확인되지 않았습니다')
        expect(page.locator('#resetProfileV5')).to_be_enabled()
        assert requests[0]['confirmation']=='초기화' and requests[0]['revision']==0
        browser.close()
