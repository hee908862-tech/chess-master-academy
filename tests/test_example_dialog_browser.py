"""Native example modal, real local API and Chromium; no physical WebView claim."""
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_redesign_browser_followup import isolated, site
from test_movement_browser import enter, ready
from test_relationship_lessons_browser import choose_intro
from movement_ui_helpers import options, finish_example, independent, playback


@pytest.mark.parametrize('width,height,zoom',[(320,650,1),(390,844,1),(844,390,1),(1366,768,1),(390,844,1.25)])
def test_autoplay_modal_isolation_focus_and_mobile_controls(isolated,site,width,height,zoom):
    page,_=isolated;page.set_viewport_size(dict(width=width,height=height));enter(page)
    page.evaluate('(zoom)=>document.documentElement.style.zoom=zoom',zoom)
    choose_intro(page,'rules-shield-piece')
    dialog=page.locator('#movementExampleDialog')
    expect(dialog).to_have_accessible_name('공격길을 막아 지키기 · 먼저 예시 보기')
    expect(dialog).to_be_visible()
    expect(page.locator('#movementExampleText')).to_contain_text('흑 비숍 g7 → 백 룩 a1')
    expect(page.locator('#movementExampleTitle')).to_be_focused()
    assert page.evaluate('cmaMovement.state().clipPlaying')
    before=page.evaluate("async()=>({movement:await api('/movement'),me:await api('/me'),journey:await api('/journey')})")
    page.wait_for_function('cmaMovement.state().clipIndex>0')
    page.get_by_role('button',name='멈춤',exact=True).click()
    index=page.evaluate('cmaMovement.state().clipIndex');page.wait_for_timeout(1750)
    assert page.evaluate('cmaMovement.state().clipIndex')==index
    # Native modal prevents background focus/input; no background scroll.
    page.evaluate("document.getElementById('movementUnit').focus()")
    assert page.evaluate("document.getElementById('movementExampleDialog').contains(document.activeElement)")
    assert page.evaluate("getComputedStyle(document.body).overflow")=='hidden'
    page.locator('#movementExampleTitle').focus();page.keyboard.press('Shift+Tab')
    expect(page.locator('#movementExampleActions button')).to_be_focused()
    page.keyboard.press('Tab');expect(dialog.get_by_role('button',name='닫기 · 스킵하고 연습',exact=True)).to_be_focused()
    page.keyboard.press('Shift+Tab');expect(page.locator('#movementExampleActions button')).to_be_focused()
    playback(page)
    for control in dialog.locator('button:enabled:not(.sq)').all():
        control.scroll_into_view_if_needed()
        assert control.evaluate('(b)=>{const r=b.getBoundingClientRect();return r.height>=44 && b.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}')
    assert dialog.evaluate('(d)=>d.scrollWidth<=d.clientWidth+1')
    output=Path('/tmp/example-dialog-qa');output.mkdir(exist_ok=True)
    dialog.evaluate('(d)=>d.scrollTop=0')
    page.screenshot(path=str(output/f'example-{width}x{height}-zoom{zoom}.png'),full_page=True)
    page.keyboard.press('Escape');expect(dialog).not_to_be_visible()
    expect(page.locator('#movementTitle')).to_be_focused()
    assert not page.evaluate('cmaMovement.state().clipPlaying')
    assert page.evaluate("getComputedStyle(document.body).overflow")!='hidden'
    after=page.evaluate("async()=>({movement:await api('/movement'),me:await api('/me'),journey:await api('/journey')})")
    assert after['me']==before['me'] and after['journey']==before['journey']
    for key in ['session_id','moves','done','mistakes','result']:
        assert after['movement']['active'][key]==before['movement']['active'][key]
    assert after['movement']['active']['teaching']['phase']=='guided'
    # Reopen resets playback without creating a second dialog; close restores trigger.
    options(page)
    reopen=page.get_by_role('button',name='짧은 시연 · 정답 도움',exact=True)
    reopen.click();expect(dialog).to_be_visible()
    assert page.evaluate('cmaMovement.state().clipIndex')==0
    expect(page.locator('dialog[open]')).to_have_count(1)
    page.keyboard.press('Escape');expect(reopen).to_be_focused()
    page.reload();ready(page)
    expect(dialog).to_be_visible()
    finish_example(page)
    assert page.evaluate('cmaMovement.state().unit.teaching.phase')=='guided'


def test_reduced_motion_steps_replay_skip_and_background_cancel(isolated,site):
    page,_=isolated;page.emulate_media(reduced_motion='reduce');enter(page);choose_intro(page,'rules-mate-queen')
    dialog=page.locator('#movementExampleDialog')
    assert not page.evaluate('cmaMovement.state().clipPlaying')
    page.wait_for_timeout(1800);assert page.evaluate('cmaMovement.state().clipIndex')==0
    expect(dialog.get_by_role('button',name='재생',exact=True)).to_have_count(0)
    playback(page)
    dialog.get_by_role('button',name='다음 수',exact=True).click()
    assert page.evaluate('cmaMovement.state().clipIndex')==1
    assert not page.evaluate("cmaBoardPresentation.isAnimating('movementBoard')")
    playback(page)
    dialog.get_by_role('button',name='다시 보기',exact=True).click()
    assert page.evaluate('cmaMovement.state().clipIndex')==0
    assert not page.evaluate('cmaMovement.state().clipPlaying')
    page.keyboard.press('Escape')
    options(page)
    page.get_by_role('button',name='짧은 시연 · 정답 도움',exact=True).click()
    expect(dialog).to_be_visible()
    page.locator('#movementExampleActions button').evaluate('(b)=>{b.click();b.click()}')
    expect(dialog).not_to_be_visible()
    expect(page.locator('#movementLesson')).to_contain_text('2/3')
    assert page.evaluate('cmaMovement.state().moves')==[]
    assert not page.evaluate('cmaMovement.state().done')


def test_autoplay_visibility_route_back_restart_and_logout_cancel(isolated,site):
    page,_=isolated;enter(page);choose_intro(page,'rules-protect-piece')
    first=page.evaluate('cmaMovement.state().unit.session_id')
    page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'))")
    assert not page.evaluate('cmaMovement.state().clipPlaying')
    page.evaluate("delete document.hidden;document.dispatchEvent(new Event('visibilitychange'))")
    assert not page.evaluate('cmaMovement.state().clipPlaying')
    playback(page)
    page.get_by_role('button',name='다시 보기',exact=True).click()
    assert page.evaluate('cmaMovement.state().clipPlaying')
    page.evaluate("cmaNavigation.go('home')")
    expect(page.locator('#movementExampleDialog')).not_to_be_visible()
    page.wait_for_timeout(1800)
    assert page.evaluate('cmaMovement.state().clip') is None
    page.go_back();ready(page)
    expect(page.locator('#movementExampleDialog')).to_be_visible()
    finish_example(page)
    expect(page.locator('#movementLesson')).to_contain_text('2/3')
    options(page)
    page.get_by_role('button',name='설명부터 다시',exact=True).click()
    expect(page.locator('#movementExampleDialog')).to_be_visible()
    assert page.evaluate('cmaMovement.state().unit.session_id')!=first
    assert page.evaluate('cmaMovement.state().clipPlaying')
    # Simulate the shared logout handler while the modal is active.
    page.evaluate("document.getElementById('signout').click()")
    expect(page.locator('#movementExampleDialog')).not_to_be_visible()
    page.wait_for_timeout(1800)
    assert page.evaluate('cmaMovement.state().clip') is None
    assert not page.evaluate('cmaMovement.state().clipPlaying')
    assert page.evaluate('cmaMovement.state().unit') is None


def test_animation_is_inside_modal_and_silent_and_app_motion_preference(isolated,site):
    page,_=isolated;enter(page)
    page.evaluate("()=>{window.exampleSounds=[];window.playMoveSound=(...args)=>exampleSounds.push(args);const animate=Element.prototype.animate;Element.prototype.animate=function(frames,options){return animate.call(this,frames,{...options,duration:1500});};}")
    choose_intro(page,'rules-shield-piece')
    page.get_by_role('button',name='멈춤',exact=True).click()
    playback(page)
    # Bring the controls into view before starting fixed-position piece animation.
    # Scrolling intentionally cancels board motion; Playwright's implicit scroll
    # must settle before the click whose animation is being asserted.
    next_move=page.get_by_role('button',name='다음 수',exact=True)
    next_move.scroll_into_view_if_needed()
    page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
    next_move.click()
    ghost=page.locator('#movementExampleDialog .cma-motion-ghost')
    expect(ghost).to_have_count(1)
    expect(ghost).to_be_visible()
    assert page.evaluate('exampleSounds')==[]
    page.get_by_role('button',name='닫기 · 스킵하고 연습',exact=True).click()
    expect(page.locator('.cma-motion-ghost')).to_have_count(0)
    page.evaluate("localStorage.setItem('cma_reduce_motion','on')")
    options(page)
    page.get_by_role('button',name='짧은 시연 · 정답 도움',exact=True).click()
    expect(page.locator('#movementExampleDialog')).to_be_visible()
    assert not page.evaluate('cmaMovement.state().clipPlaying')
    expect(page.get_by_role('button',name='재생',exact=True)).to_have_count(0)
    playback(page)
    page.get_by_role('button',name='다음 수',exact=True).click()
    assert not page.evaluate("cmaBoardPresentation.isAnimating('movementBoard')")
    assert page.evaluate('exampleSounds')==[]


def test_real_lesson_picker_restores_focus_and_start_focuses_practice(isolated,site):
    page,_=isolated;enter(page)
    page.locator('#movementHelp summary').click()
    page.locator('#movementUnit').select_option('rules-shield-piece')
    opener=page.get_by_role('button',name='고른 연습 열기',exact=True)
    opener.click()
    expect(page.locator('#movementExampleDialog')).to_be_visible()
    assert page.evaluate('cmaMovement.state().clipPlaying')
    page.get_by_role('button',name='닫기 · 스킵하고 연습',exact=True).click()
    # The picker disclosure closes on a new lesson; focus moves to its practice title.
    expect(page.locator('#movementTitle')).to_be_focused()
    expect(page.locator('#movementLesson')).to_contain_text('2/3')
    expect(page.locator('#movementTitle')).to_be_focused()
    assert page.evaluate('cmaMovement.state().moves')==[]


def test_playback_disclosure_retains_focus_before_toggle_event(isolated,site):
    page,_=isolated;enter(page);choose_intro(page,'rules-protect-piece')
    # Both actions occur in the same task, before details' queued toggle event.
    page.evaluate("""()=>{const tools=document.querySelector('.movement-playback-tools');tools.open=true;
      const next=tools.querySelector('[data-control=next]');next.focus();next.click();}""")
    expect(page.locator('.movement-playback-tools')).to_have_attribute('open','')
    next_button=page.locator('#movementClip [data-control=next]')
    expect(next_button).to_be_visible();expect(next_button).to_be_focused()
    assert page.evaluate('cmaMovement.state().clipIndex')==1
    assert not page.evaluate('cmaMovement.state().clipPlaying')
