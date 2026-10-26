from pathlib import Path
import pytest
from playwright.sync_api import expect
from movement_ui_helpers import options, finish_example, independent, playback
from test_redesign_browser_followup import isolated, site
from test_movement_browser import enter, ready


def choose_intro(page,unit):
    page.evaluate("async id=>{const d=await api('/movement');await api('/movement/start','POST',{action:'start',unit_id:id,revision:d.revision,request_id:crypto.randomUUID(),relationship_flow:true});await cmaMovement.load(true);}",unit)
    ready(page)
    expect(page.locator('#movementClip')).to_be_visible()
    expect(page.locator('#movementExampleTitle')).to_contain_text('먼저 예시 보기')


@pytest.mark.parametrize('width,height',[(320,650),(390,844),(844,390),(1366,768)])
def test_explain_guide_independent_and_replay_records(isolated,site,width,height):
    page,_=isolated;page.set_viewport_size(dict(width=width,height=height));enter(page)
    choose_intro(page,'rules-shield-piece')
    expect(page.locator('#movementGoal')).to_contain_text('흑 비숍 g7 → 백 룩 a1')
    expect(page.locator('#movementBoard .foundation-arrows path')).not_to_have_count(0)
    assert page.evaluate('cmaMovement.state().clipPlaying')
    page.get_by_role('button',name='멈춤',exact=True).click()
    playback(page)
    for control in page.locator('#movementClip button:enabled').all():
        control.scroll_into_view_if_needed()
        assert control.evaluate('(b)=>{const r=b.getBoundingClientRect();return r.height>=44 && b.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}')
    output=Path('/tmp/relationship-qa');output.mkdir(exist_ok=True)
    page.screenshot(path=str(output/f'explain-{width}.png'),full_page=True)
    original=page.evaluate("async()=>({me:await api('/me'),journey:await api('/journey')})")
    finish_example(page)
    expect(page.locator('#movementLesson')).to_contain_text('2/3')
    page.screenshot(path=str(output/f'guided-{width}.png'),full_page=True)
    source=page.locator('#movementBoard [aria-label^="d2 "]')
    source.focus();page.keyboard.press('Enter');expect(source).to_be_focused()
    page.locator('#movementBoard [aria-label^="d4 "]').click()
    expect(page.locator('#movementLesson')).to_contain_text('3/3')
    state=page.evaluate('cmaMovement.state()')
    assert state['moves']==[] and not state['done'] and state['unit']['result'] is None
    page.reload();ready(page)
    expect(page.locator('#movementExampleDialog')).to_be_visible()
    finish_example(page)
    expect(page.locator('#movementLesson')).to_contain_text('3/3')
    assert page.evaluate('cmaMovement.state().unit.teaching.guide_done')
    expect(page.locator('#movementLesson')).to_contain_text('3/3')
    expect(page.locator('#movementBoard .foundation-arrows')).to_have_count(0)
    page.locator('#movementBoard [aria-label^="d2 "]').click()
    expect(page.locator('#movementBoard .target')).to_have_count(0)
    page.locator('#movementBoard [aria-label^="d4 "]').click()
    page.wait_for_function('cmaMovement.state().data.active.done && !cmaMovement.state().pending')
    assert page.evaluate('cmaMovement.state().unit.practice_result')=='assisted_application'
    assert page.evaluate("async()=>({me:await api('/me'),journey:await api('/journey')})")==original
    for control in page.locator('#movementActions button:enabled').all():
        control.scroll_into_view_if_needed()
        assert control.evaluate('(b)=>{const r=b.getBoundingClientRect();return b.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    output=Path('/tmp/relationship-qa');output.mkdir(exist_ok=True)
    page.screenshot(path=str(output/f'independent-{width}.png'),full_page=True)


def test_reduced_motion_route_skip_duplicate_and_help(isolated,site):
    page,_=isolated;page.emulate_media(reduced_motion='reduce');enter(page)
    choose_intro(page,'rules-mate-queen')
    assert not page.evaluate('cmaMovement.state().clipPlaying')
    playback(page)
    page.get_by_role('button',name='다음 수',exact=True).click()
    page.wait_for_function('cmaMovement.state().clipIndex>0')
    assert not page.evaluate("cmaBoardPresentation.isAnimating('movementBoard')")
    page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'))")
    assert not page.evaluate('cmaMovement.state().clipPlaying')
    page.evaluate("delete document.hidden;cmaNavigation.go('home')")
    assert page.evaluate('cmaMovement.state().clip') is None
    page.evaluate("cmaNavigation.go('learn/movement')");ready(page)
    expect(page.locator('#movementExampleDialog')).to_be_visible()
    expect(page.locator('#movementClip')).to_be_visible()
    assert not page.evaluate('cmaMovement.state().clipPlaying')
    page.locator('#movementExampleActions button').evaluate('(b)=>{b.click();b.click()}')
    expect(page.locator('#movementExampleDialog')).not_to_be_visible()
    independent(page)
    expect(page.locator('#movementLesson')).to_contain_text('3/3')
    options(page)
    page.get_by_role('button',name='짧은 시연 · 정답 도움',exact=True).click()
    expect(page.locator('#movementClip')).to_be_visible()
    finish_example(page)
    page.locator('#movementBoard [aria-label^="g5 "]').click();page.locator('#movementBoard [aria-label^="g7 "]').click()
    page.wait_for_function('cmaMovement.state().data.active.done && !cmaMovement.state().pending')
    assert page.evaluate('cmaMovement.state().unit.practice_result')=='assisted_application'


@pytest.mark.parametrize('unit_id',['rules-protect-piece','rules-mate-queen','rules-escape-block','rules-castle-attacked','rules-check-plan','rules-avoid-loss'])
def test_relationship_topics_replay_keyboard_and_guided_actions(isolated,site,unit_id):
    from movement_content import BY_ID
    page,_=isolated;page.set_viewport_size(dict(width=390,height=844));enter(page);choose_intro(page,unit_id)
    playback(page)
    next_button=page.locator('#movementClip').get_by_role('button',name='다음 수',exact=True)
    next_button.focus();page.keyboard.press('Enter')
    assert page.evaluate('cmaMovement.state().clipIndex')==1
    expect(next_button).to_be_focused()
    while not next_button.is_disabled():
        next_button.click()
        if unit_id=='rules-protect-piece' and '되잡을 수' in page.locator('#movementGoal').inner_text():
            Path('/tmp/relationship-qa').mkdir(exist_ok=True)
            page.screenshot(path='/tmp/relationship-qa/protection-recapture.png',full_page=True)
        if unit_id=='rules-mate-queen' and page.evaluate('cmaMovement.state().clip.frames[cmaMovement.state().clipIndex].arrows?.length>0'):
            Path('/tmp/relationship-qa').mkdir(exist_ok=True)
            page.screenshot(path='/tmp/relationship-qa/mate-attack.png',full_page=True)
    assert not page.evaluate('cmaMovement.state().done')
    output=Path('/tmp/relationship-qa');output.mkdir(exist_ok=True)
    page.screenshot(path=str(output/f'{unit_id}-explanation.png'),full_page=True)
    finish_example(page)
    for action in BY_ID[unit_id]['example_actions']:
        count=page.evaluate('cmaMovement.state().unit.teaching.guide_moves.length')
        if action.startswith('square:'):page.locator(f'#movementBoard [aria-label^="{action[7:]} "]').click()
        else:
            page.locator(f'#movementBoard [aria-label^="{action[:2]} "]').click()
            page.locator(f'#movementBoard [aria-label^="{action[2:4]} "]').click()
        page.wait_for_function('(n)=>cmaMovement.state().unit.teaching.guide_moves.length>n',arg=count)
    expect(page.locator('#movementLesson')).to_contain_text('3/3')
    assert page.evaluate('cmaMovement.state().moves')==[]
    assert page.evaluate('cmaMovement.state().unit.teaching.guide_done')
    expect(page.locator('#movementLesson')).to_contain_text('3/3')
    assert page.evaluate('cmaMovement.state().moves')==[]
    assert not page.evaluate('cmaMovement.state().done')


def test_restart_and_late_guidance_after_route_exit(isolated,site):
    page,_=isolated;enter(page);choose_intro(page,'rules-protect-piece')
    old=page.evaluate('cmaMovement.state().unit.session_id')
    finish_example(page)
    options(page)
    page.get_by_role('button',name='설명부터 다시',exact=True).click()
    expect(page.locator('#movementClip')).to_be_visible()
    assert page.evaluate('cmaMovement.state().unit.session_id')!=old
    page.evaluate("()=>{const original=api;window.api=async(...args)=>{const result=await original(...args);if(args[0]==='/movement/lesson')await new Promise(r=>setTimeout(r,600));return result;};}")
    page.locator('#movementExampleActions button').click()
    page.evaluate("cmaNavigation.go('home')")
    page.wait_for_timeout(850)
    assert page.evaluate('cmaMovement.state().clip') is None
    assert page.evaluate('cmaNavigation.current()')=='home'
    page.evaluate("cmaNavigation.go('learn/movement')");ready(page)
    expect(page.locator('#movementExampleDialog')).to_be_visible()
    finish_example(page)
    expect(page.locator('#movementLesson')).to_contain_text('2/3')
    assert page.evaluate('cmaMovement.state().moves')==[]


def test_committed_guidance_response_failure_recovers_and_logout_cancels(isolated,site):
    import secrets
    page,_=isolated;enter(page)
    page.evaluate("cmaNavigation.go('profile/account')")
    page.get_by_role('button',name='계정 전환',exact=True).click()
    page.locator('#codeField').fill('RELATION-'+secrets.token_hex(4))
    page.locator('#pinField').fill('relationship-test-pin')
    page.locator('#signup').click()
    page.wait_for_function("localStorage.getItem('cma_identity')==='account' && token===localStorage.getItem('chess_token')")
    # Registration finishes by returning home; do not race its final navigation.
    page.wait_for_function("cmaNavigation.current()==='home'")
    page.evaluate("cmaNavigation.go('learn/movement')")
    choose_intro(page,'rules-avoid-loss')
    page.evaluate("()=>{const original=api;let fail=true;window.api=async(...args)=>{const r=await original(...args);if(args[0]==='/movement/lesson'&&fail){fail=false;throw Error('검사용 응답 유실');}return r;};}")
    page.locator('#movementExampleActions button').click()
    page.wait_for_function('!!cmaMovement.state().error')
    # Reload reads the committed guide stage; it must not retry a mutation.
    page.locator('#movementExampleDialog').get_by_role('button',name='저장 위치 확인',exact=True).click()
    expect(page.locator('#movementLesson')).to_contain_text('2/3')
    assert page.evaluate('cmaMovement.state().moves')==[]
    page.evaluate("()=>{const original=api;window.api=async(...args)=>{const r=await original(...args);if(args[0]==='/movement/lesson'){await new Promise(resolve=>window.releaseGuidance=resolve);window.guidanceReturned=true;}return r;};}")
    page.locator('#movementBoard [aria-label^="c4 "]').click();page.locator('#movementBoard [aria-label^="d3 "]').click()
    page.wait_for_function('!!window.releaseGuidance')
    assert page.evaluate('cmaMovement.state().unit.teaching.guide_moves')==[]
    page.evaluate("cmaNavigation.go('profile/account')")
    page.locator('#signout').click()
    page.wait_for_function('!token')
    page.evaluate('window.releaseGuidance()')
    page.wait_for_function('window.guidanceReturned')
    assert page.evaluate('cmaMovement.state().unit') is None
    assert page.evaluate('cmaMovement.state().clip') is None
    assert not page.evaluate("localStorage.getItem('chess_token')")


def test_cancelled_introduction_cannot_become_independent_practice(isolated,site):
    page,_=isolated;enter(page);choose_intro(page,'rules-shield-piece')
    page.evaluate('cmaMovement.cancel()')
    # A presentation cancellation never advances the persisted learning phase.
    page.evaluate('cmaMovement.load(true)')
    ready(page)
    expect(page.locator('#movementExampleDialog')).to_be_visible()
    expect(page.locator('#movementClip')).to_be_visible()
    assert page.evaluate('cmaMovement.state().unit.teaching.phase')=='explain'
    assert page.evaluate('cmaMovement.state().moves')==[]
    assert not page.evaluate('cmaMovement.state().done')
    finish_example(page)
    independent(page)
    expect(page.locator('#movementLesson')).to_contain_text('3/3')


def test_existing_lesson_can_opt_into_new_flow_without_erasing_history(isolated,site):
    page,_=isolated;enter(page)
    page.evaluate("async()=>{const d=await api('/movement');await api('/movement/start','POST',{unit_id:'rules-shield-piece',revision:d.revision,request_id:crypto.randomUUID()});await cmaMovement.load(true);}")
    ready(page)
    assert not page.evaluate('cmaMovement.state().unit.teaching')
    old=page.evaluate('cmaMovement.state().unit.session_id')
    finish_example(page)
    page.locator('#movementBoard [aria-label^="d2 "]').click();page.locator('#movementBoard [aria-label^="d4 "]').click()
    page.wait_for_function('cmaMovement.state().data.active.done && !cmaMovement.state().pending')
    completed=page.evaluate('cmaMovement.state().data.summary.completed')
    options(page)
    page.get_by_role('button',name='기록 보존 · 설명부터 새로',exact=True).click()
    expect(page.locator('#movementClip')).to_be_visible()
    assert page.evaluate('cmaMovement.state().unit.session_id')!=old
    assert page.evaluate('cmaMovement.state().data.summary.completed')==completed
    assert page.evaluate('cmaMovement.state().data.units.find(u=>u.id===cmaMovement.state().unit.unit_id).completed_before')
