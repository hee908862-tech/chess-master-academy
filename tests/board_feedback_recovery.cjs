// Execute actual controller code with transport/DOM doubles: no browser coverage claim.
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
(async()=>{
 const nodes=new Map(),feedback=new Map();
 const node=id=>{if(!nodes.has(id))nodes.set(id,{textContent:'',style:{},classList:{add(){},contains(){return false}},replaceChildren(){},append(){},querySelectorAll(){return []},after(){}});return nodes.get(id)};
 const ctx={console,token:'local',chessStart:'start',cancelPromotion(){},fromFen(){return {}},drawBoard(){},setInterval(){},setTimeout(){},clearTimeout(){},ready(){return true},document:{getElementById:node,createElement:()=>node(Math.random())},window:{cmaFeedback:{set:(id,s)=>feedback.set(id,s),clear:id=>feedback.delete(id)},cmaBoardTools:{cancel(){}},cmaBoardPresentation:{cancel(){}}}};
 vm.createContext(ctx);
 let src=fs.readFileSync('public/study.js','utf8');vm.runInContext(src.slice(src.indexOf('class BoardStudy'),src.indexOf("const help="))+';globalThis.BoardStudy=BoardStudy',ctx);
 for(const id of ['studyOpeningBoard','reviewBoard']){
   ctx.api=async()=>{throw Error('offline')};const study=new ctx.BoardStudy(id,node('host'));
   await study.start('start');assert.equal(study.busy,false);assert.equal(feedback.get(id).kind,'error');assert.match(feedback.get(id).title,/조회 실패/);
   ctx.api=async()=>({fen:'board w - - 0 1',legal:[],terminal:false});await study.load();assert.equal(feedback.get(id).kind,'ready');assert.equal(study.error,null);
 }
 src=fs.readFileSync('public/v8.js','utf8');src=src.slice(src.indexOf("'use strict';"),src.indexOf('const retry=document.createElement'));
 vm.runInContext(src+';globalThis.v8={feedbackOverlay,startGame,showResult,start,restore}',ctx);
 ctx.api=async()=>({});const fen='board w - - 0 1';ctx.fromFen=()=>({a1:'R'});
 ctx.v8.feedbackOverlay({index:48,feedback:{correct:true,original_fen:fen,answer_fen:fen,answer:'a1a4'}});assert.match(feedback.get('testBoard').title,/첫 수/);
 ctx.v8.startGame({board:{turn:'white',squares:{},legal:[]}});assert.match(feedback.get('testBoard').title,/평가 대국/);assert.doesNotMatch(feedback.get('testBoard').title,/정답/);
 ctx.v8.showResult({stage:'test',index:1,delta:null,domains:{},strengths:[],weaknesses:[]});assert.match(feedback.get('testBoard').title,/전체 완료/);
 ctx.api=async()=>{throw Error('offline')};await ctx.v8.restore();assert.equal(feedback.get('testBoard').kind,'error');
 ctx.api=async()=>({active:false});await ctx.v8.restore();assert.equal(feedback.has('testBoard'),false);
 ctx.api=async()=>{throw Error('offline')};await ctx.v8.start();assert.equal(feedback.get('testBoard').kind,'error');
 ctx.api=async()=>({active:true,phase:'game',board:{turn:'white',squares:{},legal:[]}});await ctx.v8.restore();assert.match(feedback.get('testBoard').title,/평가 대국/);
 src=fs.readFileSync('public/learning.js','utf8');ctx.$=node;ctx.renderControls=ctx.lockControls=ctx.renderDashboard=()=>{};
 vm.runInContext('(()=>{let task={message:"complete"},busy=false,generation=0,pendingLoad=false;'+src.slice(src.indexOf('  async function run('),src.indexOf('  async function load('))+';globalThis.runLearning=run;})();',ctx);
 feedback.set('learningBoard',{title:'첫 수 판단 완료',kind:'complete'});
 await ctx.runLearning(async()=>{node('learningMessage').textContent='간격 저장 완료'});
 assert.equal(feedback.get('learningBoard').kind,'complete');assert.equal(node('learningMessage').textContent,'간격 저장 완료');
 console.log('PASS: study initial failure/retry x2; legacy feedback/game/result/start/restore recovery; learning settings preserve verdict');
})().catch(e=>{console.error(e);process.exitCode=1});
