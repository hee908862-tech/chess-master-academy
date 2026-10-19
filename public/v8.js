/* V8 independent 49+1 assessment UI. Keeps v7 game, puzzle, account modules. */
(function(){
'use strict';
const $$=id=>document.getElementById(id);
let current=null,chosen=null,busy=false,showing=false,selectedBase=null,lastAnswer=null,evalClock=null,evalClockAt=0;
const dom=$$('v8DomainList'),info=$$('v8ScoreSummary'),board=$$('testBoard'),progress=$$('testProgress'),status=$$('testStatus');
function evalClockSet(c){evalClock=c||null;evalClockAt=Date.now();evalClockDraw()}
function evalClockDraw(){const el=$$('v8Outcome');if(!el||!evalClock||current?.phase!=='game')return;
 const w=Math.max(0,(evalClock.white_ms||0)-(Date.now()-evalClockAt)),b=evalClock.black_ms||0;
 const fmt=x=>`${Math.floor(x/60000)}:${String(Math.floor(x%60000/1000)).padStart(2,'0')}`;
 el.textContent=`평가 대국 10+5 · 백 ${fmt(w)} · 흑 ${fmt(b)} · 힌트/무르기 없음`;
}
setInterval(evalClockDraw,1000);
function display(msg,klass=''){status.textContent=msg;status.className='notice '+klass;}
function hideOverlay(){const o=$$('v8Overlay');o.hidden=true;}
function feedbackOverlay(data){
 const o=$$('v8Overlay');o.hidden=false;const fb=data.feedback;
 $$('v8Verdict').textContent=fb.correct?'✓ 정답입니다':'✕ 오답입니다';
 $$('v8Verdict').style.color=fb.correct?'#74e2c2':'#ffabb1';
 $$('v8VerdictDetails').textContent=`${fb.domain} · 난이도 ${fb.difficulty}/7 · ${fb.seconds}초 · ${fb.points}점`;
 $$('v8AnswerText').textContent=`모범 착수: ${nameMove(fb.original_fen,fb.answer)}`;
 lastAnswer=fb;
 drawBoard('testBoard',fromFen(fb.answer_fen),{last:[fb.answer.slice(0,2),fb.answer.slice(2,4)]});
 const squares=board.querySelectorAll('.sq');for(const sq of squares){const a=sq.getAttribute('aria-label')?.split(' ')[0];if(a===fb.answer.slice(2,4))sq.classList.add('v8-correct');}
 display('모범 착수와 채점 결과를 확인한 뒤 다음 문제를 누르세요.');
}
function nameMove(fen,uci){const p=fromFen(fen)[uci.slice(0,2)];const sym=({P:'',N:'N',B:'B',R:'R',Q:'Q',K:'K'})[(p||'P').toUpperCase()]||'';return sym+uci.slice(0,2)+' → '+sym+uci.slice(2,4)}
function showQuestion(r){
 current={phase:'questions',q:r.question};chosen=null;hideOverlay();lastAnswer=null;
 progress.textContent=`문항 ${r.index+1} / 49 · ${r.domain} · 난이도 ${r.question.difficulty}/7`;
 display(r.question.description);
 $$('v8Outcome').textContent='문제마다 정답과 걸린 시간을 함께 기록합니다.';
 draw();
}
function draw(){
 if(!current)return;
 if(current.phase==='questions'){
 const q=current.q;const targets=chosen?(q.legal||[]).filter(u=>u.slice(0,2)===chosen).map(u=>({to:u.slice(2,4)})):[];
 drawBoard('testBoard',fromFen(q.fen),{flip:q.fen.split(' ')[1]==='b',selected:chosen,targets,onClick:click});
 }else if(current.phase==='game'){
 const g=current.game;const targets=chosen?(g.legal||[]).filter(m=>m.from===chosen):[];
 drawBoard('testBoard',g.squares,{selected:chosen,targets,last:g.last_move?[g.last_move.slice(0,2),g.last_move.slice(2,4)]:[],onClick:click});
 }
}
async function click(sq){
 if(busy||!current||!['questions','game'].includes(current.phase))return;
 if(chosen===sq){chosen=null;draw();return;}
 const game=current.phase==='game',p=game?current.game.squares:fromFen(current.q.fen);
 const legal=game?(current.game.legal||[]).map(m=>m.from+m.to+(m.promotion||'')):current.q.legal;
 const side=game?(current.game.turn==='black'?'b':'w'):(current.q.fen.split(' ')[1]);
 const friendly=x=>p[x]&&((p[x]===p[x].toUpperCase())===(side==='w'||side==='white'));
 if(!chosen){if(friendly(sq)&&legal.some(m=>m.slice(0,2)===sq)){chosen=sq;draw();}return;}
 const from=chosen,found=legal.find(m=>m.slice(0,2)===from&&m.slice(2,4)===sq);
 if(!found){chosen=friendly(sq)&&legal.some(m=>m.slice(0,2)===sq)?sq:null;draw();return;}
 const promo=await choosePromotion(from,sq,p[from],legal);
 const selectedMove=promo?(from+sq+promo):found;
 chosen=null;busy=true;
 try{
  if(!game){const r=await api('/v8/assessment/answer','POST',{id:current.q.id,move:selectedMove});feedbackOverlay(r);current={phase:'feedback'};}
  else{
   // Draw the validated selected move immediately, before waiting for AI analysis.
   const originalGame=current.game;
   const optimistic={...originalGame,squares:{...originalGame.squares},legal:[],turn:'black',last_move:selectedMove};
   optimistic.squares[sq]=optimistic.squares[from];delete optimistic.squares[from];
   if((originalGame.squares[from]||'').toLowerCase()==='p'&&from[0]!==sq[0]&&!originalGame.squares[sq])delete optimistic.squares[sq[0]+from[1]];
   if(promo)optimistic.squares[sq]=(p[from]===p[from].toUpperCase()?promo.toUpperCase():promo.toLowerCase());
   current={phase:'game',game:optimistic};draw();display('착수가 반영됐습니다. AI가 생각하고 있습니다.');
   const r=await api('/v8/assessment/game-move','POST',{move:selectedMove});evalClockSet(r.clock);
   if(r.done){current={phase:'results'};drawBoard('testBoard',r.board.squares);showResult(r.result);}
   else{current={phase:'game',game:r.board};progress.textContent=`50번째 평가 · 중급 AI 실전 대국`;display('AI가 응수했습니다. 다음 수를 두세요.');draw();}
  }
 }catch(err){display(err.message,'err');restore();}finally{busy=false;}
}
function startGame(r){hideOverlay();chosen=null;current={phase:'game',game:r.board};evalClockSet(r.clock);
 progress.textContent=`50번째 평가 · AI 대국 (10+5)`;
 $$('v8Outcome').textContent='힌트와 무르기 없는 별도 평가 대국입니다. 백으로 착수해 주세요.';
 display('중급 AI와 실제 종료까지 대국합니다. 제한시간: 10분 + 착수당 5초.');draw();}
async function start(){if(!token){tab('profile');return;}if(busy)return;busy=true;
 try{const r=await api('/v8/assessment/start','POST');showQuestion(r);}catch(e){display(e.message,'err')}finally{busy=false;}}
async function next(){if(busy)return;busy=true;
 try{const r=await api('/v8/assessment/next','POST');if(r.phase==='game')startGame(r);else showQuestion(r);}catch(e){display(e.message,'err')}finally{busy=false}}
function showResult(r){hideOverlay();progress.textContent='50단계 종합 평가 완료';
 $$('v8Outcome').textContent=`${r.stage} · 내부 실력 지수 ${r.index}/1000 · ${r.delta===null?'첫 진단':(r.delta>=0?'+':'')+r.delta+' 변동'}`;
 const fmt=n=>n===null||n===undefined?'측정 불가':n.toFixed?.(1)??String(n);
 info.replaceChildren();
 const h=document.createElement('h3');h.textContent=`${r.stage} · ${r.index}점`;info.append(h);
 const p=document.createElement('p');p.textContent=`문제 점수 ${fmt(r.quiz_score)} · AI 실전 정확도 ${fmt(r.game_score)} · ${r.formula}`;info.append(p);
 const grid=document.createElement('div');grid.className='v8-results-grid';
 for(const d of Object.values(r.domains)){
  const el=document.createElement('div');el.className='v8-result-item';
  el.textContent=`${d.label}: ${d.score}점 · ${d.correct}/${d.total}개 · 중앙 풀이시간 ${d.median_seconds}초`;grid.append(el);
 }info.append(grid);
 const advice=document.createElement('p');advice.textContent=`강점: ${r.strengths.join(', ')} / 보완: ${r.weaknesses.join(', ')}. 공식 Elo와 직접 환산되지 않는 내부 지수입니다.`;info.append(advice);
 display('평가 결과가 계정에 저장되었습니다.');loadHistory();loadRecommendations();
}
async function restore(){if(!token)return;try{const r=await api('/v8/assessment/status');if(r.phase==='results'&&r.result){showResult(r.result);return;}if(r.active){if(r.phase==='questions')showQuestion(r);else if(r.phase==='feedback'){current={phase:'feedback'};feedbackOverlay(r);}else if(r.phase==='game')startGame(r);}else if(r.recent)showResult(r.recent);else{hideOverlay();}}catch(e){display(e.message,'err')}}
function renderProfile(data){if(!data)return;
 const p=$$('v8ProfileResult');if(!p)return;
 const last=data.latest;
 if(!last){p.textContent='아직 50단계 진단 기록이 없습니다.';return;}
 const delta=last.delta===null?'최초 진단':`이전 대비 ${last.delta>=0?'+':''}${last.delta}`;
 p.textContent=`${last.stage} · 내부 실력 지수 ${last.index}/1000 · ${delta}`;
 const h=$$('v8History');h.replaceChildren();
 for(const d of (data.history||[]).slice(-10).reverse()){
  const item=document.createElement('div');item.className='v8-result-item';item.textContent=`${d.at.slice(0,10)} · ${d.stage} · ${d.index}점 (문제 ${d.quiz_score}, AI ${d.game_score??'미측정'})`;h.append(item);
 }
}
async function loadRecommendations(){
 if(!token)return;
 try{
  const d=await api('/v8/recommendations'), box=$$('v8RecommendationList');
  box.replaceChildren();if(!d.ready)return;
  const title=document.createElement('h3');title.textContent='진단 기반 보완 과목 추천';box.append(title);
  for(const course of d.courses){
   const btn=document.createElement('button');btn.className='btn';
   btn.style.textAlign='left';btn.textContent=`${course.reason} · 실습 열기`;
   btn.onclick=()=>{tab('learn');const raw=(course.id+' '+course.reason).toLowerCase();const theme=raw.includes('메이트')||raw.includes('mate')?'mateIn2':raw.includes('킹')||raw.includes('endgame')?'endgame':raw.includes('방어')||raw.includes('defen')?'defensiveMove':raw.includes('포크')||raw.includes('fork')?'fork':raw.includes('핀')||raw.includes('pin')?'pin':'advantage';if(!window.cmaOpenV9Course?.(theme)){const x=document.getElementById('v9CourseHistory');if(x)x.textContent='추천 과목 연결을 확인할 수 없습니다. 과목 목록에서 직접 선택하세요.';}};
   box.append(btn);
  }
 }catch(e){}
}
async function loadHistory(){if(!token)return;try{const d=await api('/v8/assessment/history');renderProfile(d);loadRecommendations()}catch(e){}}
$$('v8Start').onclick=start;$$('v8Next').onclick=next;
$$('startTest').style.display='none';
$$('v6AssessmentFeedback').style.display='none';
const origTab=tab;
tab=function(id){origTab(id);if(id==='assessment'){restore();}if(id==='profile'){loadHistory();}};
// Older assessment helpers remain available for past progress but are no longer used.
setTimeout(()=>{loadHistory();restore()},600);
})();

/* Curated mate-in-three interactive challenge; server checks every ply. */
(function(){
'use strict';
const byId=id=>document.getElementById(id);
let task=null,selected=null,locked=false;
const button=byId('v8MateStart');if(!button)return;
function msg(t){byId('v8MateStatus').textContent=t;}
function render(){if(!task)return;
 const f=fromFen(task.fen),legal=task.legal||[];
 drawBoard('v8MateBoard',f,{selected,targets:selected?legal.filter(u=>u.slice(0,2)===selected).map(u=>({to:u.slice(2,4)})):[],onClick:tap});
 byId('v8MateStep').textContent=task.finished?'완료':`메이트 인 3 · ${task.step}/3번째 백 착수`;
}
async function start(){if(!token){tab('profile');return;}if(locked)return;locked=true;
 try{task=await api('/v8/mate3/start','POST');selected=null;render();msg(task.message);}catch(e){msg(e.message)}finally{locked=false}}
async function tap(s){if(!task||task.finished||locked)return;
 const pos=fromFen(task.fen);
 if(selected===s){selected=null;render();return;}
 if(!selected){if(pos[s]&&pos[s]===pos[s].toUpperCase()){selected=s;render()}return;}
 const from=selected,m=task.legal.find(u=>u.slice(0,2)===from&&u.slice(2,4)===s);
 if(!m){selected=pos[s]&&pos[s]===pos[s].toUpperCase()?s:null;render();return;}
 selected=null;locked=true;
 try{const r=await api('/v8/mate3/move','POST',{move:m});task=r;render();msg(r.message);if(r.correct)playMoveSound('move');}
 catch(e){msg(e.message)}finally{locked=false}
}
button.onclick=start;
})();
