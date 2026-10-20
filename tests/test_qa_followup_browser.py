"""S3/S4 UI regression tests. Controlled API fixtures in real Chromium, not live QA."""
import pytest
from playwright.sync_api import expect
from test_qa_browser import page, site, open_page, RESULT, START

OLD = dict(RESULT, stage='이전 진단', index=271)
NEW = dict(RESULT, stage='새 진단', index=350)
QUESTION = dict(active=True, phase='questions', index=0, domain='전술',
                question=dict(id=0,fen=START,legal=['e2e4'],difficulty=1,description='새 문제'))
FEEDBACK = dict(active=True,phase='feedback',feedback=dict(correct=True,domain='전술',
    difficulty=1,seconds=1,points=100,original_fen=START,answer_fen=START,answer='e2e4'))


def previous_result(page,site):
    page.route('**/api/v8/assessment/status',lambda r:r.fulfill(json={'active':False,'recent':OLD}))
    page.route('**/api/v8/assessment/history',lambda r:r.fulfill(json={'latest':OLD,'history':[]}))
    page.route('**/api/v8/recommendations',lambda r:r.fulfill(json={'ready':True,'courses':[{'id':'quietMove','reason':'이전 추천'}]}))
    open_page(page,site)
    page.evaluate("tab('assessment')")
    expect(page.locator('#v8ScoreSummary')).to_contain_text('271점')
    expect(page.locator('#v8RecommendationList')).to_contain_text('이전 추천')


def game_board(page,color='white'):
    return page.evaluate("color => ({squares:fromFen(chessStart),turn:color,legal:[],is_over:false})",color)


@pytest.mark.parametrize('phase',['questions','feedback','game'])
def test_s3_active_restore_clears_previous_result(page,site,phase):
    previous_result(page,site)
    state=QUESTION if phase=='questions' else FEEDBACK if phase=='feedback' else dict(
        active=True,phase='game',board=game_board(page),clock={'white_ms':40000,'black_ms':600000})
    page.route('**/api/v8/assessment/status',lambda r:r.fulfill(json=state))
    page.evaluate("tab('home');tab('assessment')")
    expect(page.locator('#v8ScoreSummary')).to_be_empty()
    expect(page.locator('#v8RecommendationList')).to_be_empty()
    expect(page.locator('#v8Outcome')).not_to_contain_text('271')
    # Account history remains available, without repopulating current results.
    page.evaluate("tab('profile')")
    expect(page.locator('#v8ProfileResult')).to_contain_text('271')
    page.wait_for_timeout(100)
    expect(page.locator('#v8RecommendationList')).to_be_empty()
    page.route('**/api/v8/assessment/status',lambda r:r.fulfill(json={'active':False,'recent':NEW}))
    page.evaluate("tab('assessment')")
    expect(page.locator('#v8ScoreSummary')).to_contain_text('350점')
    expect(page.locator('#v8ScoreSummary')).not_to_contain_text('271점')


def test_s3_new_start_discards_late_recommendations(page,site):
    previous_result(page,site)
    pending=[]
    page.route('**/api/v8/recommendations',lambda r:pending.append(r))
    page.evaluate("tab('profile')")
    page.wait_for_timeout(150)
    assert pending
    page.evaluate("tab('assessment')")
    page.route('**/api/v8/assessment/start',lambda r:r.fulfill(json=QUESTION))
    page.locator('#v8Start').click()
    expect(page.locator('#testProgress')).to_contain_text('문항 1 / 49')
    for route in pending:
        route.fulfill(json={'ready':True,'courses':[{'id':'quietMove','reason':'늦은 이전 추천'}]})
    page.wait_for_timeout(100)
    expect(page.locator('#v8ScoreSummary')).to_be_empty()
    expect(page.locator('#v8RecommendationList')).to_be_empty()


@pytest.mark.parametrize('color,label',[('white','백 ♔ vs AI ♚'),('black','흑 ♚ vs AI ♔')])
@pytest.mark.parametrize('entry',['new','resume','timeout'])
def test_s4_matchup_uses_actual_game_color(page,site,color,label,entry):
    open_page(page,site)
    board=game_board(page,color)
    page.evaluate("tab('play')")
    if entry=='new':
        page.route('**/api/game/new',lambda r:r.fulfill(json={'board':board,'player_color':color,'message':'새 대국'}))
        page.locator('#playerColor').select_option(color)
        page.locator('#newGame').click()
    else:
        response={'active':True,'board':board,'player_color':color}
        if entry=='timeout':response.update(active=False,timeout=True,result='loss',clock={'mode':'bullet','white_ms':60000,'black_ms':0})
        page.route('**/api/game',lambda r:r.fulfill(json=response))
        page.evaluate('() => resumeGame()')
    expect(page.locator('#gameMatchup')).to_have_text(label)
    # Selecting the next game's color must not relabel the existing game.
    if not page.locator('#gameSettings').evaluate('(e)=>e.open'):page.locator('#gameSettings > summary').click()
    page.locator('#playerColor').select_option('black' if color=='white' else 'white')
    expect(page.locator('#gameMatchup')).to_have_text(label)
    if entry=='new':
        page.route('**/api/game/new',lambda r:r.fulfill(status=503,json={'detail':'시작 실패'}))
        page.locator('#newGame').click()
        expect(page.locator('#gameStatus')).to_contain_text('시작 실패')
        expect(page.locator('#gameMatchup')).to_have_text(label)

        other='black' if color=='white' else 'white'
        page.route('**/api/game/new',lambda r:r.fulfill(json={'board':game_board_data,'player_color':other,'message':'색상 전환'}))
        game_board_data=game_board(page,other)
        page.locator('#newGame').click()
        expect(page.locator('#gameMatchup')).to_have_text('흑 ♚ vs AI ♔' if other=='black' else '백 ♔ vs AI ♚')
