"""New curriculum resume recommendations and legacy preference, local synthetic guest."""
import pytest
from playwright.sync_api import expect
from test_redesign_browser_followup import isolated,site
from test_movement_browser import enter,ready,square

@pytest.mark.parametrize('width,height',[(1366,768),(390,844)])
def test_new_progress_home_profile_resume_no_restarts(isolated,site,width,height):
    page,_=isolated;page.set_viewport_size(dict(width=width,height=height));enter(page)
    square(page,'b2').click();square(page,'b5').click()
    page.wait_for_function('cmaMovement.state().data.active.moves.length===1 && !cmaMovement.state().pending')
    saved=page.evaluate("api('/movement')")
    page.evaluate("cmaNavigation.go('home')")
    expect(page.locator('#homeNextAction > button')).to_have_text('기초 이어하기')
    expect(page.locator('#homeNextAction')).to_contain_text('기초 직접 연습')
    page.reload();expect(page.locator('#homeNextAction > button')).to_have_text('기초 이어하기')
    writes=[];page.on('request',lambda r:writes.append(r.url) if '/movement/' in r.url and r.method=='POST' else None)
    page.locator('#homeNextAction > button').click();ready(page)
    assert page.evaluate("api('/movement')")==saved and not writes
    assert page.evaluate('cmaMovement.state().source')=='b5'
    page.evaluate("cmaNavigation.go('profile')")
    expect(page.locator('#profileNextAction > button')).to_have_text('기초 이어하기')
    # An explicit old-course selection changes the resume preference, not old/new records.
    page.evaluate("cmaNavigation.go('learn/basics')")
    page.locator('#foundationCourseList').evaluate('e=>e.open=true')
    page.locator('#foundation-open-king-check').click()
    page.wait_for_function('!!cmaFoundations.state()?.active && !cmaFoundations.status().busy')
    legacy=page.evaluate("api('/foundations')")['active']
    page.evaluate("cmaNavigation.go('home')");page.reload()
    page.locator('#homeNextAction > button').click()
    expect(page.locator('#foundationWorkspace')).to_be_visible()
    assert page.evaluate("api('/foundations')")['active']==legacy
    assert page.evaluate("api('/movement')")['active']==saved['active']
