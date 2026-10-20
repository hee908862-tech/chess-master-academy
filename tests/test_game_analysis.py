import threading
import time
import chess
import chess.engine
import pytest
import game_analysis as ga
from test_runtime_isolation import runtime


def wait_result(client,key):
    for _ in range(100):
        data=client.get('/api/games/analysis').json()
        game=next(g for g in data['games'] if g['game_key']==key)
        if game['status'] not in ('queued','running'):return game
        time.sleep(.02)
    raise AssertionError('analysis did not finish')


def seed(server):
    state=server.get_state('RUNTIME-A');game={'moves':['e2e4','e7e5','g1f3','b8c6'],'color':'black','ended':'2026-10-20','assistance':{'version':1,'complete':True,'events':[]}}
    state['games']=[game];server.save_state('RUNTIME-A',state);return game


def test_black_pov_mates_missing_depth_and_rating_hold(monkeypatch,tmp_path):
    path=tmp_path/'engine';path.touch()
    class Engine:
        id={'name':'test engine'}
        def configure(self,settings):assert settings=={'Threads':1,'Hash':16}
        def analyse(self,board,limit):
            # White advantage grows after Black's move: a loss for the black user.
            cp=100 if len(board.move_stack)%2 else 300
            return {'score':chess.engine.PovScore(chess.engine.Cp(cp),chess.WHITE),'depth':12}
        def quit(self):pass
    monkeypatch.setattr(chess.engine.SimpleEngine,'popen_uci',lambda *a,**k:Engine())
    game={'moves':['e2e4','e7e5','g1f3','b8c6'],'color':'black','assistance':{'version':1}}
    result=ga.analyse_game(game,str(path))
    assert result['user_moves']==result['expected_moves']==2
    assert all(r['before_cp']==-100 and r['after_cp']==-300 and r['loss_cp']==200 for r in result['rows'])
    assert result['quality']==36.8 and result['rating'] is None and not result['representative']
    Engine.analyse=lambda *args,**kwargs:{'score':chess.engine.PovScore(chess.engine.Mate(1),chess.BLACK),'depth':4}
    result=ga.analyse_game(game,str(path));assert result['status']=='partial' and all(r['mate_evaluation'] for r in result['rows'])
    Engine.analyse=lambda *args,**kwargs:{}
    with pytest.raises(RuntimeError):ga.analyse_game(game,str(path))


def test_background_dedup_failed_retry_and_account_isolation(runtime,monkeypatch):
    server,(a,b)=runtime;game=seed(server);key=ga.game_key(game)
    entered=threading.Event();release=threading.Event();calls=[]
    def work(*args):
        calls.append(1);entered.set();assert release.wait(3)
        raise RuntimeError('engine failed')
    monkeypatch.setattr(ga,'analyse_game',work)
    assert a.get('/api/games/analysis').json()['games'][0]['status']=='not_started'
    assert a.post('/api/games/analysis/'+key).status_code==200;assert entered.wait(2)
    assert a.post('/api/games/analysis/'+key).status_code==200
    assert b.get('/api/me').status_code==200 and b.get('/api/games/analysis').json()['games']==[]
    assert b.post('/api/games/analysis/'+key).status_code==404
    release.set();assert wait_result(a,key)['status']=='failed';assert len(calls)==1
    monkeypatch.setattr(ga,'analyse_game',lambda *a:{'status':'complete','score_version':ga.VERSION,'quality':80,'user_moves':2,'expected_moves':2,'representative':False,'rating':None})
    assert a.post('/api/games/analysis/'+key).status_code==200
    assert wait_result(a,key)['status']=='complete'
    assert a.get('/api/games/analysis').json()['average'] is None
    assert len(server.get_state('RUNTIME-A')['games'])==1


def test_reset_generation_does_not_restore_analysis(runtime,monkeypatch):
    server,(a,b)=runtime;game=seed(server);key=ga.game_key(game)
    entered=threading.Event();release=threading.Event()
    def work(*args):entered.set();release.wait(3);return {'status':'complete','quality':90}
    monkeypatch.setattr(ga,'analyse_game',work)
    a.post('/api/games/analysis/'+key);assert entered.wait(2)
    try:
        r=a.post('/api/profile/reset',json={'pin':'local-runtime-9384','confirmation':'초기화','revision':0});assert r.status_code==200,r.text
    finally:release.set()
    for _ in range(100):
        if ga._slots.acquire(blocking=False):ga._slots.release();break
        time.sleep(.02)
    with server.db() as conn:assert server.execute(conn,'SELECT * FROM game_analysis WHERE code=?',('RUNTIME-A',)).fetchall()==[]


def test_internal_quality_monotone_no_elo_mapping():
    assert ga.move_quality(0,100)==(100,0)
    assert ga.move_quality(0,-200)[0]>ga.move_quality(0,-400)[0]
    assert ga.move_quality(10000,-10000)[0]==0


def test_interrupted_job_can_retry_without_inventing_score(runtime,monkeypatch):
    import json
    server,(a,b)=runtime;game=seed(server);key=ga.game_key(game)
    raw={'status':'running','requested_at':time.time()-121,'job_id':'old'}
    with server.db() as conn:server.execute(conn,'INSERT INTO game_analysis(code,game_key,state) VALUES(?,?,?)',('RUNTIME-A',key,json.dumps(raw)))
    item=a.get('/api/games/analysis').json()['games'][0]
    assert item['status']=='failed' and 'quality' not in item
    monkeypatch.setattr(ga,'analyse_game',lambda *a:{'status':'partial','score_version':ga.VERSION,'quality':70,'representative':False,'rating':None})
    assert a.post('/api/games/analysis/'+key).status_code==200
    assert wait_result(a,key)['status']=='partial'


def opera_game():
    board=chess.Board();moves=[]
    for san in 'e4 e5 Nf3 d6 d4 Bg4 dxe5 Bxf3 Qxf3 dxe5 Bc4 Nf6 Qb3 Qe7 Nc3 c6 Bg5 b5 Nxb5 cxb5 Bxb5+ Nbd7 O-O-O Rd8 Rxd7 Rxd7 Rd1 Qe6 Bxd7+ Nxd7 Qb8+ Nxb8 Rd8#'.split():
        move=board.parse_san(san);moves.append(move.uci());board.push(move)
    assert board.is_checkmate()
    return {'moves':moves,'color':'white','termination':'rules','assistance':{'version':1,'complete':True,'events':[]}}


def test_actual_stockfish_terminal_mate_is_not_low_depth():
    import os
    path=os.environ['STOCKFISH_PATH'];game=opera_game();board=chess.Board()
    for u in game['moves']:board.push_uci(u)
    with chess.engine.SimpleEngine.popen_uci(path) as engine:
        terminal=engine.analyse(board,chess.engine.Limit(time=.08,depth=14))
    assert terminal['depth']==0 # Reproduces the former min(before,after) exclusion.
    result=ga.analyse_game(game,path)
    assert result['user_moves']==17 and result['status']=='complete',result
    assert result['representative']
    row=result['rows'][-1];assert row['terminal'] and row['quality']==100 and row['after_cp'] is None
    assert row['quality_basis']=='rules_checkmate'
    assert all(r['before_cp']!=10000 and r['after_cp']!=10000 for r in result['rows'])


def test_actual_stockfish_stalemate_is_terminal_not_missing_depth():
    import os
    result=ga.analyse_game({'initial_fen':'7k/5K2/4Q3/8/8/8/8/8 w - - 0 1','moves':['e6g6'],'color':'white'},os.environ['STOCKFISH_PATH'])
    assert result['status']=='complete' and result['rows'][0]['terminal']
    assert '낮은 탐색 깊이' not in result['flags']


@pytest.mark.parametrize('termination',['resign','timeout'])
def test_normal_long_losses_are_not_excluded_from_quality(monkeypatch,tmp_path,termination):
    path=tmp_path/'engine';path.touch()
    class Engine:
        id={'name':'controlled'}
        def configure(self,*a):pass
        def analyse(self,*a):return {'score':chess.engine.PovScore(chess.engine.Cp(0),chess.WHITE),'depth':12}
        def quit(self):pass
    monkeypatch.setattr(chess.engine.SimpleEngine,'popen_uci',lambda *a,**k:Engine())
    game=opera_game();game.update(termination=termination,result='loss',resigned=termination=='resign')
    game['moves']=game['moves'][:-1]
    result=ga.analyse_game(game,str(path));assert result['representative'] and result['status']=='complete'
