"""Reap orphaned subprocesses created by this pytest process only; never PID1 children."""
import ctypes,os
import pytest
ctypes.CDLL(None).prctl(36,1,0,0,0)
@pytest.fixture(autouse=True)
def reap_own_orphans():
    yield
    while True:
        try:
            pid,_=os.waitpid(-1,os.WNOHANG)
            if not pid:break
        except ChildProcessError:break
if os.environ.get('CMA_LOW_RESOURCE')=='1':
    from playwright.sync_api import BrowserType
    original_launch=BrowserType.launch
    def low_resource_launch(self,**kwargs):
        kwargs['args']=[*(kwargs.get('args') or []),'--single-process','--no-zygote','--disable-gpu','--disable-breakpad','--renderer-process-limit=1']
        return original_launch(self,**kwargs)
    BrowserType.launch=low_resource_launch
