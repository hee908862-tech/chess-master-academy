"""Game layout: real local game plus explicit controlled edge states, no production writes."""
import json
from pathlib import Path
import chess
from playwright.sync_api import expect
from test_qa_browser import page, site, open_page, square
from test_board_interaction import board_data, setup_wait, play_initial, reply

CAPTURES=Path('/tmp/cma-game-focus-evidence')

def test_actual_game_geometry_hint_undo_and_navigation(page,site):
    open_page(page,site)
    # site owns a disposable SQLite account; its init token also survives reload.
    page.evaluate("tab('play')")
    for w,h in [(1280,720),(1366,768),(1165,747)]:
        page.set_viewport_size(dict(width=w,height=h))
        box=page.locator('#gameBoard').bounding_box()
        assert box['y']+box['height']<=h
    page.locator('#aiLevel').select_option('1')
    page.locator('#newGame').click()
    page.wait_for_function('game&&!gameBusy')
    expect(page.locator('#gameSettings')).not_to_have_attribute('open','')
    CAPTURES.mkdir(exist_ok=True)
    measurements={}
    for w,h in [(360,800),(390,844),(1280,720),(1366,768)]:
        page.set_viewport_size(dict(width=w,height=h));page.evaluate('scrollTo(0,0)')
        boxes={}
        for id in ['gameBoard','turnIndicator','gameClock','v7Hint','v7Undo']:
            r=page.locator('#'+id).bounding_box();boxes[id]=r
            assert r['x']>=0 and r['y']>=0 and r['x']+r['width']<=w+1 and r['y']+r['height']<=h, (w,h,id,r)
        assert boxes['v7Hint']['height']>=44 and boxes['v7Undo']['height']>=44
        assert abs(boxes['gameBoard']['height']-boxes['gameBoard']['width'])<1
        measurements[str(w)]=boxes
        page.screenshot(path=str(CAPTURES/f'active-{w}.png'))
    (CAPTURES/'geometry.json').write_text(json.dumps(measurements,indent=2))
    page.locator('#v7Hint').click();expect(page.locator('#gameStatus')).to_contain_text('추천:')
    square(page,'gameBoard','e2').click();square(page,'gameBoard','e4').click()
    page.wait_for_function('game.ply>=2&&!gameBusy',timeout=20000)
    page.locator('#v7Undo').click();expect(page.locator('#gameStatus')).to_contain_text('되돌렸습니다')
    assert page.evaluate('game.ply')==0
    square(page,'gameBoard','e2').click()
    before=page.evaluate('({fen:game.fen,selected:selectedGame})')
    page.locator('.nav [data-tab=learn]').click();page.keyboard.press('Escape')
    assert page.evaluate('({fen:game.fen,selected:selectedGame})')==before
    assert page.evaluate("document.querySelector('.view.active').id")=='play'
    page.evaluate("tab('play')")
    assert page.evaluate('({fen:game.fen,selected:selectedGame})')==before
    page.set_viewport_size(dict(width=390,height=844));page.locator('#gameTools > summary').click()
    page.evaluate('scrollTo(0,document.body.scrollHeight)')
    page.evaluate("tab('home')")
    assert page.evaluate('scrollY')==0
    assert page.evaluate("document.activeElement.closest('.view').id")=='home'
    page.evaluate("tab('play')")
    assert page.evaluate('game.fen')==before['fen']
    page.locator('#moreNavigation').click()
    page.locator('#moreNavigationDialog').get_by_role('button',name='기록',exact=True).click()
    page.wait_for_timeout(50)
    assert page.evaluate('scrollY')==0
    assert page.evaluate("document.activeElement.closest('.view').id")=='profile'
    page.evaluate("tab('play')")
    page.locator('#gameSettings > summary').click()
    page.locator('#playerColor').select_option('black');page.locator('#timeMode').select_option('rapid')
    page.locator('#newGame').click();page.wait_for_function('game&&playerColor==="black"&&!gameBusy',timeout=20000)
    expect(page.locator('#gameBoard .sq').first).to_have_attribute('aria-label',__import__('re').compile('h1 '))
    expect(page.locator('#gameClock')).not_to_contain_text('무제한')
    saved=page.evaluate('game.fen');page.reload();page.wait_for_function('game&&!gameBusy');page.evaluate("tab('play')")
    assert page.evaluate('game.fen')==saved
    page.screenshot(path=str(CAPTURES/'black-resumed.png'))


def test_short_zoom_rotation_keyboard_and_promotion(page,site):
    open_page(page,site);page.evaluate("tab('play')")
    for w,h in [(844,390),(1280,600),(320,640),(640,360)]:
        page.set_viewport_size(dict(width=w,height=h))
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.locator('#v7Hint').scroll_into_view_if_needed()
        r=page.locator('#v7Hint').bounding_box();assert 0<=r['y'] and r['y']+r['height']<=h
        CAPTURES.mkdir(exist_ok=True);page.screenshot(path=str(CAPTURES/f'scroll-{w}.png'))
    # 200% CSS zoom, checked separately from browser-native zoom / physical mobile.
    page.set_viewport_size(dict(width=1280,height=720));page.evaluate("document.documentElement.style.zoom='2'")
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.locator('#v7Undo').scroll_into_view_if_needed();page.screenshot(path=str(CAPTURES/'zoom-200.png'))
    page.evaluate("document.documentElement.style.zoom='1'")
    page.set_viewport_size(dict(width=360,height=800))
    board=board_data(chess.Board('7k/P7/8/8/8/8/8/4K3 w - - 0 1'))
    page.evaluate("b=>{playerColor='white';showGame({...b,session_id:'edge'},'승격 선택 검사');}",board)
    square(page,'gameBoard','a7').focus();page.keyboard.press('Enter');square(page,'gameBoard','a8').focus();page.keyboard.press('Enter')
    expect(page.locator('#cmaPromotionModal')).to_be_visible()
    page.screenshot(path=str(CAPTURES/'promotion.png'))
    page.evaluate("tab('play')");expect(page.locator('#cmaPromotionModal')).to_be_visible()
    page.keyboard.press('Escape');expect(page.locator('#cmaPromotionModal')).to_be_hidden()
    assert page.evaluate('game.fen')==board['fen']


def test_wait_failure_check_clock_and_end_keep_actions(page,site):
    open_page(page,site);page.set_viewport_size(dict(width=390,height=844));page.evaluate("tab('play')")
    board=board_data(chess.Board('4k3/8/8/8/8/8/4r3/4K3 w - - 0 1'))
    page.evaluate("b=>{playerColor='white';showGame({...b,session_id:'edge',ply:2},'체크: 킹을 안전하게 이동하세요.');setGameClock({white_ms:60000,black_ms:60000});gameBusy=true;cmaGameActions();}",board)
    expect(page.locator('#v7Hint')).to_be_disabled();expect(page.locator('#v7Undo')).to_be_disabled()
    expect(page.locator('#gameActionReason')).to_contain_text('응답')
    page.screenshot(path=str(CAPTURES/'waiting-check.png'))
    page.evaluate('gameBusy=false;cmaGameActions()')
    page.route('**/api/v7/game/hint*',lambda r:r.fulfill(status=503,json={'detail':'통신 실패 검사'}))
    page.locator('#v7Hint').click();expect(page.locator('#gameStatus')).to_contain_text('통신 실패 검사')
    expect(page.locator('#v7Hint')).to_be_enabled()
    page.evaluate("game.is_over=true;drawGame();document.getElementById('turnIndicator').textContent='대국 종료';")
    expect(page.locator('#v7Hint')).to_be_visible();expect(page.locator('#v7Hint')).to_be_disabled()
    expect(page.locator('#v7Undo')).to_be_visible();expect(page.locator('#v7Undo')).to_be_disabled()


def test_menu_escape_preserves_waiting_premove(page,site):
    name,requests,task=setup_wait(page,site,'game')
    page.get_by_role('checkbox',name='프리무브 gameBoard',exact=True).check()
    play_initial(page,name);square(page,name,'g1').click();square(page,name,'f3').click()
    page.locator('#gameTools > summary').click()
    expect(page.locator('#gamePremoveStatus')).to_contain_text('g1 → f3')
    page.locator('.nav [data-tab=learn]').click();page.keyboard.press('Escape')
    expect(page.locator('#gameBoard .premove-arrow')).to_have_count(1)
    page.evaluate("tab('play')")
    expect(page.locator('#gameBoard .premove-arrow')).to_have_count(1)
    b=chess.Board();b.push_uci('e2e4');b.push_uci('e7e5');reply(requests[0],'game',b,task)
    for _ in range(100):
        if len(requests)==2:break
        page.wait_for_timeout(50)
    assert len(requests)==2
    b.push_uci('g1f3');reply(requests[1],'game',b,task,True)
