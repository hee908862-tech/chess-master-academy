"""Node controller checks only: no browser/mobile claims."""
import json
import subprocess
from pathlib import Path


def test_reload_and_cross_tab_logout_controller():
    root=Path(__file__).resolve().parents[1]
    app=(root/'public/app.js').read_text()
    init=next(line for line in app.splitlines() if line.startswith('let token='))
    source=(root/'public/guest-access.js').read_text()
    hooks=source[source.index('const oldSignout='):source.index('const oldTab=')]
    script='''const assert=require('node:assert/strict');
const values=new Map(),localStorage={getItem:k=>values.get(k)||null,removeItem:k=>values.delete(k)},sessionStorage={getItem:()=>null};
const events={};let cancelled=0,reset=0,loggedOut=null,user={},msg={};
const saved={replaceChildren(){}},window={cmaBoardTools:{cancelAll(){cancelled++}},addEventListener:(k,fn)=>events[k]=fn};
const resetGameAccount=()=>reset++,tab=()=>{};
const signout={onclick:async()=>{loggedOut=token;localStorage.removeItem('chess_token');token='';}};
const $=()=>signout;
values.set('cma_identity','linked');values.set('cma_linked_token','linked');values.set('chess_token','owner');
'''+init+'''
assert.equal(token,'linked');
'''+hooks+'''
(async()=>{await signout.onclick();assert.equal(loggedOut,'owner');assert.equal(token,'');assert.equal(localStorage.getItem('cma_linked_token'),null);
token='linked';events.storage({key:'cma_linked_token',oldValue:'linked',newValue:null});assert.equal(token,'');assert.equal(user,null);assert.equal(cancelled,1);
})();'''
    result=subprocess.run(['node','-e',script],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    # Reload with no account cannot bootstrap a linked resume token.
    for data,expected in [({'cma_identity':'linked','cma_linked_token':'linked'},''),({'cma_identity':'guest','cma_guest_token':'anonymous'},'anonymous')]:
        script="const m="+json.dumps(data)+";const localStorage={getItem:k=>m[k]||null},sessionStorage={getItem:()=>null};"+init+"require('node:assert/strict').equal(token,"+json.dumps(expected)+");"
        result=subprocess.run(['node','-e',script],capture_output=True,text=True)
        assert result.returncode==0,result.stderr
