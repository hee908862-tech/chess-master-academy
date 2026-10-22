"""Concurrent restoration must not share accounts or cache across mutations."""
import subprocess
from pathlib import Path


def test_inflight_reads_are_identity_scoped_and_invalidated_by_writes():
    script=Path('public/app.js').read_text()
    wrapper=script[script.index('const sharedReads='):script.index('async function apiRequest')]
    test=r'''
const assert=require('node:assert/strict');let token='first';const calls=[];
function apiRequest(path,method,body){let resolve,reject;const p=new Promise((a,b)=>{resolve=a;reject=b});calls.push({path,method,body,resolve,reject});return p;}
'''+wrapper+r'''
(async()=>{
 const a=api('/journey'),b=api('/journey');assert.equal(a,b);assert.equal(calls.length,1);
 token='second';const c=api('/journey');assert.notEqual(a,c);assert.equal(calls.length,2);
 token='first';const write=api('/journey/action','POST',{action:'next'});const fresh=api('/journey');assert.notEqual(a,fresh);
 calls[0].resolve({old:true});await a;await Promise.resolve();assert.equal(api('/journey'),fresh);
 calls[3].resolve({current:true});await fresh;await Promise.resolve();assert.notEqual(api('/journey'),fresh);
 const w2=api('/journey/action','POST',{}),w3=api('/journey/action','POST',{});assert.notEqual(w2,w3);
 const fail=api('/foundations');calls.at(-1).reject(Error('offline'));await fail.catch(()=>{});await Promise.resolve();assert.notEqual(api('/foundations'),fail);
 console.log('identity, mutation, settlement, error, writes: passed');
})().catch(e=>{console.error(e);process.exit(1)});
'''
    subprocess.run(['node','-e',test],check=True,capture_output=True,text=True)
