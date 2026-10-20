import threading
import time
import chess
import pytest
import engine_budget as budget
from test_runtime_isolation import runtime


def test_one_engine_and_failure_release(monkeypatch):
    class Engine:
        def quit(self):pass
    monkeypatch.setattr(chess.engine.SimpleEngine,'popen_uci',lambda *a,**k:Engine())
    with budget.open_engine('fake'):
        start=time.monotonic()
        with pytest.raises(budget.EngineBusy):budget.open_engine('fake')
        assert time.monotonic()-start<.5
    with budget.open_engine('fake'):pass
    monkeypatch.setattr(chess.engine.SimpleEngine,'popen_uci',lambda *a,**k:(_ for _ in ()).throw(OSError('failed')))
    with pytest.raises(OSError):budget.open_engine('fake')
    assert budget._slot.acquire(blocking=False);budget._slot.release()


def test_foreground_busy_returns_retry_without_saving_game(runtime,monkeypatch,tmp_path):
    server,(a,b)=runtime;path=tmp_path/'engine';path.touch();monkeypatch.setattr(server,'STOCKFISH_PATH',str(path))
    assert budget._slot.acquire(blocking=False)
    try:
        start=time.monotonic();response=a.post('/api/game/new',json={'color':'black'})
        assert response.status_code==503 and response.headers['retry-after']=='1'
        assert time.monotonic()-start<1
        assert a.get('/api/game').json()['active'] is False
        assert b.get('/api/me').status_code==200
    finally:budget._slot.release()
