"""One engine process per app worker; bounded admission, no unbounded foreground wait."""
import threading
import time
import chess.engine

_slot=threading.BoundedSemaphore(1)
class EngineBusy(chess.engine.EngineError):pass

class Lease:
    def __init__(self,engine,timings=None):
        self.engine=engine;self.released=False;self.timings=timings if timings is not None else {}
    def __getattr__(self,name):return getattr(self.engine,name)
    def __enter__(self):return self
    def __exit__(self,kind,value,traceback):
        # Preserve the analysis failure instead of replacing it with a quit failure.
        try:self.quit()
        except (chess.engine.EngineError,TimeoutError,OSError):
            if kind is None:raise
    def quit(self):
        if self.released:return
        started=time.monotonic()
        try:self.engine.quit()
        except (chess.engine.EngineError,TimeoutError,OSError) as exc:
            exc.engine_failure_stage='shutdown'
            raise
        finally:
            try:
                # quit() may time out; always close its transport before releasing admission.
                close=getattr(self.engine,'close',None)
                if close:close()
            finally:
                self.timings['shutdown_ms']=round((time.monotonic()-started)*1000,3)
                self.released=True;_slot.release()

def open_engine(*args,**kwargs):
    timings=kwargs.pop('timings',None)
    if timings is None:timings={}
    started=time.monotonic();acquired=_slot.acquire(timeout=.15)
    timings['queue_ms']=round((time.monotonic()-started)*1000,3)
    if not acquired:raise EngineBusy('다른 분석이 진행 중입니다. 잠시 후 다시 시도해 주세요.')
    started=time.monotonic()
    try:return Lease(chess.engine.SimpleEngine.popen_uci(*args,**kwargs),timings)
    except BaseException:_slot.release();raise
    finally:timings['startup_ms']=round((time.monotonic()-started)*1000,3)
