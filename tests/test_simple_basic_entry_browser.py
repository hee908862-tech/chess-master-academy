"""Intentional lesson entry, minimal actions and board-local practice results."""
import json
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_redesign_browser_followup import isolated,site
from test_movement_browser import enter,ready


def pick(page,unit):
    help=page.locator('#movementHelp')
    if not help.evaluate('(e)=>e.open'):help.locator('summary').click()
    page.locator('#movementUnit').select_option(unit)
    page.get_by_role('button',name='고른 연습 열기',exact=True).click()
    expect(page.locator('#movementExampleDialog')).to_be_visible()
    page.wait_for_function('!cmaMovement.state().loading && !cmaMovement.state().pending')


def skip(page):
    page.locator('#movementExampleActions button').click()
    expect(page.locator('#movementExampleDialog')).not_to_be_visible()


def practice(page):
    if page.evaluate("cmaMovement.state().unit.teaching?.phase==='guided'"):
        help=page.locator('#movementHelp')
        if not help.evaluate('(e)=>e.open'):help.locator('summary').click()
        page.get_by_role('button',name='따라 하기 건너뛰기',exact=True).click()
        page.wait_for_function("cmaMovement.state().unit.teaching.phase==='independent'")


@pytest.mark.parametrize('width,height',[(320,650),(390,844),(844,390),(1366,768)])
def test_entry_primary_controls_and_resume_loop_protection(isolated,site,width,height):
    page,_=isolated;page.set_viewport_size({'width':width,'height':height});enter(page)
    expect(page.locator('#movementExampleDialog')).not_to_be_visible() # Simple rook motion has no example.
    pick(page,'rules-shield-piece')
    dialog=page.locator('#movementExampleDialog');expect(dialog).to_be_visible()
    assert page.evaluate('cmaMovement.state().clipPlaying')
    assert dialog.locator('button:visible:not(.sq)').count()==3 # close/skip, pause, one primary
    primary=page.locator('#movementExampleActions button')
    assert primary.evaluate('(b)=>{const r=b.getBoundingClientRect();return r.height>=44 && b.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}')
    assert dialog.evaluate('(d)=>d.scrollWidth<=d.clientWidth+1')
    output=Path('/tmp/simple-basic-qa');output.mkdir(exist_ok=True)
    page.screenshot(path=str(output/f'popup-{width}.png'),full_page=False)
    page.keyboard.press('Escape')
    expect(dialog).not_to_be_visible()
    page.wait_for_function("cmaMovement.state().unit.teaching.phase==='guided'")
    before=page.evaluate('cmaMovement.state().unit.session_id')
    page.locator('#movementBoard [aria-label^="d2 "]').click();page.locator('#movementBoard [aria-label^="d4 "]').click()
    page.wait_for_function("cmaMovement.state().unit.teaching.phase==='independent' && !cmaMovement.state().pending")
    assert page.evaluate('cmaMovement.state().moves')==[]
    assert not page.evaluate('cmaMovement.state().done')
    expect(page.locator('#movementOutcome')).to_have_count(0)
    expect(dialog).not_to_be_visible()
    page.locator('#movementBoard [aria-label^="d2 "]').click();page.locator('#movementBoard [aria-label^="d4 "]').click()
    expect(page.locator('#movementOutcome')).to_contain_text('O')
    expect(page.locator('#movementOutcome')).to_contain_text('정답')
    page.wait_for_function('cmaMovement.state().data.active.done && !cmaMovement.state().pending')
    expect(page.locator('#movementActions')).to_contain_text('다음')
    assert page.locator('#movementActions button').count()==1
    page.screenshot(path=str(output/f'correct-{width}.png'),full_page=False)
    page.wait_for_timeout(1900);expect(dialog).not_to_be_visible()
    assert page.evaluate('cmaMovement.state().unit.session_id')==before
    # A real leave/return is a new introduction, even after completion.
    page.evaluate("cmaNavigation.go('home')")
    page.evaluate('cmaMovement.enter()')
    expect(dialog).to_be_visible()
    saved=page.evaluate('cmaMovement.state().data.summary.completed')
    skip(page)
    assert page.evaluate('cmaMovement.state().done')
    assert page.evaluate('cmaMovement.state().data.summary.completed')==saved


def test_wrong_move_retry_preserves_history_and_initial_practice_phase(isolated,site):
    page,_=isolated;page.set_viewport_size({'width':390,'height':844});enter(page);pick(page,'rules-shield-piece');skip(page);practice(page)
    original=page.evaluate("async()=>({me:await api('/me'),journey:await api('/journey')})")
    session=page.evaluate('cmaMovement.state().unit.session_id')
    page.locator('#movementBoard [aria-label^="d2 "]').click();page.locator('#movementBoard [aria-label^="d3 "]').click()
    expect(page.locator('#movementOutcome')).to_contain_text('X')
    output=Path('/tmp/simple-basic-qa');output.mkdir(exist_ok=True)
    page.wait_for_function('!cmaMovement.state().pending && cmaMovement.state().data.active.moves.length===1')
    page.screenshot(path=str(output/'incorrect-390.png'),full_page=False)
    page.get_by_role('button',name='다시하기',exact=True).evaluate('(b)=>{b.click();b.click()}')
    page.wait_for_function('(old)=>cmaMovement.state().unit.session_id!==old && !cmaMovement.state().pending',arg=session)
    assert page.evaluate('cmaMovement.state().unit.run')==1
    assert page.evaluate('cmaMovement.state().unit.teaching.phase')=='independent'
    assert page.evaluate('cmaMovement.state().moves')==[]
    expect(page.locator('#movementExampleDialog')).not_to_be_visible()
    expect(page.locator('#movementOutcome')).to_have_count(0)
    expect(page.locator('#movementBoard [aria-label^="d2 백 폰"]')).to_have_count(1)
    assert page.evaluate("async()=>({me:await api('/me'),journey:await api('/journey')})")==original
    page.locator('#movementBoard [aria-label^="d2 "]').click();page.locator('#movementBoard [aria-label^="e3 "]').click()
    expect(page.locator('#movementOutcome')).to_contain_text('둘 수 없는 이동')
    assert page.evaluate('cmaMovement.state().moves')==[]
    assert page.locator('#movementOutcome').evaluate('(e)=>getComputedStyle(e).pointerEvents')=='none'
    page.evaluate("cmaNavigation.go('home')")
    expect(page.locator('#movementOutcome')).to_have_count(0)


@pytest.mark.parametrize('account,legacy',[(False,True),(False,False),(True,False)])
def test_saved_identity_home_resume_autointro_preserves_attempt(isolated,site,account,legacy):
    import secrets
    page,_=isolated;enter(page)
    if account:
        page.evaluate("cmaNavigation.go('profile/account')")
        page.get_by_role('button',name='계정 전환',exact=True).click()
        page.locator('#codeField').fill('ENTRY-'+secrets.token_hex(5))
        page.locator('#pinField').fill('entry-test-pin')
        page.locator('#signup').click()
        page.wait_for_function("localStorage.getItem('cma_identity')==='account' && cmaNavigation.current()==='home'")
    page.evaluate("""async legacy=>{const d=await api('/movement');await api('/movement/start','POST',{action:'start',unit_id:'rules-shield-piece',revision:d.revision,request_id:crypto.randomUUID(),relationship_flow:!legacy});await cmaMovement.load(true);} """,legacy)
    page.evaluate('cmaMovement.enter()');ready(page)
    expect(page.locator('#movementExampleDialog')).to_be_visible();skip(page)
    if not legacy:practice(page)
    page.locator('#movementBoard [aria-label^="d2 "]').click();page.locator('#movementBoard [aria-label^="d3 "]').click()
    page.wait_for_function('!cmaMovement.state().pending && cmaMovement.state().data.active.moves.length===1')
    before=page.evaluate("api('/movement')")['active']
    page.evaluate("cmaNavigation.go('home')");page.reload()
    resume=page.locator('#homeNextAction > button');expect(resume).to_have_text('기초 이어하기');resume.click()
    expect(page.locator('#movementExampleDialog')).to_be_visible()
    assert page.evaluate('cmaMovement.state().clipPlaying')
    page.keyboard.press('Escape');expect(page.locator('#movementExampleDialog')).not_to_be_visible()
    after=page.evaluate("api('/movement')")['active']
    for key in ['session_id','moves','mistakes','done','result']:
        assert after[key]==before[key]
    assert after['helped']
    page.wait_for_timeout(1850)
    expect(page.locator('#movementExampleDialog')).not_to_be_visible()
    # Same-route refresh is a render/read, not a new entry.
    page.evaluate('cmaMovement.load()');ready(page)
    expect(page.locator('#movementExampleDialog')).not_to_be_visible()


def test_promotion_pending_cancel_and_opponent_do_not_grade(isolated,site):
    page,_=isolated;enter(page);pick(page,'rules-pawn-promotion');skip(page)
    page.locator('#movementBoard [aria-label^="e7 "]').click();page.locator('#movementBoard [aria-label^="e8 "]').click()
    dialog=page.get_by_role('dialog',name='어떤 기물로 승격할까요?')
    expect(dialog).to_be_visible()
    expect(page.locator('#movementOutcome')).to_have_count(0)
    assert page.evaluate('cmaMovement.state().moves')==[]
    page.keyboard.press('Escape');expect(dialog).not_to_be_visible()
    expect(page.locator('#movementOutcome')).to_have_count(0)
    page.locator('#movementBoard [aria-label^="e8 "]').click()
    expect(dialog).to_be_visible()
    dialog.get_by_role('button',name=__import__('re').compile('퀸$')).click()
    expect(page.locator('#movementOutcome')).to_contain_text('O')
    assert not page.evaluate('cmaMovement.state().done')
    assert page.evaluate('cmaMovement.state().moves')==['e7e8q']
    page.wait_for_timeout(1900);expect(page.locator('#movementOutcome')).to_have_count(0)
    assert not page.evaluate('cmaMovement.state().done')
