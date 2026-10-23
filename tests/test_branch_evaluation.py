"""Explicit read-only evaluation fallback; isolated owned API, never operating data."""
import copy
import chess
import chess.engine
import pytest
from test_runtime_isolation import runtime

FEN='8/2k5/1Np2K2/P1P2ppp/1P6/3b2P1/7P/8 b - - 0 1'


def test_evaluation_white_pov_cache_rate_and_no_record_mutation(runtime,monkeypatch,tmp_path):
    server,(a,b)=runtime
    path=tmp_path/'engine';path.touch();monkeypatch.setattr(server,'STOCKFISH_PATH',str(path))
    class Engine:
        id={'name':'test engine'}
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def configure(self,options):assert options=={'Threads':1,'Hash':16}
        def analyse(self,board,limit):
            assert limit.time==.2 and limit.depth==14 and limit.nodes==60000
            return {'score':chess.engine.PovScore(chess.engine.Cp(200),chess.BLACK),'depth':12,'pv':[chess.Move.from_uci('f5f4')]}
    import study_server
    monkeypatch.setattr(study_server,'open_engine',lambda *a,**kw:Engine())
    before=copy.deepcopy(server.get_state('RUNTIME-A'))
    r=a.post('/api/study/position',json={'fen':FEN,'evaluate':True})
    assert r.status_code==200 and r.json()['evaluation']['value']==-200
    assert r.json()['evaluation']['best']=='f5f4'
    assert a.post('/api/study/position',json={'fen':FEN,'evaluate':True}).status_code==200
    changed=chess.Board(FEN);changed.push_uci('f5f4')
    assert a.post('/api/study/position',json={'fen':changed.fen(),'evaluate':True}).status_code==429
    assert server.get_state('RUNTIME-A')==before


def test_auth_invalid_position_and_engine_failure_do_not_become_zero(runtime,monkeypatch):
    server,(a,b)=runtime
    assert a.post('/api/study/position',json={'fen':FEN,'evaluate':True},headers={'Authorization':'Bearer invalid'}).status_code==401
    assert a.post('/api/study/position',json={'fen':'invalid','evaluate':True}).status_code==400
    monkeypatch.setattr(server,'STOCKFISH_PATH','')
    import study_server,time
    clock=time.monotonic()+100;monkeypatch.setattr(study_server.time,'monotonic',lambda:clock)
    r=a.post('/api/study/position',json={'fen':FEN.replace('0 1','2 1'),'evaluate':True})
    assert r.status_code==503 and 'evaluation' not in r.json()
    direct=a.post('/api/study/position',json={'fen':FEN,'moves':['f5f4','g3f4']})
    assert direct.status_code==200 and direct.json()['fen'].split()[1]=='b'


def test_terminal_mate_and_draw_without_engine(runtime,monkeypatch):
    server,(a,b)=runtime;monkeypatch.setattr(server,'STOCKFISH_PATH','')
    for fen,kind in [('7k/6Q1/5K2/8/8/8/8/8 b - - 0 1','terminal-mate'),('7k/5Q2/5K2/8/8/8/8/8 b - - 0 1','draw')]:
        r=a.post('/api/study/position',json={'fen':fen,'evaluate':True})
        assert r.status_code==200 and r.json()['evaluation']['kind']==kind


def test_actual_stockfish_branch_pov_and_best_reply(runtime,monkeypatch):
    from pathlib import Path
    server,(a,b)=runtime
    path='/tmp/chess-stockfish/usr/games/stockfish'
    if not Path(path).is_file():pytest.skip('actual Stockfish unavailable')
    monkeypatch.setattr(server,'STOCKFISH_PATH',path)
    import study_server,time
    clock=time.monotonic()+300;monkeypatch.setattr(study_server.time,'monotonic',lambda:clock)
    r=a.post('/api/study/position',json={'fen':FEN.replace('0 1','3 1'),'evaluate':True})
    assert r.status_code==200,r.text
    value=r.json()['evaluation'];assert value['kind'] in ('cp','mate') and value['value']<0
    assert chess.Move.from_uci(value['best']) in chess.Board(FEN).legal_moves
