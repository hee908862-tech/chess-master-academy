"""Delayed auth/session reads: real Chromium, disposable local account, no game writes."""
import chess
from playwright.sync_api import expect
from test_qa_browser import page, site, open_page
from test_board_interaction import board_data

def restored():
    b=chess.Board();b.push_uci('e2e4');b.push_uci('c7c6')
    return dict(active=True,session_id='saved-game',player_color='white',board={**board_data(b),'ply':2},clock=None)

def test_auth_then_session_delay_and_failure_retry(page,site):
    auth=[];games=[];writes=[]
    page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
    page.route('**/api/me',lambda r:auth.append(r))
    page.route('**/api/game',lambda r:games.append(r))
    page.goto(site[0]);page.evaluate("tab('play')")
    expect(page.locator('#gameStatus')).to_contain_text('계정을 확인')
    expect(page.locator('#newGame')).to_be_disabled()
    expect(page.locator('#gameBoard')).to_be_hidden()
    page.screenshot(path='/tmp/game-restore-pending.png')
    # Auth response is real; release every concurrent summary read too.
    for r in auth:r.continue_()
    page.unroute('**/api/me')
    expect(page.locator('#gameStatus')).to_contain_text('저장된 대국을 확인')
    page.wait_for_timeout(100)
    assert games
    games.pop(0).fulfill(status=503,json={'detail':'읽기 실패'})
    expect(page.locator('#gameStatus')).to_contain_text('대국 조회 실패')
    expect(page.locator('#newGame')).to_be_disabled()
    page.locator('#gameRestoreRetry').click()
    expect(page.locator('#gameStatus')).to_contain_text('저장된 대국을 확인')
    page.wait_for_timeout(150)
    games.pop(0).fulfill(json=restored())
    expect(page.locator('#gameStatus')).to_contain_text('불러왔습니다')
    expect(page.locator('#gameBoard')).to_be_visible()
    expect(page.locator('#gameRestoreRetry')).to_be_hidden()
    assert page.evaluate('game.fen')==restored()['board']['fen']
    assert not writes
    for width,height in [(390,844),(1280,720)]:
        page.set_viewport_size(dict(width=width,height=height))
        page.screenshot(path=f'/tmp/game-restored-{width}.png')

def test_stale_read_cannot_replace_newer_read_or_account(page,site):
    open_page(page,site);page.evaluate("tab('play')")
    reads=[];page.route('**/api/game',lambda r:reads.append(r))
    page.evaluate('void resumeGame()');page.wait_for_timeout(100)
    page.evaluate('void resumeGame()');page.wait_for_timeout(100)
    reads[1].fulfill(json=restored())
    expect(page.locator('#gameStatus')).to_contain_text('불러왔습니다')
    reads[0].fulfill(json={'active':False})
    page.wait_for_timeout(100)
    assert page.evaluate('game.session_id')=='saved-game'
    page.evaluate('void resumeGame()');page.wait_for_timeout(100)
    page.evaluate("token='other-account';game=null;gameRestoreFeedback('pending','계정 B 확인 중');")
    reads[2].fulfill(json=restored());page.wait_for_timeout(100)
    assert page.evaluate('game') is None
    expect(page.locator('#gameStatus')).to_have_text('계정 B 확인 중')

def test_auth_failure_is_unknown_not_empty_and_retry_recovers(page,site):
    page.route('**/api/me',lambda r:r.fulfill(status=503,json={'detail':'계정 조회 실패'}))
    page.goto(site[0]);page.evaluate("tab('play')")
    expect(page.locator('#gameStatus')).to_contain_text('계정 확인 실패')
    expect(page.locator('#newGame')).to_be_disabled()
    page.unroute('**/api/me')
    page.route('**/api/game',lambda r:r.fulfill(json={'active':False}))
    page.locator('#gameRestoreRetry').click()
    expect(page.locator('#gameStatus')).to_contain_text('색상과 시간을 선택')
    expect(page.locator('#newGame')).to_be_enabled()


def test_account_switch_hides_prior_board_until_new_account_lookup(page,site):
    open_page(page,site)
    page.evaluate("b=>showGame({...b,session_id:'account-a'},'A 대국')",restored()['board'])
    reads=[];page.route('**/api/me',lambda r:reads.append(r))
    page.evaluate("token='account-b';void refresh();tab('play')")
    expect(page.locator('#gameBoard')).to_be_hidden()
    expect(page.locator('#newGame')).to_be_disabled()
    expect(page.locator('#gameStatus')).to_contain_text('계정을 확인')
    page.route('**/api/game',lambda r:r.fulfill(json={'active':False}))
    # Supply a valid local account summary, while keeping the synthetic B owner.
    summary=page.request.get(site[0]+'/api/me',headers={'Authorization':'Bearer '+site[1]}).json()
    reads[0].fulfill(json=summary)
    expect(page.locator('#gameStatus')).to_contain_text('색상과 시간을 선택')
    assert page.evaluate('game') is None
