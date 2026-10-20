"""Controlled-response Chromium tests; never accesses the deployed application."""
import chess
import pytest
from playwright.sync_api import expect
from test_qa_browser import page, site, open_page, square, RESULT


def board_data(board):
    return dict(fen=board.fen(),squares={chess.square_name(s):p.symbol() for s,p in board.piece_map().items()},
        turn='white' if board.turn else 'black',is_over=False) | {'legal':[{'from':m.uci()[:2],'to':m.uci()[2:4],'promotion':m.uci()[4:]} for m in board.legal_moves]}


def setup_wait(page,site,mode,initial=None):
    b=initial or chess.Board()
    board=board_data(b)
    task=dict(id='p1',session_id='s1',fen=b.fen(),legal=[m.uci() for m in b.legal_moves],
        rating=1400,themes=['전술'],ply=1,index=0,total=1,side='white',opponent_last_move=None)
    open_page(page,site)
    if mode=='game':
        name='gameBoard';path='**/api/game/move'
        page.route('**/api/game/new',lambda r:r.fulfill(json={'board':board,'session_id':'s1','player_color':'white'}))
        page.evaluate("tab('play')");page.locator('#newGame').click()
    elif mode=='assessment':
        name='testBoard';path='**/api/v8/assessment/game-move'
        page.route('**/api/v8/assessment/status',lambda r:r.fulfill(json={'active':True,'phase':'game','session_id':'s1','board':board}))
        page.evaluate("tab('assessment')")
    else:
        name='v9PuzzleBoard';path='**/api/v9/puzzle/move'
        page.route('**/api/v9/puzzle/start',lambda r:r.fulfill(json=task))
        page.evaluate("tab('puzzle')");page.locator('#v9PuzzleStart').click()
    expect(square(page,name,'e2')).to_be_enabled()
    requests=[]
    page.route(path,lambda r:requests.append(r))
    return name,requests,task


def reply(route,mode,board,task,finished=False):
    if mode=='game':data={'board':board_data(board),'session_id':task['session_id'],'finished':finished}
    elif mode=='assessment':data={'board':board_data(board),'session_id':task['session_id'],'phase':'game','done':finished,'result':RESULT}
    else:data={**task,'fen':board.fen(),'legal':[m.uci() for m in board.legal_moves],
        'correct':True,'solved':finished,'done':finished,'reply':'e7e5','message':'정답','completed_fen':board.fen()}
    route.fulfill(json=data)


def play_initial(page,name):
    square(page,name,'e2').click();square(page,name,'e4').click()
    expect(square(page,name,'e4')).to_have_attribute('aria-label',__import__('re').compile(r'^e4 백 폰(?: · .+)?$'))


@pytest.mark.parametrize('mode',['game','assessment','puzzle'])
@pytest.mark.parametrize('mobile',[False,True])
def test_premove_default_off_then_executes_once(page,site,mode,mobile):
    if mobile:page.set_viewport_size({'width':390,'height':844})
    name,requests,task=setup_wait(page,site,mode)
    toggle=page.get_by_role('checkbox',name='프리무브 '+name,exact=True)
    expect(toggle).not_to_be_checked();toggle.check()
    play_initial(page,name)
    square(page,name,'g1').click();square(page,name,'f3').click()
    expect(page.locator('#'+name+' .premove-arrow')).to_have_count(1)
    assert len(requests)==1
    if mobile:
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        if mode=='game':page.screenshot(path='/tmp/chess-premove-mobile.png',full_page=True)
    b=chess.Board();b.push_uci('e2e4');b.push_uci('e7e5')
    reply(requests[0],mode,b,task)
    # Wait for the actual queued request; 300ms was flaky under concurrent Chromium/engine load.
    for _ in range(100):
        if len(requests)>=2:break
        page.wait_for_timeout(50)
    assert len(requests)==2
    sent=requests[1].request.post_data_json
    assert sent.get('move',sent.get('from_sq','')+sent.get('to_sq',''))=='g1f3'
    assert sent['session_id']=='s1' and sent['expected_fen']==b.fen()
    b.push_uci('g1f3');reply(requests[1],mode,b,task,True)
    page.wait_for_timeout(150)
    assert len(requests)==2
    expect(page.locator('#'+name+' .premove-arrow')).to_have_count(0)
    assert page.evaluate("localStorage.getItem('cma_premove')")=='on'


@pytest.mark.parametrize('mode',['game','assessment','puzzle'])
@pytest.mark.parametrize('action',['off','cancel','menu','illegal','finished','session','error'])
def test_premove_cancellation(page,site,action,mode):
    name,requests,task=setup_wait(page,site,mode)
    toggle=page.get_by_role('checkbox',name='프리무브 '+name,exact=True);toggle.check()
    play_initial(page,name)
    square(page,name,'g1').click();square(page,name,'f3' if action!='illegal' else 'g5').click()
    if action=='off':toggle.uncheck()
    if action=='cancel':page.get_by_label('프리무브 '+name,exact=True).locator('..').locator('..').get_by_role('button',name='예약 취소').click()
    if action=='menu':page.evaluate("tab('home')")
    if action in ['off','cancel','menu']:expect(page.locator('#'+name+' .premove-arrow')).to_have_count(0)
    b=chess.Board();b.push_uci('e2e4');b.push_uci('e7e5')
    if action=='session':task['session_id']='other'
    if action=='error':requests[0].fulfill(status=409,json={'detail':'대국 변경'})
    else:reply(requests[0],mode,b,task,action=='finished')
    page.wait_for_timeout(250)
    assert len(requests)==1
    expect(page.locator('#'+name+' .premove-arrow')).to_have_count(0)


@pytest.mark.parametrize('choice',['cancel','r'])
def test_premove_promotion_waits_for_choice_and_menu_cancels(page,site,choice):
    initial=chess.Board('7k/P7/8/8/8/8/4P3/4K3 w - - 0 1')
    name,requests,task=setup_wait(page,site,'game',initial)
    page.get_by_role('checkbox',name='프리무브 '+name,exact=True).check()
    play_initial(page,name);square(page,name,'a7').click();square(page,name,'a8').click()
    initial.push_uci('e2e4');initial.push_uci('h8g8')
    reply(requests[0],'game',initial,task)
    expect(page.locator('#cmaPromotionModal')).to_be_visible()
    assert len(requests)==1
    if choice=='cancel':
        page.evaluate("tab('home')")
        expect(page.locator('#cmaPromotionModal')).to_be_hidden()
        page.wait_for_timeout(100);assert len(requests)==1
    else:
        page.locator('#cmaPromotionModal button').filter(has_text='룩').click()
        page.wait_for_timeout(100);assert len(requests)==2
        assert requests[1].request.post_data_json['promotion']=='r'
        initial.push_uci('a7a8r');reply(requests[1],'game',initial,task,True)


def test_black_question_feedback_keeps_orientation_and_history(page,site):
    b=chess.Board();b.push_uci('e2e4')
    q=dict(id=0,fen=b.fen(),legal=[m.uci() for m in b.legal_moves],difficulty=1,description='직전 수 기회',opponent_last_move='e2e4')
    state={'active':True,'phase':'questions','index':0,'domain':'전술','question':q}
    page.route('**/api/v8/assessment/status',lambda r:r.fulfill(json=state))
    b.push_uci('e7e5')
    fb=dict(correct=True,domain='전술',difficulty=1,seconds=1,points=100,original_fen=q['fen'],answer_fen=b.fen(),answer='e7e5')
    page.route('**/api/v8/assessment/answer',lambda r:r.fulfill(json={'feedback':fb}))
    open_page(page,site);page.evaluate("tab('assessment')")
    expect(page.locator('#testBoard .sq').first).to_have_attribute('aria-label','h1 백 룩')
    expect(square(page,'testBoard','e2')).to_have_class(__import__('re').compile('opponent-move'))
    expect(square(page,'testBoard','e4')).to_have_class(__import__('re').compile('opponent-move'))
    square(page,'testBoard','e7').click();square(page,'testBoard','e5').click()
    expect(page.locator('#v8Overlay')).to_be_visible()
    expect(page.locator('#testBoard .sq').first).to_have_attribute('aria-label','h1 백 룩')
    state.clear();state.update(active=True,phase='feedback',feedback=fb)
    page.evaluate("tab('home');tab('assessment')")
    expect(page.locator('#v8Overlay')).to_be_visible()
    expect(page.locator('#testBoard .sq').first).to_have_attribute('aria-label','h1 백 룩')
    page.reload();page.evaluate("tab('assessment')")
    expect(page.locator('#testBoard .sq').first).to_have_attribute('aria-label','h1 백 룩')


def test_black_puzzle_hint_reply_and_next_color(page,site):
    b=chess.Board();b.push_uci('e2e4')
    task=dict(id='black',session_id='s1',fen=b.fen(),legal=[m.uci() for m in b.legal_moves],side='black',rating=1400,themes=['전술'],ply=1,index=0,total=1,opponent_last_move='e2e4')
    page.route('**/api/v9/puzzle/start',lambda r:r.fulfill(json=task))
    page.route('**/api/v9/puzzle/hint*',lambda r:r.fulfill(json={'from':'e7','to':'e5','move_label':'e5','explanation':'힌트'}))
    open_page(page,site);page.evaluate("tab('puzzle')");page.locator('#v9PuzzleStart').click()
    name='v9PuzzleBoard'
    expect(page.locator('#'+name+' .sq').first).to_have_attribute('aria-label','h1 백 룩')
    page.locator('#v9PuzzleHint').click()
    expect(page.locator('#'+name+' .move-hint')).to_have_count(2)
    expect(page.locator('#'+name+' .opponent-move')).to_have_count(2)
    b.push_uci('e7e5');b.push_uci('g1f3')
    page.route('**/api/v9/puzzle/move',lambda r:r.fulfill(json={**task,'fen':b.fen(),'legal':[m.uci() for m in b.legal_moves],'correct':True,'solved':False,'reply':'g1f3','opponent_last_move':'g1f3'}))
    square(page,name,'e7').click();square(page,name,'e5').click()
    expect(square(page,name,'f3')).to_have_attribute('aria-label',__import__('re').compile(r'^f3 백 나이트 · 상대 직전 수'))
    expect(page.locator('#'+name+' .sq').first).to_have_attribute('aria-label','h1 백 룩')
    page.evaluate("tab('home');tab('puzzle')")
    expect(page.locator('#'+name+' .sq').first).to_have_attribute('aria-label','h1 백 룩')
    task.update(id='white',fen=chess.STARTING_FEN,side='white',legal=['e2e4'],opponent_last_move=None)
    page.locator('#v9PuzzleStart').click()
    expect(page.locator('#'+name+' .sq').first).to_have_attribute('aria-label','a8 흑 룩')
    expect(page.locator('#v9PuzzleMessage')).to_contain_text('직전 수 기록이 없어')


def test_results_stay_clear_during_reload_and_delayed_status(page,site):
    from test_qa_followup_browser import previous_result,QUESTION
    previous_result(page,site)
    pending=[]
    page.route('**/api/v8/assessment/status',lambda r:pending.append(r))
    page.evaluate("tab('home');tab('assessment')")
    expect(page.locator('#v8ScoreSummary')).to_be_empty()
    expect(page.locator('#v8RecommendationList')).to_be_empty()
    assert pending
    pending[0].fulfill(json=QUESTION)
    expect(page.locator('#testProgress')).to_contain_text('문항 1')
    page.route('**/api/v8/assessment/status',lambda r:r.fulfill(json=QUESTION))
    page.reload();page.evaluate("tab('assessment')")
    expect(page.locator('#testProgress')).to_contain_text('문항 1')
    expect(page.locator('#v8ScoreSummary')).to_be_empty()
    expect(page.locator('#v8RecommendationList')).to_be_empty()


@pytest.mark.parametrize('mode',['game','assessment'])
def test_premove_does_not_execute_on_expired_clock(page,site,mode):
    name,requests,task=setup_wait(page,site,mode)
    page.get_by_role('checkbox',name='프리무브 '+name,exact=True).check()
    play_initial(page,name);square(page,name,'g1').click();square(page,name,'f3').click()
    b=chess.Board();b.push_uci('e2e4');b.push_uci('e7e5')
    data={'board':board_data(b),'session_id':'s1','clock':{'mode':'bullet','white_ms':0,'black_ms':60000}}
    requests[0].fulfill(json=data)
    page.wait_for_timeout(100)
    assert len(requests)==1
    expect(page.locator('#'+name+' .premove-arrow')).to_have_count(0)
