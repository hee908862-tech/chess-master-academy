"""Controlled engine lifecycle checks; these are not real Stockfish tests."""
import threading
from concurrent.futures import ThreadPoolExecutor
import chess
import chess.engine
import pytest
import engine_budget
import growth_model

class Engine:
    id={'name':'controlled-test-engine'}
    def __init__(self):self.closed=False
    def configure(self,*a):pass
    def analyse(self,board,limit):
        assert limit.time==.3 and limit.depth==16
        return {'score':chess.engine.PovScore(chess.engine.Cp(0),chess.WHITE),'depth':12}
    def quit(self):pass
    def close(self):self.closed=True

@pytest.mark.parametrize('failure',[TimeoutError,chess.engine.EngineTerminatedError])
def test_failure_closes_and_allows_next_request(monkeypatch,tmp_path,failure):
    path=tmp_path/'engine';path.touch();engine=Engine()
    def broken(*a):raise failure('controlled failure')
    engine.analyse=broken
    engine.quit=broken
    monkeypatch.setattr(chess.engine.SimpleEngine,'popen_uci',lambda *a,**k:engine)
    result=growth_model.verify_loss(chess.STARTING_FEN,'e2e4',str(path))
    assert result['status']=='unverified' and 'loss_cp' not in result
    assert result['error_type']==failure.__name__ and result['failure_stage']=='analysis_before'
    assert engine.closed
    assert all(k in result['timings_ms'] for k in ['queue_ms','startup_ms','analysis_before_ms','shutdown_ms','total_ms'])
    healthy=Engine();monkeypatch.setattr(chess.engine.SimpleEngine,'popen_uci',lambda *a,**k:healthy)
    assert growth_model.verify_loss(chess.STARTING_FEN,'e2e4',str(path))['status']=='equivalent_alternative'
    assert healthy.closed

def test_concurrent_request_does_not_start_second_process(monkeypatch,tmp_path):
    path=tmp_path/'engine';path.touch();entered=threading.Event();release=threading.Event();calls=[]
    class Waiting(Engine):
        def analyse(self,*a):
            entered.set();assert release.wait(3)
            return super().analyse(*a)
    def spawn(*a,**k):calls.append(1);return Waiting()
    monkeypatch.setattr(chess.engine.SimpleEngine,'popen_uci',spawn)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(growth_model.verify_loss,chess.STARTING_FEN,'e2e4',str(path))
        assert entered.wait(3)
        try:
            second=growth_model.verify_loss(chess.STARTING_FEN,'e2e4',str(path))
            assert second['status']=='unverified' and second['reason']=='diagnosis_busy'
            assert len(calls)==1
        finally:release.set()
        assert first.result()['status']=='equivalent_alternative'

def test_startup_timeout_releases_slot(monkeypatch,tmp_path):
    path=tmp_path/'engine';path.touch()
    def broken(*a,**k):raise TimeoutError('startup')
    monkeypatch.setattr(chess.engine.SimpleEngine,'popen_uci',broken)
    result=growth_model.verify_loss(chess.STARTING_FEN,'e2e4',str(path))
    assert result['failure_stage']=='startup'
    assert 'startup_ms' in result['timings_ms']
    assert engine_budget._slot.acquire(False)
    engine_budget._slot.release()


def test_shutdown_failure_cannot_leave_verified_error(monkeypatch,tmp_path):
    path=tmp_path/'engine';path.touch()
    class LateFailure(Engine):
        def analyse(self,board,limit):
            return {'score':chess.engine.PovScore(chess.engine.Cp(300 if not board.move_stack else 0),chess.WHITE),'depth':12}
        def quit(self):raise TimeoutError('shutdown')
    monkeypatch.setattr(chess.engine.SimpleEngine,'popen_uci',lambda *a,**k:LateFailure())
    result=growth_model.verify_loss(chess.STARTING_FEN,'e2e4',str(path))
    assert result['status']=='unverified'
    assert 'loss_cp' not in result
