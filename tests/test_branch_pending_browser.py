"""Durable pending exposure is separate from original grade/history; local browser."""
from playwright.sync_api import expect
from test_branch_matrix_browser import mount,move,FEN
from test_qa_browser import page,site


def test_failed_exposure_survives_reload_and_retries_before_measured_start(page,site):
    page.route('**/api/study/exposure',lambda r:r.fulfill(status=503,json={'detail':'테스트 저장 실패'}))
    d=mount(page,site);move(d,'f5','f4')
    assert page.evaluate('cmaExplore.flushExposures()') is False
    expect(d).to_contain_text('노출 이력 저장 미확인')
    assert page.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('cma_branch_pending_v1:')).some(k=>JSON.parse(localStorage[k]).pending.length>=2)")
    assert page.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('cma_branch_pending_v1:')).every(k=>/^cma_branch_pending_v1:[0-9a-f]{64}$/.test(k)&&!localStorage[k].includes(token))")
    page.reload();page.wait_for_function('!!token && !!window.cmaExplore')
    # No branch has been reopened: the start guard still restores failed pending history.
    assert page.evaluate('cmaExplore.flushExposures()') is False
    page.unroute('**/api/study/exposure')
    assert page.evaluate('cmaExplore.flushExposures()') is True
    assert page.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('cma_branch_pending_v1:')).length===0")


def test_pending_owner_is_not_assigned_to_different_identity(page,site):
    page.route('**/api/study/exposure',lambda r:r.fulfill(status=503,json={'detail':'테스트 저장 실패'}))
    mount(page,site);assert page.evaluate('cmaExplore.flushExposures()') is False
    page.evaluate("window.oldBranchIdentity=token;token='separate-test-identity';document.querySelector('#userBadge').textContent='다른 테스트 정체성'")
    page.route('**/api/me',lambda r:r.fulfill(json={'code':'separate-confirmed-test-owner'}))
    requests=[];page.on('request',lambda r:requests.append(r.url) if r.url.endswith('/api/study/exposure') else None)
    assert page.evaluate('cmaExplore.flushExposures()') is True
    assert requests==[]
    page.evaluate("token=window.oldBranchIdentity;delete window.oldBranchIdentity;document.querySelector('#userBadge').textContent='원래 테스트 정체성'")
    assert page.evaluate('cmaExplore.flushExposures()') is False


def test_storage_failure_blocks_measured_start_but_local_moves_work(page,site):
    mount(page,site)
    page.evaluate("()=>{window.originalSetItem=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(String(k).startsWith('cma_branch_pending_v1:'))throw new DOMException('test quota','QuotaExceededError');return originalSetItem.call(this,k,v)}}")
    d=page.locator('.branch-explorer[data-board="matrixSource"]');move(d,'f5','f4')
    expect(d).to_contain_text('독립 평가 시작을 보류')
    assert page.evaluate('cmaExplore.flushExposures()') is False
    expect(d.locator('[role=status]').filter(has_text='분기')).to_contain_text('분기 1반수')
    page.evaluate('Storage.prototype.setItem=window.originalSetItem;delete window.originalSetItem')
    assert page.evaluate('cmaExplore.flushExposures()') is True


def test_rotated_identity_restores_stable_owner_pending_before_cached_me_ready(page,site):
    page.route('**/api/study/exposure',lambda r:r.fulfill(status=503,json={'detail':'테스트 저장 실패'}))
    mount(page,site);page.wait_for_function('summaryOwner===token && !!user?.code')
    assert page.evaluate('cmaExplore.flushExposures()') is False
    owner=page.evaluate('user.code')
    page.evaluate("token='rotated-test-token';summaryOwner=null;user=null;document.querySelector('#userBadge').textContent='계정 재확인'")
    page.route('**/api/me',lambda r:r.fulfill(json={'code':owner}))
    # A new token namespace is empty, but authenticated owner lookup restores old pending.
    assert page.evaluate('cmaExplore.flushExposures()') is False
    page.unroute('**/api/study/exposure')
    page.route('**/api/study/exposure',lambda r:r.fulfill(json={'recorded':len(r.request.post_data_json['fens']),'overflow':False}))
    assert page.evaluate('cmaExplore.flushExposures()') is True


def test_no_pending_history_does_not_add_me_dependency(page,site):
    page.goto(site[0]);page.wait_for_function('!!token && !!window.cmaExplore')
    page.evaluate('summaryOwner=null;user=null')
    reads=[]
    def fail_me(route):
        reads.append(1);route.fulfill(status=503,json={'detail':'테스트 계정 조회 지연'})
    page.route('**/api/me',fail_me)
    assert page.evaluate('cmaExplore.flushExposures()') is True
    assert reads==[]


def test_unknown_identity_with_prior_pending_and_me_failure_blocks(page,site):
    page.route('**/api/study/exposure',lambda r:r.fulfill(status=503,json={'detail':'테스트 저장 실패'}))
    mount(page,site);assert page.evaluate('cmaExplore.flushExposures()') is False
    page.evaluate("token='unconfirmed-rotated-token';summaryOwner=null;user=null")
    page.route('**/api/me',lambda r:r.fulfill(status=503,json={'detail':'테스트 계정 조회 지연'}))
    assert page.evaluate('cmaExplore.flushExposures()') is False


def test_unbound_original_token_pending_never_silently_moves_to_rotated_owner(page,site):
    page.route('**/api/me',lambda r:r.fulfill(status=503,json={'detail':'테스트 소유자 조회 미확인'}))
    mount(page,site)
    assert page.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('cma_branch_pending_v1:')).some(k=>JSON.parse(localStorage[k]).scope==='token'&&JSON.parse(localStorage[k]).pending.length)")
    page.evaluate("token='replacement-identity';summaryOwner=null;user=null")
    page.unroute('**/api/me');page.route('**/api/me',lambda r:r.fulfill(json={'code':'newly-confirmed-account'}))
    posts=[];page.on('request',lambda r:posts.append(r.url) if r.url.endswith('/api/study/exposure') else None)
    assert page.evaluate('cmaExplore.requireExposureSaved(document.body.appendChild(document.createElement("p")))') is False
    expect(page.locator('body')).to_contain_text('원래 로그인/게스트 정체성으로 돌아가')
    assert posts==[]


import pytest
@pytest.mark.parametrize('activity,button,status,endpoint',[
    ('training','learningVerify','learningMessage','/api/learning/start'),
    ('puzzle','v9PuzzleStart','v9PuzzleMessage','/api/v9/puzzle/start'),
    ('challenge','challengeStart','challengeStatus','/api/challenge/action'),
])
def test_failed_exposure_blocks_independent_training_and_puzzle_start(page,site,activity,button,status,endpoint):
    page.route('**/api/study/exposure',lambda r:r.fulfill(status=503,json={'detail':'테스트 저장 실패'}))
    mount(page,site);assert page.evaluate('cmaExplore.flushExposures()') is False
    if activity=='training':
        dashboard=page.evaluate("api('/learning/dashboard')");dashboard.update(active=None,path=None)
        page.route('**/api/learning/dashboard',lambda r:r.fulfill(json=dashboard))
    page.evaluate('view=>cmaNavigation.go(view)','puzzle' if activity=='challenge' else activity)
    if activity=='challenge':page.locator('#puzzleModeChallenge').click()
    expect(page.locator('#'+button)).to_be_enabled(timeout=15000)
    posts=[];page.on('request',lambda r:posts.append(r.url) if r.method=='POST' and r.url.endswith(endpoint) else None)
    page.evaluate('id=>document.getElementById(id).click()',button)
    expect(page.locator('#'+status)).to_contain_text('판정 요청 전 보류',timeout=15000)
    assert posts==[]


def test_delayed_exposure_flush_navigation_cancels_preflight(page,site):
    held=[]
    page.route('**/api/study/exposure',lambda r:held.append(r))
    mount(page,site)
    page.evaluate("window.preflightOutcome=null;void cmaExplore.requireExposureSaved('puzzleStatus').then(ok=>{window.preflightOutcome=ok})")
    page.wait_for_timeout(700)
    assert held
    page.evaluate("tab('profile')")
    for route in held:
        route.fulfill(json={'recorded':len(route.request.post_data_json['fens']),'overflow':False})
    page.wait_for_function('window.preflightOutcome!==null')
    assert page.evaluate('window.preflightOutcome') is False
