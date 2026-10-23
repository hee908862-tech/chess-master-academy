/* V6 evidence-led curriculum and assessment feedback layer. Runs after prior modules. */
let c6Course=null,c6Selected=null,c6Pending=false,c6CourseId=null;
const c6Meta={fork:'기물 두 개를 동시에 공격하는 안전한 포크',pin:'왕 뒤에 있는 기물을 움직이지 못하게 하는 핀',skewer:'킹을 먼저 공격하고 뒤의 고가치 기물을 노리는 스큐어',discovered:'앞의 기물이 비켜 발견 체크를 여는 전술',double:'비숍 등 하나의 기물로 여러 대상을 공격',safecheck:'합법적인 체크',capture:'큰 기물 포획',mate:'체크메이트',opening:'기물 전개',endgame:'폰 승격 방향의 전진'};
const coursesBox=document.getElementById('v6CourseMenu');
const feedbackBox=document.getElementById('v6AssessmentFeedback');
const recommendBox=document.getElementById('v6Recommendations');
const legacyLessonList=document.getElementById('lessonList');
legacyLessonList.style.display='none';
$('lessonQuizBox').style.display='none';$('completeLesson').style.display='none';
$('restartGuided').textContent='선택 과목 다시 시작';

async function c6LoadCourses(){
 if(!token){coursesBox.textContent='로그인 후 세부 과목을 선택할 수 있습니다.';return;}
 try{
  const items=await api('/v6/courses'); coursesBox.replaceChildren();
  const grid=document.createElement('div');grid.className='v6-course-grid';
  items.forEach(it=>{
   const b=document.createElement('button');b.className='v6-course'+(it.completed?' completed':'');
   const name=document.createElement('strong');name.textContent=it.name;
   const desc=document.createElement('small');desc.textContent=it.description;
   const meta=document.createElement('span');meta.textContent=`${it.level} · ${it.count}개 상황 · ${it.completed?'✓ 완료':'연습 가능'}`;
   b.append(name,desc,meta);b.onclick=()=>c6Begin(it.id);grid.append(b);
  }); coursesBox.append(grid);
 }catch(e){coursesBox.textContent=e.message}
}
async function c6LoadSuggestions(){
 return; // The legacy v6 suggestion renderer is retired.
 if(!token)return;
 try{const d=await api('/v6/diagnostic/recommend');recommendBox.replaceChildren();
  const head=document.createElement('strong');head.textContent=`진단 결과에 따른 추천 · ${d.stage}`;recommendBox.append(head);
  for(const i of d.suggestions.slice(0,7)){
   const b=document.createElement('button');b.className='v6-suggestion';b.textContent=`${i.name} — ${i.reason}`;b.onclick=()=>{tab('learn');c6Begin(i.id)};recommendBox.append(b);
  }
 }catch(e){recommendBox.textContent=e.message}
}
function c6Draw(){window.cmaExplore?.offer('guidedBoard',null);
 if(!c6Course || c6Course.done)return;
 const pos=fromFen(c6Course.fen);
 const targets=c6Selected?(c6Course.legal||[]).filter(s=>s.slice(0,2)===c6Selected).map(s=>({to:s.slice(2,4)})):[];
 drawBoard('guidedBoard',pos,{selected:c6Selected,targets,onClick:c6Click});
 $('v5ScenarioProgress').textContent=`${c6Course.topic} · ${c6Course.index+1}/${c6Course.total} 문제`;
 $('guidedPrompt').textContent=`${c6Course.prompt}\n연습 목표: ${c6Meta[c6Course.objective]||c6Course.objective}`;
 $('guidedPrompt').style.whiteSpace='pre-line';
}
async function c6Begin(id){
 if(!ready())return;c6CourseId=id;c6Pending=true;c6Selected=null;
 try{c6Course=await api(`/v6/course/${id}/start`,'POST');c6Draw();$('lessonHeading').textContent=c6Course.topic+' · 포지션별 실습';
  $('lessonBody').textContent='정답 좌표를 암기하는 과정이 아닙니다. 합법 수 중 실제 학습 목표를 만족하는 수를 찾으세요. 진행은 과목별로 따로 저장됩니다.';
  $('lessonStatus').textContent='';}
 catch(e){$('guidedPrompt').textContent=e.message}finally{c6Pending=false}
}
async function c6Click(s){
 if(!c6Course||c6Course.done||c6Pending)return;
 if(c6Selected===s){c6Selected=null;c6Draw();return;}
 const pos=fromFen(c6Course.fen);
 if(!c6Selected){if(pos[s]&&pos[s]===pos[s].toUpperCase()){c6Selected=s;c6Draw()}return;}
 const from=c6Selected;
 if(!(c6Course.legal||[]).some(m=>m.slice(0,2)===from&&m.slice(2,4)===s)){
  c6Selected=pos[s]&&pos[s]===pos[s].toUpperCase()?s:null;c6Draw();return;
 }
 c6Selected=null;c6Pending=true;
 try{
  const r=await api('/v6/course/move','POST',{move:from+s});
  if(!r.correct){c6Draw();$('lessonStatus').textContent='힌트: '+r.message;return;}
  window.cmaBoardPresentation.transition('guidedBoard',from+s,()=>drawBoard('guidedBoard',fromFen(r.played_fen),{last:[from,s]}));
  window.cmaExplore?.offer('guidedBoard',r.played_fen);$('guidedPrompt').textContent='✓ '+r.message;
  if(r.done){c6Course={done:true};$('v5ScenarioProgress').textContent='교육 과목 완료';
   $('lessonStatus').textContent=r.passed?`✓ 숙련 기준 달성 · 첫 시도 ${r.first_try}/${r.total}`:`연습 완료 · 첫 시도 ${r.first_try}/${r.total}. 숙련 확인을 위해 다시 도전하세요.`;
   await c6LoadCourses();await c6LoadSuggestions();await refreshSummaryOnly();
  }else {c6Course=r.next;setTimeout(()=>{if(c6Course&&!c6Course.done)c6Draw()},1000)}
 }catch(e){$('lessonStatus').textContent=e.message;c6Draw()}
 finally{c6Pending=false;}
}
$('restartGuided').onclick=()=>c6CourseId&&c6Begin(c6CourseId);
// Prevent legacy course auto-start from racing against the new topic-based curriculum.
guidedDone=true;
// Old broad subjects are deliberately removed from the academy UI, including review habits.
const oldV6Tab=tab;
tab=function(id){oldV6Tab(id);if(id==='learn'){c6LoadCourses();c6LoadSuggestions();}};

// Exam: submit => feedback overlay => explicit advance. Never auto-move to the next question.
let c6Feedback=null;
function c6ClearFeedback(){c6Feedback=null;feedbackBox.hidden=true;feedbackBox.replaceChildren()}
function c6DisplayFeedback(data){
 c6Feedback=data.feedback||data;v3Busy=false;v3Selected=null;
 feedbackBox.replaceChildren();feedbackBox.hidden=false;
 const correct=c6Feedback.correct;
 const status=document.createElement('h3');status.textContent=correct?'✓ 정답입니다':'정답 수순을 확인하세요';
 const explanation=document.createElement('p');explanation.textContent=c6Feedback.explanation;
 const code=document.createElement('div');code.className='v6-answer-code';code.textContent=`모범 착수: ${c6Feedback.solution?.slice(0,2)||'—'} → ${c6Feedback.solution?.slice(2,4)||'—'}`;
 const btn=document.createElement('button');btn.className='btn primary';btn.textContent='다음 문제 →';btn.onclick=c6Advance;
 feedbackBox.append(status,explanation,code,btn);
 $('testProgress').textContent=`채점 완료 · ${(data.index??0)+1} / 25`;
 notice('testStatus',correct?'정답입니다. 다음 문제 버튼을 눌러 진행하세요.':'체스판에 정답 수순을 재생했습니다. 확인 후 넘어가세요.',correct?'ok':'');
 if(c6Feedback.answer_fen){window.cmaBoardPresentation.transition('testBoard',c6Feedback.solution,()=>drawBoard('testBoard',fromFen(c6Feedback.answer_fen),{last:c6Feedback.solution?[c6Feedback.solution.slice(0,2),c6Feedback.solution.slice(2,4)]:[]}));}
}
async function c6Advance(){if(v3Busy||!c6Feedback)return;v3Busy=true;
 try{const r=await api('/v6/assessment/advance','POST');c6ClearFeedback();if(r.phase==='game')v3StartGame(r);else v3QuestionShown(r)}
 catch(e){notice('testStatus',e.message,'err')}finally{v3Busy=false}
}
const baseV3QuestionShown=v3QuestionShown;
v3QuestionShown=function(data){if(data?.phase==='feedback'){c6DisplayFeedback(data);return;}c6ClearFeedback();baseV3QuestionShown(data)};
const baseV3StartGame=v3StartGame;
v3StartGame=function(data){c6ClearFeedback();baseV3StartGame(data)};
const baseV3Click=v3TestClick;
v3TestClick=async function(s){
 if(v3Test?.phase==='game')return baseV3Click(s);
 if(v3Busy||!v3Question||c6Feedback)return;
 if(v3Selected===s){v3Selected=null;v3TestDraw();return;}
 const pieces=fromFen(v3Question.fen),moves=v3Question.legal||[];
 if(!v3Selected){if(pieces[s]&&pieces[s]===pieces[s].toUpperCase()){v3Selected=s;v3TestDraw()}return;}
 const uci=moves.find(m=>m.slice(0,2)===v3Selected&&m.slice(2,4)===s);
 if(!uci){v3Selected=pieces[s]&&pieces[s]===pieces[s].toUpperCase()?s:null;v3TestDraw();return;}
 const from=v3Selected;v3Selected=null;v3Busy=true;
 try{const r=await api('/assessment-v3/answer','POST',{question_id:v3Question.id,move:uci});c6DisplayFeedback(r)}
 catch(e){notice('testStatus',e.message,'err');v3TestDraw()}finally{v3Busy=false}
};
const v6BaseStart=v3Start;
v3Start=async function(){c6ClearFeedback();await v6BaseStart()};
(async()=>{if(token){try{const r=await api('/assessment-v3/status');if(r.phase==='feedback')c6DisplayFeedback(r)}catch(e){}c6LoadCourses();c6LoadSuggestions();}})();

// Restore post-submission feedback without skipping a graded item.
v3Restore=async function(){if(!token)return;try{const r=await api('/assessment-v3/status');if(!r.active)return;if(r.phase==='feedback')c6DisplayFeedback(r);else if(r.phase==='game')v3StartGame(r);else v3QuestionShown(r)}catch(e){}};
