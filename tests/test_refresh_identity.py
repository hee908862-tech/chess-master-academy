"""Execute the real refresh function without a browser or network."""
import subprocess
from pathlib import Path


def test_old_account_success_and_401_cannot_replace_new_login():
    result=subprocess.run(['node','-e',r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('public/app.js','utf8');
const fn=source.match(/^async function refresh\(\).*$/m)[0];
(async()=>{for(const late401 of [false,true]){
 let resolve,reject;const pending=new Promise((r,j)=>{resolve=r;reject=j});let renders=0,removed=0;const feedback=[];
 const c={token:'A',user:null,game:null,gameOwner:'A',gameRestoreFeedback:(...args)=>feedback.push(args),$:()=>({textContent:''}),api:()=>pending,renderSummary:()=>renders++,resumeGame:async()=>{},renderWinrates:()=>{},window:{practiceModeInitialized:true},notice:()=>{},localStorage:{removeItem:()=>removed++},sessionStorage:{removeItem:()=>removed++}};
 vm.createContext(c);vm.runInContext('let refreshGeneration=0,gameRestoreGeneration=0;'+fn,c);const request=c.refresh();assert.equal(feedback.length,1);c.token='B';
 if(late401)reject(Object.assign(Error('expired'),{status:401}));else resolve({code:'A'});
 await request;assert.equal(c.token,'B');assert.equal(renders,0);assert.equal(removed,0);assert.equal(feedback.length,1,'stale response must not replace restoration feedback');
}})().catch(e=>{console.error(e);process.exit(1)});
'''],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
