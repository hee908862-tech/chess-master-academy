"""Foreground clock component, real Chromium with synthetic preparation callback."""
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
@pytest.fixture
def view():
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page();page.route('http://localhost/',lambda r:r.fulfill(content_type='text/html',body='<main><div id="clock"></div><div id="board"></div><button id="move" disabled>착수</button></main>'))
        page.goto('http://localhost/');page.add_style_tag(path=str(ROOT/'public/solving-clock.css'));page.add_script_tag(path=str(ROOT/'public/solving-clock.js'))
        page.evaluate('''()=>{window.prepares=0;window.readyEvents=[];window.beginClock=(item='one',server={})=>cmaSolvingClock.begin({sessionId:'synthetic-session',itemId:item,server,host:'clock',board:'board',prepare:async()=>{prepares++;return {prep_started_at:new Date().toISOString()}},onReady:value=>{readyEvents.push(value);document.querySelector('#move').disabled=!value}})}''')
        yield page
        browser.close()

def start(view,item='one'):
    view.evaluate('(item)=>{void beginClock(item)}',item)
    expect(view.locator('#move')).to_be_disabled()
    view.wait_for_function('cmaSolvingClock.canInput()',timeout=6000)

@pytest.mark.parametrize('width,height',[(1366,768),(360,800),(390,844),(844,390)])
def test_preparation_locks_three_seconds_and_stable_accessible_panel(view,width,height):
    view.set_viewport_size({'width':width,'height':height});view.evaluate('void beginClock()')
    expect(view.locator('#move')).to_be_disabled();view.wait_for_timeout(1000)
    assert not view.evaluate('cmaSolvingClock.canInput()')
    view.wait_for_function('cmaSolvingClock.canInput()',timeout=5000)
    expect(view.locator('[role=timer]')).to_have_attribute('aria-live','off')
    expect(view.locator('#clock')).to_contain_text('시간 보너스에서 제외')
    assert view.evaluate('prepares')==1
    assert view.evaluate('document.documentElement.scrollWidth<=innerWidth+1')

def test_failure_does_not_start_and_retry_is_keyboard_available(view):
    view.evaluate("document.querySelector('#board').innerHTML='<img src=\"data:image/png;base64,broken\">';void beginClock()")
    expect(view.get_by_role('button',name='보드 준비 다시 시도')).to_be_visible()
    assert view.evaluate('prepares')==0
    assert view.evaluate('cmaSolvingClock.snapshot()') is None
    view.evaluate("document.querySelector('#board').replaceChildren()")
    view.get_by_role('button',name='보드 준비 다시 시도').focus();view.keyboard.press('Enter')
    view.wait_for_function('cmaSolvingClock.canInput()',timeout=6000)
    assert view.evaluate('prepares')==1

def test_pending_animation_pause_duplicate_and_result_freeze(view):
    start(view);view.wait_for_timeout(400)
    first=view.evaluate('cmaSolvingClock.snapshot()');view.wait_for_timeout(400)
    assert view.evaluate('cmaSolvingClock.snapshot()')==first
    assert not view.evaluate('cmaSolvingClock.canInput()')
    view.evaluate("cmaSolvingClock.resume('waiting');cmaSolvingClock.pause('animation')")
    view.wait_for_timeout(400);view.evaluate("cmaSolvingClock.resume('animation')")
    second=view.evaluate('cmaSolvingClock.snapshot()')
    assert second['active_ms']-first['active_ms']<150 and not second['interrupted']
    view.evaluate("cmaSolvingClock.resume('waiting');cmaSolvingClock.pause('manual')")
    expect(view.locator('#move')).to_be_disabled();view.evaluate("cmaSolvingClock.resume('manual')")
    assert view.evaluate('cmaSolvingClock.snapshot().interrupted') is True
    view.evaluate('cmaSolvingClock.stop()');text=view.locator('[role=timer]').inner_text();view.wait_for_timeout(1100)
    assert view.locator('[role=timer]').inner_text()==text
    assert not view.evaluate('cmaSolvingClock.canInput()')

def test_same_item_no_reset_reload_interrupted_and_next_item_fresh(view):
    start(view);view.wait_for_timeout(300);notifications=view.evaluate('readyEvents.length');view.evaluate('void beginClock()');assert view.evaluate('readyEvents.length')==notifications
    assert view.evaluate('prepares')==1
    first=view.evaluate('cmaSolvingClock.snapshot()');view.evaluate("cmaSolvingClock.resume('waiting')")
    # New module context simulates reload, retaining per-tab sessionStorage marker.
    view.evaluate('cmaSolvingClock.clear()');view.add_script_tag(path=str(ROOT/'public/solving-clock.js'))
    view.evaluate("void beginClock('one',{prep_started_at:new Date(Date.now()-5000).toISOString(),active_ms:300})")
    view.wait_for_function('cmaSolvingClock.canInput()',timeout=1000)
    again=view.evaluate('cmaSolvingClock.snapshot()')
    assert again['interrupted'] and again['stream_id']!=first['stream_id']
    start(view,'two');assert view.evaluate('prepares')==2
    assert view.evaluate('cmaSolvingClock.snapshot().interrupted') is False

def test_hidden_and_uncertain_pause_disable_input_and_exclude_bonus(view):
    start(view)
    view.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'))")
    assert not view.evaluate('cmaSolvingClock.canInput()')
    view.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'))")
    assert view.evaluate('cmaSolvingClock.snapshot().interrupted') is True
    view.evaluate("cmaSolvingClock.resume('waiting');cmaSolvingClock.invalidate('request_failed')")
    assert not view.evaluate('cmaSolvingClock.canInput()')
    assert view.evaluate('cmaSolvingClock.snapshot().limited') is True

def test_image_download_and_decode_precede_prepare_callback(view):
    pending=[];view.route('http://localhost/piece.svg',lambda r:pending.append(r))
    view.evaluate("document.querySelector('#board').innerHTML='<img src=\"/piece.svg\">';void beginClock()")
    view.wait_for_timeout(200)
    assert pending and view.evaluate('prepares')==0
    assert not view.evaluate('cmaSolvingClock.canInput()')
    pending[0].fulfill(content_type='image/svg+xml',body='<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40"><circle cx="20" cy="20" r="16"/></svg>')
    view.wait_for_function('prepares===1')
    assert not view.evaluate('cmaSolvingClock.canInput()')
    view.wait_for_function('cmaSolvingClock.canInput()',timeout=6000)


def test_saved_frozen_feedback_restores_without_prepare_or_running(view):
    view.evaluate("void beginClock('saved-result',{frozen:true,active_ms:12345,prep_started_at:new Date(Date.now()-30000).toISOString()})")
    expect(view.locator('[role=timer]')).to_have_text('풀이 시간 12초')
    assert view.evaluate('prepares')==0
    assert not view.evaluate('cmaSolvingClock.canInput()')
    view.wait_for_timeout(1100)
    expect(view.locator('[role=timer]')).to_have_text('풀이 시간 12초')
    expect(view.locator('#clock')).to_contain_text('풀이 종료')
    view.evaluate("void beginClock('saved-result',{frozen:true,active_ms:5000})")
    expect(view.locator('[role=timer]')).to_have_text('풀이 시간 5초')
    view.evaluate("void beginClock('saved-result',{frozen:true,active_ms:null})")
    expect(view.locator('[role=timer]')).to_have_text('풀이 시간 미측정')
