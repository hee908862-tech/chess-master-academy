import logging
import os
import chess
import pytest
from diagnostic_replay import evaluate_frame


def test_slow_uci_initialization_is_separate_from_search_budget(tmp_path,caplog):
    engine=tmp_path/'slow-uci'
    engine.write_text('''#!/usr/bin/env python3
import sys,time
for raw in sys.stdin:
 command=raw.strip()
 if command=='uci':
  time.sleep(3.2)
  print('id name Slow initialization fixture',flush=True)
  print('option name Threads type spin default 1 min 1 max 1',flush=True)
  print('option name Hash type spin default 16 min 1 max 16',flush=True)
  print('uciok',flush=True)
 elif command=='isready': print('readyok',flush=True)
 elif command.startswith('go'):
  print('info depth 14 score cp 31',flush=True)
  print('bestmove e2e4',flush=True)
 elif command=='quit': break
''')
    engine.chmod(0o700)
    with caplog.at_level(logging.INFO,logger='uvicorn.error'):
        result=evaluate_frame(chess.STARTING_FEN,str(engine))
    assert result['status']=='analysed' and result['cp_white']==31
    assert '준비·통신 별도' in result['basis']
    assert 'startup_ms' in caplog.text and 'analysis_ms' in caplog.text and 'shutdown_ms' in caplog.text
    assert chess.STARTING_FEN not in caplog.text


@pytest.mark.parametrize('stage',['startup','configure','analysis','shutdown'])
def test_failure_stage_is_logged_without_exception_payload(monkeypatch,tmp_path,caplog,stage):
    import engine_budget
    executable=tmp_path/'exists';executable.touch()
    class Fake:
        id={'name':'test'}
        def __enter__(self):return self
        def __exit__(self,*args):
            if stage=='shutdown':
                exc=TimeoutError('private-content');exc.engine_failure_stage='shutdown';raise exc
        def configure(self,*a):
            if stage=='configure':raise TimeoutError('private-content')
        def analyse(self,*a):
            if stage=='analysis':raise TimeoutError('private-content')
            return {'score':chess.engine.PovScore(chess.engine.Cp(10),chess.WHITE),'depth':14}
    def factory(*a,**kw):
        if stage=='startup':raise TimeoutError('private-content')
        return Fake()
    monkeypatch.setattr(engine_budget,'open_engine',factory)
    with caplog.at_level(logging.INFO,logger='uvicorn.error'):
        result=evaluate_frame(chess.STARTING_FEN,str(executable))
    assert result['status']=='failed' and result['failure_stage']==stage and 'cp_white' not in result
    assert 'TimeoutError' in caplog.text and 'private-content' not in caplog.text


def test_observed_operating_position_with_actual_stockfish():
    path=os.environ.get('STOCKFISH_PATH','')
    if not os.path.isfile(path):pytest.skip('actual Stockfish unavailable')
    # Piece placement supplied by operating QA; no claim about unseen clocks/rights.
    fen='2r2rk1/7p/pn2b1pP/1p1p2q1/3Qp3/1P2Pp2/P2P1P2/1K1R1B1R w - - 0 1'
    board=chess.Board(fen);assert board.is_valid()
    board.push_uci('d4g7');assert board.is_checkmate()
    result=evaluate_frame(fen,path)
    assert result['status']=='mate' and result['mate_white']>0
