"""Local Chromium keyboard/zoom and controlled start failure, not physical devices."""
from playwright.sync_api import expect
from test_redesign_browser_followup import isolated,site
from test_visual_evidence_browser import guest


def test_keyboard_rotation_zoom_and_history_keep_active_session(isolated):
    page,_=isolated;page.set_viewport_size({'width':360,'height':800});guest(page)
    page.evaluate("cmaNavigation.go('diagnosis/initial')")
    main=page.locator('#initialProfile > button');main.focus();main.press('Enter')
    expect(page.locator('#journeyTask')).to_be_visible(timeout=20000)
    session=page.evaluate('cmaJourney.state().active.session_id')
    page.locator('#journeySkip').focus();page.locator('#journeySkip').press('Enter')
    expect(page.locator('#journeyNext')).to_be_visible()
    page.locator('#journeyPause').focus();page.locator('#journeyPause').press('Enter')
    expect(page.locator('#homeNextAction > button')).to_have_text('진단 이어하기')
    page.go_back();expect(page.locator('#journeyNext')).to_be_visible()
    assert page.evaluate('cmaJourney.state().active.session_id')==session
    page.set_viewport_size({'width':844,'height':390})
    page.evaluate("document.documentElement.style.zoom='200%'")
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    page.locator('#journeyNext').scroll_into_view_if_needed();expect(page.locator('#journeyNext')).to_be_enabled()


def test_double_start_and_controlled_error_never_claim_completion(isolated):
    page,_=isolated;guest(page);page.evaluate("cmaNavigation.go('diagnosis/initial')")
    pending=[]
    page.route('**/api/journey/start',lambda r:pending.append(r))
    main=page.locator('#initialProfile > button');main.dblclick()
    page.wait_for_timeout(300);assert len(pending)==1
    assert page.evaluate('cmaJourney.state().initial_profile.assigned')==0
    pending[0].fulfill(status=503,json={'detail':'테스트 응답 지연 · 저장하지 않음'})
    expect(page.locator('#journeyMessage')).to_contain_text('테스트 응답 지연')
    expect(page.locator('#initialProfile')).to_contain_text('필수 잔여 48문항')
    assert page.evaluate('cmaJourney.state().active') is None
    page.unroute('**/api/journey/start')
    page.get_by_role('button',name='저장 상태 확인',exact=True).click()
    expect(page.locator('#journeyMessage')).to_contain_text('확인')
    assert page.evaluate('cmaJourney.state().initial_profile.assigned')==0
