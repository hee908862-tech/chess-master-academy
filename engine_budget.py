"""One engine process per app worker; bounded admission, no unbounded foreground wait."""
import threading
import chess.engine

_slot=threading.BoundedSemaphore(1)
class EngineBusy(chess.engine.EngineError):pass

class Lease:
    def __init__(self,engine):self.engine=engine;self.released=False
    def __getattr__(self,name):return getattr(self.engine,name)
    def __enter__(self):return self
    def __exit__(self,*args):self.quit()
    def quit(self):
        if self.released:return
        try:self.engine.quit()
        finally:self.released=True;_slot.release()

def open_engine(*args,**kwargs):
    if not _slot.acquire(timeout=.15):raise EngineBusy('다른 분석이 진행 중입니다. 잠시 후 다시 시도해 주세요.')
    try:return Lease(chess.engine.SimpleEngine.popen_uci(*args,**kwargs))
    except BaseException:_slot.release();raise
