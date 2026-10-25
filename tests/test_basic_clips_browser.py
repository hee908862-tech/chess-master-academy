"""Real local API/Chromium; viewport emulation, not physical Kakao WebView."""
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_redesign_browser_followup import isolated, site
from test_movement_browser import enter, ready


def choose(page,unit):
    page.evaluate("async id=>{const d=await api('/movement');await api('/movement/start','POST',{action:'start',unit_id:id,revision:d.revision,request_id:crypto.randomUUID()});await cmaMovement.load();}",unit)
    ready(page)


@pytest.mark.parametrize('width,height',[(1366,768),(360,640),(390,844),(844,390)])
def test_reported_clips_controls_layout_and_practice_separation(isolated,site,width,height):
    page,_=isolated;page.set_viewport_size(dict(width=width,height=height));enter(page)
    for unit in ['rules-pawn-promotion','rules-shield-piece','rules-make-stalemate']:
        choose(page,unit)
        before=page.evaluate('cmaMovement.state().moves')
        page.get_by_role('button',name='짧은 시연 · 정답 도움',exact=True).click()
        expect(page.locator('#movementClip')).to_be_visible()
        assert page.evaluate('cmaMovement.state().clipIndex')==0
        assert not page.evaluate('cmaMovement.state().clipPlaying')
        page.locator('#movementClip').get_by_role('button',name='재생',exact=True).click()
        page.wait_for_function('cmaMovement.state().clipIndex>0')
        page.locator('#movementClip').get_by_role('button',name='멈춤',exact=True).click()
        index=page.evaluate('cmaMovement.state().clipIndex');page.wait_for_timeout(1750)
        assert page.evaluate('cmaMovement.state().clipIndex')==index
        page.locator('#movementClip').get_by_role('button',name='처음부터',exact=True).click()
        while not page.locator('#movementClip').get_by_role('button',name='다음 수',exact=True).is_disabled():
            page.locator('#movementClip').get_by_role('button',name='다음 수',exact=True).click()
        assert page.evaluate('cmaMovement.state().moves')==before
        assert not page.evaluate('cmaMovement.state().done')
        assert page.evaluate('cmaMovement.state().unit.helped')
        page.locator('#movementClip').scroll_into_view_if_needed()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        if width<=850:
            assert page.locator('.mobile-nav').evaluate("e=>getComputedStyle(e).position")=='static'
        output=Path('/tmp/basic-clips-qa');output.mkdir(exist_ok=True)
        page.screenshot(path=str(output/f'{unit}-{width}x{height}.png'),full_page=True)
        page.locator('#movementClip').get_by_role('button',name='이전 수',exact=True).click()
        page.locator('#movementClip').get_by_role('button',name='닫고 직접 연습',exact=True).click()
        expect(page.locator('#movementClip')).to_be_hidden()
        assert page.evaluate('cmaMovement.state().moves')==before
    # Prior lesson preview must not replace the current session.
    session=page.evaluate('cmaMovement.state().unit.session_id')
    page.get_by_role('button',name='직전 문제 시연',exact=True).click()
    expect(page.locator('#movementClip')).to_be_visible()
    assert page.evaluate('cmaMovement.state().unit.session_id')==session
    page.locator('#movementClip').get_by_role('button',name='재생',exact=True).click()
    page.evaluate("cmaNavigation.go('home')")
    page.wait_for_timeout(1800)
    assert page.evaluate('cmaMovement.state().clip') is None
    page.evaluate("cmaNavigation.go('learn/movement')")
    ready(page)
    assert page.evaluate('cmaMovement.state().unit.session_id')==session


def test_completion_stays_and_demo_retry_and_duplicate_clicks(isolated,site):
    page,_=isolated;enter(page);choose(page,'rules-shield-piece')
    page.locator('#movementBoard [aria-label^="d2 "]').click()
    page.locator('#movementBoard [aria-label^="d4 "]').click()
    page.wait_for_function('cmaMovement.state().done && !cmaMovement.state().pending')
    page.wait_for_timeout(2800)
    assert page.evaluate('cmaMovement.state().unit.unit_id')=='rules-shield-piece'
    page.get_by_role('button',name='짧은 시연 · 정답 도움',exact=True).evaluate('(b)=>{b.click();b.click();}')
    expect(page.locator('#movementClip')).to_be_visible()
    page.locator('#movementClip').get_by_role('button',name='닫고 직접 연습',exact=True).click()
    page.get_by_role('button',name='같은 문제 직접 다시',exact=True).click()
    page.wait_for_function('!cmaMovement.state().done && cmaMovement.state().moves.length===0')
    assert page.evaluate('cmaMovement.state().unit.helped')


def test_hidden_tab_pauses_and_browser_back_cancels(isolated,site):
    page,_=isolated;enter(page);choose(page,'rules-pawn-promotion')
    page.get_by_role('button',name='짧은 시연 · 정답 도움',exact=True).click()
    page.locator('#movementClip').get_by_role('button',name='재생',exact=True).click()
    page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'))")
    assert not page.evaluate('cmaMovement.state().clipPlaying')
    page.evaluate("delete document.hidden;document.dispatchEvent(new Event('visibilitychange'))")
    assert not page.evaluate('cmaMovement.state().clipPlaying')
    page.locator('#movementClip').get_by_role('button',name='재생',exact=True).click()
    page.go_back()
    page.wait_for_function("cmaNavigation.current()!=='learn/movement'")
    assert page.evaluate('cmaMovement.state().clip') is None
    page.go_forward();ready(page)
    assert page.evaluate('cmaMovement.state().moves')==[]
    assert page.evaluate('cmaMovement.state().unit.helped')
