"""Local Chromium branch harness: real legal rules, no production account or engine call; separate exposure writes allowed."""
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page

FEN='8/2k5/1Np2K2/P1P2ppp/1P6/3b2P1/7P/8 b - - 0 1'


def mount(page,site,fen=FEN):
    page.goto(site[0]);page.wait_for_function('!!token && !!window.cmaExplore')
    page.evaluate('''fen=>{cmaNavigation.go('home');const h=document.createElement('section');h.id='branchMatrix';h.className='card';const b=document.createElement('div');b.id='matrixSource';b.className='board';b.dataset.fen=fen;h.append(b);document.querySelector('#home').prepend(h);drawBoard(b.id,fromFen(fen),{});cmaExplore.offer(b.id,fen);}''',fen)
    d=page.locator('.branch-explorer[data-board="matrixSource"]');d.locator(':scope > summary').focus();page.keyboard.press('Enter')
    expect(d.locator('.board .sq')).to_have_count(64)
    return d


def move(d,a,b):
    board=d.locator('.board')
    board.locator(f'[aria-label^="{a} "]').click();board.locator(f'[aria-label^="{b} "]').click()


@pytest.mark.parametrize('width,height,zoom',[(1366,768,1),(1180,650,1),(360,800,1),(390,844,1),(844,390,1),(1366,768,2)])
def test_f4_capture_branch_original_undo_and_layout(page,site,width,height,zoom):
    page.set_viewport_size({'width':width,'height':height});d=mount(page,site)
    if zoom!=1:page.evaluate('z=>document.body.style.zoom=z',zoom)
    writes=[];page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
    move(d,'f5','f4');expect(d.locator('[role=status]').filter(has_text='분기')).to_contain_text('분기 1반수')
    assert '체크' not in d.locator('[role=status]').filter(has_text='분기').inner_text()
    move(d,'g3','f4');expect(d.locator('[role=status]').filter(has_text='분기')).to_contain_text('분기 2반수')
    move(d,'g5','f4');expect(d.locator('[role=status]').filter(has_text='분기')).to_contain_text('분기 3반수')
    assert page.locator('#matrixSource').get_attribute('data-fen')==FEN
    assert all(url.endswith('/api/study/exposure') for url in writes)
    expect(d.locator('meter')).to_be_hidden()
    d.get_by_role('button',name='한 수 뒤로',exact=True).click();expect(d.locator('[role=status]').filter(has_text='분기')).to_contain_text('분기 2반수')
    d.get_by_role('button',name='원래 해설 위치로',exact=True).click();expect(d.locator('[role=status]').filter(has_text='분기')).to_contain_text('분기 0반수')
    assert d.locator('.board').get_attribute('data-fen')==FEN
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    # Controls remain keyboard-focusable at narrow/zoomed sizes; scrolling is allowed.
    for control in d.locator('button.btn:visible:enabled').all():
        control.focus();expect(control).to_be_focused()
    if width==390:page.screenshot(path='/tmp/continuous-branch-390.png',full_page=True)


def test_legal_en_passant_right_and_castling_are_retained(page,site):
    fen='r3k2r/8/8/3pP3/8/8/8/R3K2R w KQkq d6 0 1';d=mount(page,site,fen)
    move(d,'e5','d6');expect(d.locator('[role=status]').filter(has_text='분기')).to_contain_text('분기 1반수')
    assert 'P' not in d.locator('.board [aria-label^="d5 "]').get_attribute('aria-label')
    d.get_by_role('button',name='한 수 뒤로',exact=True).click()
    assert d.locator('.board').get_attribute('data-fen').split()[2:4]==['KQkq','d6']
    move(d,'e1','g1');expect(d.locator('[role=status]').filter(has_text='분기')).to_contain_text('O-O')
    assert page.locator('#matrixSource').get_attribute('data-fen')==fen


def test_pending_evaluation_never_blocks_move_or_applies_stale_result(page,site):
    d=mount(page,site);pending=[]
    page.route('**/api/study/position',lambda route:pending.append(route))
    d.get_by_role('button',name='현재 위치 평가',exact=True).click()
    expect(d.locator('[aria-live=polite]')).to_contain_text('분석 중')
    move(d,'f5','f4')
    expect(d.locator('[role=status]').filter(has_text='분기')).to_contain_text('분기 1반수')
    assert len(pending)==1
    # The move aborts the old request; no delayed old-position evaluation is shown.
    expect(d.locator('[aria-live=polite]')).to_contain_text('미분석')
    assert page.locator('#matrixSource').get_attribute('data-fen')==FEN


def test_exposure_failure_is_visible_and_explicit_retry_confirms_separate_history(page,site):
    page.route('**/api/study/exposure',lambda r:r.fulfill(status=503,json={'detail':'테스트 노출 저장 미확인'}))
    d=mount(page,site)
    assert page.evaluate('cmaExplore.flushExposures()') is False
    expect(d).to_contain_text('노출 이력 저장 미확인')
    move(d,'f5','f4');expect(d.locator('[role=status]').filter(has_text='분기')).to_contain_text('분기 1반수')
    page.unroute('**/api/study/exposure')
    d.get_by_role('button',name='노출 이력 저장 다시 확인',exact=True).click()
    expect(d).to_contain_text('탐색 노출 이력 저장 확인 · 원본 점수 불변')
    assert page.evaluate('cmaExplore.flushExposures()') is True
    assert page.locator('#matrixSource').get_attribute('data-fen')==FEN
