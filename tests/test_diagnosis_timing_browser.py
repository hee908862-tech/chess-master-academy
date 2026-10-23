"""Deterministic monotonic browser clock; no engine or operating account."""
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[1]
HTML='<html><head><meta charset="utf-8"></head><body><main id="controls"></main><script src="/diagnosis-timing.js"></script></body></html>'


@pytest.fixture
def timing_page():
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        page=browser.new_page()
        page.add_init_script("window.testClock=0;Object.defineProperty(performance,'now',{value:()=>window.testClock});window.tick=n=>window.testClock+=n;")
        def route(r):
            if r.request.url.endswith('/diagnosis-timing.js'):r.fulfill(content_type='application/javascript; charset=utf-8',body=(ROOT/'public/diagnosis-timing.js').read_text())
            else:r.fulfill(content_type='text/html; charset=utf-8',body=HTML)
        page.route('http://localhost:9876/**',route);page.goto('http://localhost:9876/')
        page.evaluate("cmaDiagnosisTiming.begin('session-one','item-one',null);cmaDiagnosisTiming.offer(document.querySelector('#controls'))")
        yield page
        browser.close()


def ms(page):return page.evaluate('cmaDiagnosisTiming.snapshot()')['active_ms']


def test_only_foreground_segments_exclude_server_animation_and_hidden(timing_page):
    page=timing_page;page.evaluate('tick(1200)');assert ms(page)==1200
    page.evaluate("cmaDiagnosisTiming.pause('server_pending');tick(10000);cmaDiagnosisTiming.pause('animation');cmaDiagnosisTiming.resume('server_pending');tick(2000)")
    assert ms(page)==1200
    page.evaluate("cmaDiagnosisTiming.resume('animation');tick(300)");assert ms(page)==1500
    page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));tick(30000)")
    assert ms(page)==1500
    page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'));tick(500)")
    assert ms(page)==2000


def test_explicit_pause_recorded_and_restored_without_counting_absence(timing_page):
    page=timing_page;page.evaluate('tick(1000)');page.get_by_role('button',name='생각 시간 일시정지',exact=True).click()
    page.evaluate('tick(10000)');before=page.evaluate('cmaDiagnosisTiming.snapshot()')
    assert before['active_ms']==1000 and before['explicit_pause_used']
    page.reload();page.evaluate("tick(60000);cmaDiagnosisTiming.begin('session-one','item-one',null);cmaDiagnosisTiming.offer(document.querySelector('#controls'));tick(60000)")
    after=page.evaluate('cmaDiagnosisTiming.snapshot()')
    assert after['active_ms']==1000 and after['stream_id']==before['stream_id'] and after['seq']>before['seq']
    page.get_by_role('button',name='생각 시간 측정 다시 시작',exact=True).click();page.evaluate('tick(2000)')
    assert ms(page)==3000
    expect(page.get_by_role('status')).to_contain_text('속도 비교에서 제외')


def test_pagehide_reload_no_gap_and_server_cursor_reconciles(timing_page):
    page=timing_page;page.evaluate('tick(1234.5)');before=page.evaluate('cmaDiagnosisTiming.snapshot()')
    page.evaluate("dispatchEvent(new Event('pagehide'));tick(60000)")
    assert ms(page)==1234
    page.reload();page.evaluate("tick(100000);cmaDiagnosisTiming.begin('session-one','item-one',null);tick(1000)")
    after=page.evaluate('cmaDiagnosisTiming.snapshot()')
    assert after['active_ms']==2234 and after['stream_id']==before['stream_id'] and not after['limited']
    page.evaluate("x=>cmaDiagnosisTiming.begin('session-one','item-one',{version:x.version,streams:{[x.stream_id]:{seq:20,client_ms:3000}}})",after)
    reconciled=page.evaluate('cmaDiagnosisTiming.snapshot()')
    assert reconciled['seq']==21 and reconciled['active_ms']==3000


def test_item_and_session_namespaces_do_not_share_elapsed_time(timing_page):
    page=timing_page;page.evaluate("tick(1000);cmaDiagnosisTiming.pause('question');cmaDiagnosisTiming.begin('session-two','item-one',null);cmaDiagnosisTiming.resume('question');tick(250)")
    assert ms(page)==250
    page.evaluate("cmaDiagnosisTiming.clear();tick(5000)")
    assert page.evaluate('cmaDiagnosisTiming.snapshot()') is None
    page.evaluate("cmaDiagnosisTiming.begin('session-one','item-one',null)")
    assert ms(page)==1000


def test_clock_anomaly_and_duration_cap_mark_limited_without_negative_time(timing_page):
    page=timing_page;page.evaluate('tick(500)');assert ms(page)==500
    page.evaluate('tick(-1000)');value=page.evaluate('cmaDiagnosisTiming.snapshot()')
    assert value['active_ms']==500 and value['limited']
    page.evaluate('tick(4000000)');value=page.evaluate('cmaDiagnosisTiming.snapshot()')
    assert value['active_ms']==1800000 and value['limited']
