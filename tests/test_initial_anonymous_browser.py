"""Fresh local browser identity, never the operating QA session."""
import pytest
from playwright.sync_api import expect
from test_redesign_browser_followup import isolated,site


@pytest.mark.parametrize('width,height',[(1366,768),(360,800)])
def test_anonymous_direct_entry_explicit_single_guest_and_resume(isolated,site,width,height):
    page,_=isolated;page.set_viewport_size({'width':width,'height':height})
    starts=[];diagnoses=[]
    page.on('request',lambda r:starts.append(1) if r.method=='POST' and r.url.endswith('/api/guest/start') else diagnoses.append(1) if r.method=='POST' and r.url.endswith('/api/journey/start') else None)
    page.goto(site[0]+'/#diagnosis/initial')
    expect(page.locator('#initialProfile')).to_contain_text('48개 유효 관찰')
    expect(page.locator('#initialProfile')).to_contain_text('계정 연결은 선택')
    expect(page.locator('#initialProfile').get_by_role('button',name='로그인 없이 초기 진단 시작')).to_be_visible()
    assert not starts and not diagnoses
    page.screenshot(path=f'/tmp/initial-anonymous-{width}.png',full_page=True)
    assert page.evaluate("!token && !localStorage.getItem('cma_guest_token')")
    page.locator('#initialProfile').get_by_role('button',name='로그인 없이 초기 진단 시작').dblclick()
    expect(page.locator('#initialProfile > button').first).to_have_text('진단 이어하기 · 남은 분야 바로 풀기',timeout=20000)
    expect(page).to_have_url(site[0]+'/#diagnosis/initial')
    assert len(starts)==1 and not diagnoses
    page.evaluate('window.beforeIdentity=token')
    page.locator('#initialProfile > button').click();expect(page.locator('#journeyTask')).to_be_visible(timeout=20000)
    assert len(diagnoses)==1
    page.evaluate("sessionStorage.setItem('testOriginalIdentity',token)")
    page.reload();expect(page.locator('#journeyTask')).to_be_visible()
    assert page.evaluate("token===sessionStorage.getItem('testOriginalIdentity')")
    assert len(starts)==1 and len(diagnoses)==1
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')


def test_general_choice_exposes_initial_and_optional_login_without_creation(isolated,site):
    page,_=isolated;posts=[];page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
    page.goto(site[0]+'/#diagnosis')
    expect(page.locator('#initialProfile')).to_be_visible()
    expect(page.locator('#diagnosticBlueprint')).to_be_visible()
    expect(page.locator('#initialProfile').get_by_role('button',name='로그인 없이 초기 진단 시작')).to_be_visible()
    page.locator('#initialProfile').get_by_role('button',name='기존 계정으로 로그인 · 선택').click()
    expect(page).to_have_url(site[0]+'/#profile/account')
    assert page.evaluate("loginDestination==='diagnosis/initial'")
    assert not posts and page.evaluate('!token')


def test_guest_creation_error_is_visible_and_no_record_is_claimed(isolated,site):
    page,_=isolated;page.goto(site[0]+'/#diagnosis/initial')
    page.route('**/api/guest/start',lambda r:r.fulfill(status=503,json={'detail':'테스트 생성 미실행'}))
    page.locator('#initialProfile').get_by_role('button',name='로그인 없이 초기 진단 시작').click()
    expect(page.locator('#initialGuestStatus')).to_contain_text('테스트 생성 미실행')
    assert page.evaluate("!token && !localStorage.getItem('cma_guest_token')")
    expect(page.locator('#initialProfile').get_by_role('button',name='로그인 없이 초기 진단 시작')).to_be_enabled()
