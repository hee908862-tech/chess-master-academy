"""Chromium regression: controlled network failures, plus real local newcomer/guest APIs."""
import json
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright, expect
from test_qa_browser import site, page, open_page, TASK, square, FEN


def test_diagnostic_single_flight_survives_navigation(page,site):
    starts=[];statuses=[]
    page.route('**/api/v8/assessment/start',lambda r:starts.append(r))
    page.route('**/api/v8/assessment/status',lambda r:(statuses.append(1),r.fulfill(json={'active':False})))
    open_page(page,site);page.evaluate("tab('assessment')")
    expect(page.locator('#v8Start')).to_be_enabled()
    page.locator('#v8Start').click()
    expect(page.locator('#v8Start')).to_be_disabled()
    assert len(starts)==1
    before=len(statuses)
    page.evaluate("tab('home');tab('assessment')")
    page.wait_for_timeout(700)
    assert len(statuses)==before
    starts[0].fulfill(json={'index':0,'domain':'로컬 테스트','question':{'id':'test','difficulty':1,'fen':FEN,'legal':['d7d8q'],'description':'첫 문항'}})
    expect(page.locator('#testProgress')).to_contain_text('문항 1 / 49')
    expect(page.locator('#testBoard .sq')).to_have_count(64)
    expect(page.locator('#v8Start')).to_be_enabled()


def test_lost_move_response_recovers_saved_completion(page,site):
    task={**TASK,'session_id':'recovery'}
    page.route('**/api/v9/puzzle/start',lambda r:r.fulfill(json=task))
    page.route('**/api/v9/puzzle/move',lambda r:r.abort())
    page.route('**/api/v9/session/puzzle',lambda r:r.fulfill(json={'session_id':'recovery','done':True,'result':{'completed_fen':FEN,'message':'저장된 해결 완료'}}))
    open_page(page,site);page.evaluate("tab('puzzle')");page.locator('#v9PuzzleStart').click()
    square(page,'v9PuzzleBoard','d7').click();square(page,'v9PuzzleBoard','d8').click()
    page.locator('#cmaPromotionModal button').filter(has_text='퀸').click()
    expect(page.locator('#v9PuzzleMessage')).to_contain_text('저장된 결과를 확인')
    expect(page.locator('#v9PuzzleBoard .sq')).to_have_count(64)
    expect(page.locator('#v9PuzzleNext')).to_be_visible()
    expect(page.locator('#v9PuzzleBoard .sq:enabled')).to_have_count(0)


def test_review_disabled_during_loading_and_failure(page,site):
    held=[];calls=[]
    page.route('**/api/games/history',lambda r:held.append(r))
    page.route('**/api/games/review/**',lambda r:(calls.append(1),r.abort()))
    open_page(page,site);page.evaluate("tab('review')")
    expect(page.locator('#reviewLoad')).to_be_disabled()
    page.evaluate('v5ReviewLoad()')
    assert calls==[]
    held[0].fulfill(status=503,json={'detail':'목록 서비스 지연'})
    expect(page.locator('#reviewGameSelect')).to_have_value('')
    expect(page.locator('#reviewStatus')).to_contain_text('재시도')
    expect(page.locator('#reviewLoad')).to_be_disabled()


@pytest.mark.parametrize('width,height',[(1366,768),(1165,747),(390,844),(844,390)])
def test_guest_return_and_board_layout(site,width,height):
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':width,'height':height})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(site[0]);page.wait_for_timeout(700)
        page.locator('[data-tab="puzzle"]:visible').first.click()
        expect(page.locator('#puzzle')).to_have_class('view active')
        page.locator('#v9PuzzleStart').click()
        expect(page.locator('#accountStatus')).to_contain_text('로그인이 필요')
        expect(page.locator('#v8ProfileResult')).to_contain_text('로그인하면')
        page.locator('#codeField').fill('BROWSER-QA');page.locator('#pinField').fill('test-pin-9384');page.locator('#signin').click()
        expect(page.locator('#puzzle')).to_have_class('view active')
        assert page.locator('#v9PuzzleBoard .sq').count()==0
        page.evaluate("tab('training')")
        expect(page.locator('#learningRouteStatus')).not_to_be_empty()
        page.locator('#learningRouteActions button').click()
        expect(page.locator('#learningBoard .sq')).to_have_count(64)
        expect(page.locator('#learningRouteStatus')).to_contain_text('1/4')
        page.evaluate("tab('play')")
        expect(page.locator('#gameStatus')).to_contain_text('새 대국을 시작')
        assert page.locator('#gameBoard').evaluate('(e)=>e.getBoundingClientRect().width')>200
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        Path('/tmp/followup-shots').mkdir(exist_ok=True)
        if width>850:
            box=page.locator('#gameBoard').bounding_box();assert box['y']+box['height']<=height
        page.screenshot(path=f'/tmp/followup-shots/play-{width}x{height}.png',full_page=True)
        page.evaluate("tab('assessment')")
        expect(page.locator('#v8Start')).to_be_enabled()
        if page.locator('#testBoard .sq').count()==0:page.locator('#v8Start').click()
        expect(page.locator('#testBoard .sq')).to_have_count(64,timeout=45000)
        page.screenshot(path=f'/tmp/followup-shots/assessment-{width}x{height}.png',full_page=True)
        if height<500:
            page.locator('#testBoard').evaluate("e=>e.scrollIntoView({block:'center',behavior:'instant'})")
            box=page.locator('#testBoard').bounding_box();assert 0<=box['y'] and box['y']+box['height']<=height
            current=page.evaluate("api('/v8/assessment/status')")
            source=current['question']['legal'][0][:2]
            square(page,'testBoard',source).click()
            expect(square(page,'testBoard',source)).to_have_class(__import__('re').compile('selected'))
            page.screenshot(path='/tmp/followup-shots/landscape-board-focused.png')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert not errors,errors
        browser.close()


def test_diagnostic_timeout_recovers_without_restarting(page,site):
    page.clock.install()
    starts=[]
    page.route('**/api/v8/assessment/start',lambda r:starts.append(r))
    open_page(page,site);page.evaluate("tab('assessment')")
    expect(page.locator('#v8Start')).to_be_enabled();page.locator('#v8Start').click()
    page.clock.fast_forward(13000)
    expect(page.locator('#testStatus')).to_contain_text('지연')
    page.clock.fast_forward(48000)
    expect(page.locator('#testStatus')).to_contain_text('초과')
    expect(page.locator('#v8Start')).to_be_disabled()
    page.route('**/api/v8/assessment/status',lambda r:r.fulfill(json={'active':True,'phase':'questions','index':0,'domain':'확인','question':{'id':'saved','difficulty':1,'fen':FEN,'legal':['d7d8q'],'description':'저장된 진단'}}))
    page.locator('#v8Retry').click()
    expect(page.locator('#testProgress')).to_contain_text('문항 1 / 49')
    assert len(starts)==1


def test_puzzle_uncertain_response_freezes_then_recovers_position(page,site):
    task={**TASK,'session_id':'uncertain'};moves=[]
    page.route('**/api/v9/puzzle/start',lambda r:r.fulfill(json=task))
    page.route('**/api/v9/puzzle/move',lambda r:(moves.append(1),r.abort()))
    page.route('**/api/v9/session/puzzle',lambda r:r.abort())
    open_page(page,site);page.evaluate("tab('puzzle')");page.locator('#v9PuzzleStart').click()
    square(page,'v9PuzzleBoard','d7').click();square(page,'v9PuzzleBoard','d8').click()
    page.locator('#cmaPromotionModal button').filter(has_text='퀸').click()
    expect(page.locator('#v9PuzzleMessage')).to_contain_text('저장 상태를 확인하지 못했습니다')
    expect(page.locator('#v9PuzzleBoard .sq:enabled')).to_have_count(0)
    page.route('**/api/v9/session/puzzle',lambda r:r.fulfill(json={'active':True,**task}))
    page.locator('#v9PuzzleMessage button').click()
    expect(page.locator('#v9PuzzleMessage')).to_contain_text('저장된 위치를 복원')
    expect(page.locator('#v9PuzzleHint')).to_be_enabled()
    assert len(moves)==1
