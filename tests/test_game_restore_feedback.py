"""Delayed auth/session reads: real Chromium, disposable local account, no game writes."""
import chess
import pytest
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
    expect(page.locator('#newGame')).to_be_enabled()
    reads=[];writes=[]
    page.route('**/api/game',lambda r:reads.append(r))
    page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
    def wait_reads(count):
        for _ in range(100):
            if len(reads)>=count:break
            page.wait_for_timeout(20)
        assert len(reads)==count
    page.evaluate('void resumeGame()');wait_reads(1)
    page.evaluate('void resumeGame()');page.wait_for_timeout(100)
    # Same-owner concurrent reads intentionally share one transport request.
    assert len(reads)==1
    reads[0].fulfill(json=restored())
    expect(page.locator('#gameStatus')).to_contain_text('불러왔습니다')
    assert page.evaluate('game.session_id')=='saved-game'
    page.evaluate('void resumeGame()');wait_reads(2)
    # Different identities have distinct requests. Release the new owner first.
    page.evaluate("token='other-account';game=null;void resumeGame();")
    wait_reads(3)
    other={**restored(),'session_id':'other-game'}
    reads[2].fulfill(json=other)
    expect(page.locator('#gameStatus')).to_contain_text('불러왔습니다')
    reads[1].fulfill(json={'active':False});page.wait_for_timeout(100)
    assert page.evaluate('game.session_id')=='other-game'
    expect(page.locator('#gameStatus')).to_contain_text('불러왔습니다')
    page.evaluate('void resumeGame()');wait_reads(4)
    page.evaluate("token='third-account';game=null;gameRestoreFeedback('pending','계정 C 확인 중');")
    reads[3].fulfill(json=restored());page.wait_for_timeout(100)
    assert page.evaluate('game') is None
    expect(page.locator('#gameStatus')).to_have_text('계정 C 확인 중')
    assert not writes

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


@pytest.mark.parametrize('operation',['move','new'])
def test_pending_game_request_then_real_account_login_restores_b_without_waiting_for_a(page,site,operation):
    import uuid
    from test_qa_browser import square
    open_page(page,site);page.evaluate("tab('play')")
    page.evaluate("b=>showGame({...b,session_id:'account-a'},'A 대국')",restored()['board'])
    moves=[];page.route('**/api/game/'+operation,lambda r:moves.append(r))
    if operation=='move':
        square(page,'gameBoard','g1').click();square(page,'gameBoard','f3').click()
    else:
        page.locator('#gameSettings > summary').click();page.locator('#newGame').click()
    page.wait_for_function('gameBusy')
    for _ in range(100):
        if moves:break
        page.wait_for_timeout(20)
    assert len(moves)==1
    # B is a real new local account. The existing login handler must release A's busy ownership.
    code='RESTORE-'+uuid.uuid4().hex[:12].upper();pin='local-test-pin'
    b=page.request.post(site[0]+'/api/register',data={'code':code,'pin':pin}).json()
    page.evaluate("tab('profile/account')")
    page.get_by_role('button',name='계정 전환',exact=True).click()
    page.locator('#codeField').fill(code);page.locator('#pinField').fill(pin)
    page.locator('#signin').click()
    page.wait_for_function("code=>user?.code===code&&!gameBusy&&gameRestoreState==='ready'",arg=code)
    assert page.evaluate('game') is None
    # Release A after B has fully restored: neither board nor busy state may change.
    moves[0].fulfill(json={'board':restored()['board'],'session_id':'account-a','clock':None})
    page.wait_for_timeout(150)
    assert page.evaluate('game') is None
    assert page.evaluate('gameBusy') is False
    page.evaluate("tab('play')")
    expect(page.locator('#newGame')).to_be_enabled()
    page.unroute('**/api/game/'+operation)
    # B can start its own disposable local game; A's original server state is not written here.
    if not page.locator('#gameSettings').evaluate('(e)=>e.open'):page.locator('#gameSettings > summary').click()
    page.locator('#aiLevel').select_option('1');page.locator('#newGame').click()
    page.wait_for_function("game&&!gameBusy&&game.session_id!=='account-a'")
