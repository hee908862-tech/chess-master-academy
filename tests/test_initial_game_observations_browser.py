"""Local Chromium; observation HTTP doubles with real rule-generated payloads.
Mobile viewports are emulation. Training preservation uses the disposable local API.
"""
import pytest
import chess
from pathlib import Path
from playwright.sync_api import expect
from test_qa_browser import site, page
from game_observations import observe_game


def payload():
    game = {'initial_fen':'7k/5K2/6Q1/8/8/8/8/8 w - - 0 1',
            'moves':['g6g7'],'color':'white','difficulty':3,'time_mode':'rapid'}
    return observe_game(game,'browser-observation')


def setup(page,site):
    data=payload()
    page.route('**/api/games/analysis',lambda r:r.fulfill(json={
        'games':[{'game_key':'browser-observation','at':'2026-10-23','color':'white',
                  'status':'not_started','observations_available':True}],
        'average':None,'representative_games':0,
        'app_rating':{'version':'test','series':{}},'rating_reason':'환산하지 않음'}))
    page.goto(site[0]);page.wait_for_function('!!token && !!window.cmaGameObservations')
    page.evaluate("cmaNavigation.go('profile')")
    page.get_by_text('대국 지표 · 내 수 품질과 앱 내부 레이팅',exact=True).click()
    return data


@pytest.mark.parametrize('width,height',[(1366,768),(360,800),(390,844)])
def test_unanalysed_owned_observation_board_help_and_no_writes(page,site,width,height):
    page.set_viewport_size({'width':width,'height':height})
    data=setup(page,site);requests=[];writes=[]
    if width in (360,390):
        data['conditions']['assistance_complete']=True
        data['rows'][0]['assistance'].update(known=True,hint_viewed=width==390,undo_replayed=False)
    def respond(route):
        assert route.request.headers.get('authorization','').startswith('Bearer ')
        requests.append(route.request.method);route.fulfill(json=data)
    page.route('**/api/games/observations/*',respond)
    page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
    page.locator('#gamePerformance').get_by_role('button',name='이 대국의 실전 장면 보기').click()
    box=page.locator('#gamePerformance .game-observations')
    expect(box).to_contain_text('기회 1묶음 · 실행 1')
    expect(page.locator('#gamePerformance')).to_contain_text('분석 전')
    box.get_by_text('1번째 반수 · 즉시 메이트 실행',exact=True).click()
    help_label='기록 미확인' if width==1366 else '힌트 또는 무르기 이력 있음' if width==390 else '이 착수의 도움 이력 없음'
    expect(box).to_contain_text('도움 상태: '+help_label)
    expect(box.locator('.board [aria-label^="g6 백 퀸"]')).to_have_count(1)
    expect(box.locator('.board [aria-label^="g7 빈 칸"]')).to_have_count(1)
    box.get_by_role('button',name='실제 내 수 이후',exact=True).click()
    expect(box.locator('.board [aria-label^="g7 백 퀸"]')).to_have_count(1)
    expect(box.locator('.board [aria-label^="g6 빈 칸"]')).to_have_count(1)
    box.get_by_role('button',name='원래 위치',exact=True).click()
    expect(box.locator('.board [aria-label^="g6 백 퀸"]')).to_have_count(1)
    assert requests==['GET'] and writes==[]
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    if width==390:
        Path('/tmp/cma-initial-captures').mkdir(exist_ok=True)
        box.screenshot(path='/tmp/cma-initial-captures/game-observations-390.png')


def test_late_observation_response_is_ignored_after_identity_change(page,site):
    data=setup(page,site);pending=[]
    page.route('**/api/games/observations/*',lambda r:pending.append(r))
    page.locator('#gamePerformance').get_by_role('button',name='이 대국의 실전 장면 보기').click()
    page.wait_for_function("document.querySelector('.game-observations')?.textContent.includes('확인 중')")
    assert len(pending)==1
    page.evaluate("token='isolated-other-identity'")
    pending[0].fulfill(json=data)
    page.wait_for_timeout(150)
    expect(page.locator('.game-observations')).to_have_count(0)


def test_observation_training_link_preserves_existing_local_active(page,site):
    data=setup(page,site)
    page.route('**/api/games/observations/*',lambda r:r.fulfill(json=data))
    active=page.evaluate("api('/learning/start','POST',{fresh:true,category:'mate',mode:'practice'})")
    before=page.evaluate("api('/learning/dashboard')")
    assert before['active']['session_id']==active['session_id']
    writes=[];page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
    page.locator('#gamePerformance').get_by_role('button',name='이 대국의 실전 장면 보기').click()
    page.locator('.game-observations').get_by_role('button',name='관련 메이트 기술 연습').click()
    expect(page.locator('#learningMessage')).to_contain_text('진행 중인 훈련을 보존했습니다')
    board=chess.Board(active['fen']);names={1:'폰',2:'나이트',3:'비숍',4:'룩',5:'퀸',6:'킹'}
    expected=[]
    for square in chess.SQUARES:
        piece=board.piece_at(square)
        expected.append(chess.square_name(square)+' '+(('백 ' if piece.color else '흑 ')+names[piece.piece_type] if piece else '빈 칸'))
    actual=page.locator('#learningBoard .sq').evaluate_all("ns=>ns.map(n=>n.getAttribute('aria-label').split(' ·')[0])")
    assert sorted(actual)==sorted(expected)
    assert page.evaluate("api('/learning/dashboard')")['active']==before['active']
    assert not writes


@pytest.mark.parametrize('change',['identity','new_game'])
def test_finished_game_observation_dom_is_discarded_on_context_change(page,site,change):
    data=setup(page,site)
    page.route('**/api/games/observations/*',lambda r:r.fulfill(json=data))
    page.evaluate("game={is_over:true,session_id:'local-old'};document.getElementById('turnIndicator').textContent='local old complete'")
    page.evaluate("cmaGameObservations.open('browser-observation',document.getElementById('gameObservationNext'))")
    expect(page.locator('#gameObservationNext .game-observations')).to_contain_text('기회 1묶음')
    if change=='identity':
        page.evaluate("token='isolated-other-identity';document.getElementById('userBadge').textContent='다른 테스트 계정'")
    else:
        page.evaluate("game={is_over:false,session_id:'local-new'};document.getElementById('turnIndicator').textContent='local new game'")
    expect(page.locator('#gameObservationNext .game-observations')).to_have_count(0)


def test_claimable_fifty_move_draw_does_not_hide_verified_mate():
    g={'initial_fen':'7k/5K2/6Q1/8/8/8/8/8 w - - 99 50',
       'moves':['g6g7'],'color':'white'}
    result=observe_game(g,'claimable')
    assert result['status']=='complete' and result['summary']['executed']==1


def test_independent_cards_and_latest_request_per_card(page,site):
    setup(page,site);pending=[]
    page.route('**/api/games/observations/*',lambda r:pending.append(r))
    page.evaluate("""()=>{for(const id of ['observationCardA','observationCardB']){
      const host=document.createElement('article');host.id=id;document.getElementById('gamePerformance').append(host);}
      void cmaGameObservations.open('first',document.getElementById('observationCardA'));
      void cmaGameObservations.open('second',document.getElementById('observationCardB'));} """)
    page.wait_for_timeout(100);assert len(pending)==2
    a=payload();a['note']='독립 카드 A 응답'
    b=payload();b['note']='독립 카드 B 응답'
    pending[1].fulfill(json=b);pending[0].fulfill(json=a)
    expect(page.locator('#observationCardB')).to_contain_text(b['note'])
    expect(page.locator('#observationCardA')).to_contain_text(a['note'])
    page.evaluate("""()=>{const parent=document.getElementById('observationCardA');
      void cmaGameObservations.open('older',parent);void cmaGameObservations.open('newer',parent);} """)
    page.wait_for_timeout(100);assert len(pending)==4
    latest=payload();latest['note']='같은 카드 최신 응답'
    pending[3].fulfill(json=latest);pending[2].fulfill(json=a)
    expect(page.locator('#observationCardA')).to_contain_text(latest['note'])
    expect(page.locator('#observationCardA')).not_to_contain_text(a['note'])
    expect(page.locator('#observationCardB')).to_contain_text(b['note'])
    board_ids=page.locator('#observationCardA .board, #observationCardB .board').evaluate_all('ns=>ns.map(n=>n.id)')
    assert len(board_ids)==len(set(board_ids))==2
    page.evaluate("""()=>{void cmaGameObservations.open('again-a',document.getElementById('observationCardA'));
      void cmaGameObservations.open('again-b',document.getElementById('observationCardB'));} """)
    page.wait_for_timeout(100);assert len(pending)==6
    page.evaluate("token='isolated-other-identity';document.getElementById('userBadge').textContent='다른 테스트 계정'")
    pending[5].fulfill(json=b);pending[4].fulfill(json=a)
    expect(page.locator('.game-observations')).to_have_count(0)
