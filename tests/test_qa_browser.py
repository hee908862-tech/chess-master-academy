"""Real Chromium UI with controlled API responses; not a production/Stockfish E2E claim.
Run after installing pytest, playwright, project requirements and Chromium.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import pytest
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
FEN = '6k1/3P1pp1/p6p/8/1p6/1P1Q3P/P5PK/2qq4 w - - 0 1'
START = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
RESULT = dict(stage='테스트',index=100,delta=None,quiz_score=10,game_score=None,
              formula='test',domains={},strengths=[],weaknesses=[])
CATALOG = dict(ready=True,count=30,levels=['중급'],themes=[
    dict(id='quietMove',name='조용한 수',counts={'입문':0,'중급':15,'고급':0}),
    dict(id='interference',name='간섭',counts={'입문':0,'중급':15,'고급':0})])
TASK = dict(id='fixture',fen=FEN,legal=['d7d8q','d7d8r','d7d8b','d7d8n'],
            rating=1400,themes=['승격'],ply=1,index=14,total=15,side='white')

@pytest.fixture(scope='module')
def site(tmp_path_factory):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
    env={**os.environ,'DATABASE_URL':'','SQLITE_FILE':str(tmp_path_factory.mktemp('db')/'test.sqlite3')}
    proc=subprocess.Popen([sys.executable,'-m','uvicorn','server:app','--port',str(port)],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    url=f'http://127.0.0.1:{port}'
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(url+'/api/health');break
            except Exception:
                if proc.poll() is not None: raise RuntimeError('test server failed')
                time.sleep(.1)
        req=urllib.request.Request(url+'/api/register',json.dumps({'code':'BROWSER-QA','pin':'test-pin-9384'}).encode(),{'Content-Type':'application/json'})
        token=json.load(urllib.request.urlopen(req))['token']
        yield url,token
    finally:
        proc.terminate();proc.wait(timeout=10)

@pytest.fixture
def page(site):
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
        page=browser.new_page()
        page.set_default_timeout(6000)
        page.add_init_script(f"localStorage.setItem('chess_token',{json.dumps(site[1])});localStorage.setItem('cma_prefs',JSON.stringify({{soundOn:false}}));")
        page.route('**/api/v9/catalog',lambda route:route.fulfill(json=CATALOG))
        page.route('**/api/v8/assessment/status',lambda route:route.fulfill(json={'active':False}))
        if os.getenv('QA_UI_REVISION'):
            html=subprocess.check_output(['git','show',os.environ['QA_UI_REVISION']+':public/index.html'],cwd=ROOT,text=True)
            page.route(site[0]+'/',lambda route:route.fulfill(body=html,content_type='text/html'))
            for name in ['app.js','v8.js','v9.js']:
                source=subprocess.check_output(['git','show',os.environ['QA_UI_REVISION']+':public/'+name],cwd=ROOT,text=True)
                def serve_source(content):
                    return lambda route:route.fulfill(body=content,content_type='application/javascript')
                page.route('**/assets/'+name,serve_source(source))
        yield page
        browser.close()

def open_page(page,site):
    page.goto(site[0]);page.wait_for_timeout(900)

def square(page,board,name):
    return page.locator(f'#{board} [aria-label^="{name} "]')


def test_recommendations_and_delayed_catalog(page,site):
    page.route('**/api/v8/recommendations',lambda r:r.fulfill(json={'ready':True,'courses':[
        {'id':i,'reason':'조용한 수와 전략 10점'} for i in ['quietMove','interference','quietMove','unknown']]}))
    # Calling before init resolves must await the catalog, preserving canonical IDs.
    page.goto(site[0])
    assert page.evaluate("() => window.cmaOpenV9Course('quietMove')")
    expect(page.locator('#v9CourseTitle')).to_have_text('조용한 수 · 난이도 선택')
    page.evaluate("tab('profile')")
    buttons=page.locator('#v8RecommendationList button')
    expect(buttons).to_have_count(3)
    expect(buttons.nth(2)).to_be_disabled()
    page.evaluate("tab('assessment')")
    buttons.nth(1).click()
    expect(page.locator('#v9CourseTitle')).to_have_text('간섭 · 난이도 선택')
    assert not page.evaluate("() => window.cmaOpenV9Course('unknown')")


def test_timeout_return_and_recent_lock(page,site):
    open_page(page,site)
    board=page.evaluate("() => ({squares:fromFen(chessStart),turn:'white',legal:[{from:'e2',to:'e4'}]})")
    response={'active':True,'phase':'game','board':board,'clock':{'white_ms':10000,'black_ms':600000}}
    page.route('**/api/v8/assessment/status',lambda r:r.fulfill(json=response))
    page.evaluate("tab('assessment')")
    expect(square(page,'testBoard','e2')).to_be_enabled()
    response.update(active=False,phase='results',result=RESULT)
    page.evaluate("tab('home');tab('assessment')")
    expect(page.locator('#testProgress')).to_have_text('50단계 종합 평가 완료')
    expect(square(page,'testBoard','e2')).to_be_disabled()
    page.evaluate("document.querySelector('#testBoard [aria-label^=e2]').click();document.querySelector('#testBoard [aria-label^=e4]').click()")
    assert page.locator('#testBoard .selected').count()==0
    response.clear();response.update(active=False,recent=RESULT)
    page.evaluate("tab('home');tab('assessment')")
    expect(page.locator('#testBoard button')).to_have_count(0)


@pytest.mark.parametrize('promotion',['q','r'])
@pytest.mark.parametrize('mobile',[False,True])
def test_original_promotion_summary(page,site,promotion,mobile):
    if mobile: page.set_viewport_size({'width':390,'height':844})
    page.route('**/api/v9/course/start',lambda r:r.fulfill(json=TASK))
    submitted=[]
    def moved(route):
        submitted.append(route.request.post_data_json['move'])
        route.fulfill(json=dict(correct=True,solved=True,done=True,completed_fen=FEN.replace('6k1/3P1pp1','3'+promotion.upper()+'2k1/5pp1'),reply=None,message='완료',correct_count=15,total=15,mastered=True))
    page.route('**/api/v9/course/move',moved)
    open_page(page,site)
    page.evaluate("tab('learn')")
    page.evaluate("() => cmaOpenV9Course('quietMove')")
    page.locator('#v9CourseStart').click()
    square(page,'v9CourseBoard','d7').click();square(page,'v9CourseBoard','d8').click()
    me=page.request.get(site[0]+'/api/me',headers={'Authorization':'Bearer '+site[1]}).json()
    me['stats'].update(courses_completed=1,solved=15,first_try_total=15,first_try_correct=15)
    page.route('**/api/me',lambda r:r.fulfill(json=me))
    page.locator('#cmaPromotionModal button').filter(has_text='퀸' if promotion=='q' else '룩').click()
    expect(page.locator('#v9CourseMessage')).to_contain_text('15/15')
    expect(page.locator('#profileLessons')).to_have_text('1')
    expect(page.locator('#homePuzzles')).to_have_text('15개')
    assert submitted==['d7d8'+promotion]
    assert page.locator('#v9CourseBoard button:not(:disabled)').count()==0
    if mobile:
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        if os.getenv('QA_SCREENSHOT_DIR'):
            page.screenshot(path=str(Path(os.environ['QA_SCREENSHOT_DIR'])/('promotion-'+promotion+'.png')),full_page=True)


@pytest.mark.parametrize('operation',['move','hint','start'])
def test_missing_session_disables_stale_board(page,site,operation):
    page.route('**/api/v9/puzzle/start',lambda r:r.fulfill(json=TASK))
    open_page(page,site);page.evaluate("tab('puzzle')")
    page.locator('#v9PuzzleStart').click()
    expect(square(page,'v9PuzzleBoard','d7')).to_be_enabled()
    page.route('**/api/v9/puzzle/'+operation,lambda r:r.fulfill(status=409,json={'detail':'현재 진행 중인 문제가 없습니다.'}))
    if operation=='move':
        square(page,'v9PuzzleBoard','d7').click();square(page,'v9PuzzleBoard','d8').click()
        page.locator('#cmaPromotionModal button').filter(has_text='룩').click()
    else: page.locator('#v9Puzzle'+operation.title()).click()
    expect(page.locator('#v9PuzzleMessage')).to_contain_text('새 문제를 시작')
    expect(page.locator('#v9PuzzleBoard button')).to_have_count(0)
    expect(page.locator('#v9PuzzleHint')).to_be_disabled()


def test_black_bullet_timeout_refreshes_summary(page,site):
    open_page(page,site)
    board=page.evaluate("() => ({squares:fromFen(chessStart),legal:[],turn:'black'})")
    page.route('**/api/game',lambda r:r.fulfill(json={'active':False,'timeout':True,'result':'loss','board':board,'clock':{'mode':'bullet','white_ms':60000,'black_ms':0}}))
    me=page.request.get(site[0]+'/api/me',headers={'Authorization':'Bearer '+site[1]}).json()
    me['stats']['games']=1
    page.route('**/api/me',lambda r:r.fulfill(json=me))
    page.evaluate("() => {playerColor='black';tab('play');return resumeGame();}")
    expect(page.locator('#profileGames')).to_have_text('1')
    expect(page.locator('#homeGames')).to_have_text('1판')
    assert page.evaluate('game.is_over')


def test_catalog_loading_waits_before_navigation(page,site):
    pending=[]
    page.route('**/api/v9/catalog',lambda r:pending.append(r))
    page.goto(site[0])
    page.evaluate("() => {window.opened=null;window.cmaOpenV9Course('interference').then(x=>window.opened=x);}")
    assert page.evaluate('window.opened') is None
    for route in pending: route.fulfill(json=CATALOG)
    page.wait_for_function('window.opened === true')
    expect(page.locator('#v9CourseTitle')).to_have_text('간섭 · 난이도 선택')


def test_assessment_failed_optimistic_move_waits_for_restore(page,site):
    open_page(page,site)
    board=page.evaluate("() => ({squares:fromFen(chessStart),turn:'white',legal:[{from:'e2',to:'e4'}]})")
    page.route('**/api/v8/assessment/status',lambda r:r.fulfill(json={'active':True,'phase':'game','board':board}))
    page.evaluate("tab('assessment')")
    expect(square(page,'testBoard','e2')).to_be_enabled()
    pending=[]
    page.route('**/api/v8/assessment/status',lambda r:pending.append(r))
    page.route('**/api/v8/assessment/game-move',lambda r:r.fulfill(status=409,json={'detail':'종료됨'}))
    square(page,'testBoard','e2').click();square(page,'testBoard','e4').click()
    expect(page.locator('#testBoard button')).to_have_count(0)
    assert pending
    pending[0].fulfill(json={'active':False,'recent':RESULT})
    expect(page.locator('#testProgress')).to_have_text('50단계 종합 평가 완료')
    expect(page.locator('#testBoard button')).to_have_count(0)


def test_assessment_status_single_flight_keeps_results(page,site):
    open_page(page,site)
    pending=[]
    page.route('**/api/v8/assessment/status',lambda r:pending.append(r))
    page.evaluate("tab('assessment')");page.wait_for_timeout(100)
    page.evaluate("tab('home');tab('assessment')");page.wait_for_timeout(100)
    assert len(pending)==1  # Navigation shares the pending status read.
    pending[0].fulfill(json={'active':False,'recent':RESULT})
    expect(page.locator('#testProgress')).to_have_text('50단계 종합 평가 완료')
    page.wait_for_timeout(100)
    assert len(pending)==1
    expect(page.locator('#testBoard button')).to_have_count(0)
