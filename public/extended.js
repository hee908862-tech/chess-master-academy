window.practiceModeInitialized=true;
/* Integrated practice / assessment / lesson mastery layer. Reuses v2 board and account API. */
let activePractice=null,practiceSelected=null,practicePending=false;
let activeTest=null,testSelected=null,testPending=false;
let activeQuiz=null,quizPending=false;
let practiceAttempts=0;

async function freshPractice(){
 if(!ready())return;
 const btn=$('freshPuzzle');btn.disabled=true;
 try{
  activePractice=await api('/practice/next','POST');practiceSelected=null;practicePending=false;
  $('puzzleTitle').textContent=activePractice.theme;
  $('puzzleDesc').textContent=activePractice.description;
  $('puzzleLevel').textContent=activePractice.difficulty;
  $('puzzleSolved').textContent='미해결';
  $('nextPuzzle').style.display='none';
  $('practiceCount').textContent='새 문제 '+(++practiceAttempts)+'회차';
  notice('puzzleStatus','백 차례입니다. 전술을 찾아 기물을 이동시켜 주세요.');
  drawPracticeBoard();
 }catch(err){notice('puzzleStatus',err.message,'err')}
 finally{btn.disabled=false}
}
function drawPracticeBoard(){if(!activePractice)return;drawBoard('puzzleBoard',fromFen(activePractice.fen),{selected:practiceSelected,targets:practiceSelected?moveTargets(activePractice.fen,activePractice.legal||[],practiceSelected):[],onClick:practiceClick})}
async function practiceClick(square){
 if(!activePractice||practicePending)return;
 const position=fromFen(activePractice.fen);
 if(practiceSelected===square){practiceSelected=null;drawPracticeBoard();return;}
 if(!practiceSelected){if(!position[square]||position[square]!==position[square].toUpperCase())return;practiceSelected=square;drawPracticeBoard();return;}
 const from=practiceSelected,move=from+square;
 // This is the same server supplied legal list used for the green target markers.
 const allowed=(activePractice.legal||[]).some(u=>u===move||u.slice(0,4)===move);
 if(!allowed){practiceSelected=position[square]&&position[square]===position[square].toUpperCase()?square:null;drawPracticeBoard();return;}
 practiceSelected=null;practicePending=true;drawPracticeBoard();
 try{
  const result=await api('/practice/answer','POST',{exercise_id:activePractice.id,move});
  if(result.correct){
   ensureAudio(); const optimistic={...position,[square]:position[from]};delete optimistic[from];
   animateBoardTransition('puzzleBoard',from,square,()=>drawBoard('puzzleBoard',optimistic,{last:[from,square]}));
   playMoveSound(position[square]?'capture':'move');
  } else drawPracticeBoard();
  notice('puzzleStatus',result.explanation,result.correct?'ok':'err');
  $('puzzleSolved').textContent=result.correct?'✓ 정답':'오답 · 재학습';
  $('nextPuzzle').style.display=result.correct?'inline-flex':'none';
  await refreshPuzzleStats();
 }catch(err){notice('puzzleStatus',err.message,'err');drawPracticeBoard();}
 finally{practicePending=false;}
}
$('freshPuzzle').addEventListener('click',freshPractice);
// The practice stream overrides old list selection: a learner cannot pick only remembered ids.
$('puzzleSelect').closest('.btn-row').style.display='none';
$('nextPuzzle').onclick=freshPractice;
$('puzzleHint').onclick=()=>{if(activePractice)notice('puzzleStatus','힌트: 체크, 잡기, 위협 순으로 후보수를 조사하세요. 힌트 사용 여부는 향후 숙련도에 별도 반영됩니다.');};
$('puzzleReset').onclick=()=>{practiceSelected=null;drawPracticeBoard();};

function drawTestBoard(){if(!activeTest?.question)return;drawBoard('testBoard',fromFen(activeTest.question.fen),{selected:testSelected,onClick:clickTest})}
async function newTest(){
 if(!ready())return;
 const btn=$('startTest');btn.disabled=true;
 try{activeTest=await api('/test/start','POST');testSelected=null;testPending=false;
  $('testProgress').textContent='문항 1 / 12';
  $('testResult').textContent='평가가 진행 중입니다. 매 문항 1회만 제출됩니다.';
  notice('testStatus',activeTest.question.description);
  drawTestBoard();
 }catch(err){notice('testStatus',err.message,'err')}
 finally{btn.disabled=false}
}
async function clickTest(sq){
 if(!activeTest?.question||testPending)return;
 ensureAudio();const board=fromFen(activeTest.question.fen);
 if(!testSelected){if(!board[sq]||board[sq]!==board[sq].toUpperCase())return;testSelected=sq;drawTestBoard();return}
 const move=testSelected+sq;testSelected=null;testPending=true;
 try{
  const data=await api('/test/answer','POST',{question_id:activeTest.question.id,move});
  if(data.done){
   activeTest={question:null};
   $('testBoard').innerHTML='';
   $('testProgress').textContent='진단 완료';
   $('testResult').textContent=`${data.result.stage} · ${data.result.correct}/${data.result.total}문제 정답 · ${data.result.confidence}. 보완 분야: ${data.result.weaknesses.join(', ')||'복합 계산'}.`;
   notice('testStatus','평가가 완료됐습니다. 추천 학습을 통해 개선한 후 재평가해 보세요.','ok');
  }else{
   activeTest.question=data.question;
   $('testProgress').textContent=`문항 ${data.index+1} / ${data.total}`;
   notice('testStatus',data.question.description);
   drawTestBoard();
  }
 }catch(err){notice('testStatus',err.message,'err')}
 finally{testPending=false}
}
$('startTest').onclick=newTest;
drawBoard('testBoard',fromFen(chessStart));

// Replace easy 'complete lesson' action with server-validated concept checks.
async function openQuiz(){
 if(!ready())return;
 try{
  activeQuiz=await api('/lessons/quiz/'+encodeURIComponent(selectedLesson));
  const box=$('lessonQuizBox');box.replaceChildren();
  const h=document.createElement('strong');h.textContent=activeQuiz.question;box.appendChild(h);
  const choices=document.createElement('div');choices.className='btn-row';choices.style.marginTop='12px';
  activeQuiz.choices.forEach((label,i)=>{
   const b=document.createElement('button');b.className='btn';b.textContent=label;
   b.onclick=()=>submitQuiz(i);choices.appendChild(b);
  });
  box.appendChild(choices);
  $('completeLesson').textContent='다른 확인 문제 보기';
 }catch(err){notice('lessonStatus',err.message,'err')}
}
async function submitQuiz(choice){
 if(!activeQuiz||quizPending)return;quizPending=true;
 try{
  const result=await api('/lessons/answer','POST',{lesson_id:activeQuiz.lesson_id,choice});
  activeQuiz=null;
  $('lessonQuizBox').textContent=result.completed?'핵심 개념 확인 완료. 이 교육 과정이 완료 처리되었습니다.':`${result.message} 연속 확인 진행도 ${result.progress}/3. 다음 문제를 풀어보세요.`;
  $('completeLesson').textContent='다음 확인 문제';
  notice('lessonStatus',result.completed?'학습 이수 기록이 계정에 저장됐습니다.':result.message,result.correct?'ok':'err');
  if(result.completed)await refresh();
 }catch(err){notice('lessonStatus',err.message,'err')}
 finally{quizPending=false}
}
$('completeLesson').onclick=openQuiz;
const oldOpenLesson=openLesson;
openLesson=function(id){oldOpenLesson(id);activeQuiz=null;$('lessonQuizBox').textContent='설명을 숙지한 뒤 확인 문제 3개를 연속으로 풀어야 교육이 완료됩니다.';$('completeLesson').textContent='이해도 확인 문제';};

const originalRefresh=refresh;
refresh=async function(){await originalRefresh();if(user?.state?.assessment){const a=user.state.assessment;$('testResult').textContent=`최근 예비 진단: ${a.stage}, ${a.correct}/${a.total} 정답. 보완 분야: ${(a.weaknesses||[]).join(', ')||'없음'}.`; $('homeGrade').textContent=a.stage;}};
// New random practice on entry to puzzle page.
document.querySelectorAll('[data-tab="puzzle"],[data-go="puzzle"]').forEach(btn=>btn.addEventListener('click',()=>{if(!activePractice||practicePending)freshPractice()}));

/* V3: lesson board practice & 25-question + AI assessment */
let guided=null,guidedSelected=null,guidedBusy=false,guidedDone=false;
let v3Test=null,v3Selected=null,v3Busy=false,v3Game=null,v3Question=null,v3Result=null;

function moveTargets(fen,legal,source){return legal.filter(uci=>uci.slice(0,2)===source).map(uci=>({to:uci.slice(2,4)}));}
function guidedDraw(){if(!guided)return;drawBoard('guidedBoard',fromFen(guided.fen),{selected:guidedSelected,targets:guidedSelected?moveTargets(guided.fen,guided.legal,guidedSelected):[],onClick:guidedClick})}
async function beginGuided(){if(!token)return;guidedBusy=false;guidedDone=false;guidedSelected=null;
 try{guided=await api('/guided/start/'+encodeURIComponent(selectedLesson),'POST');$('guidedPrompt').textContent=`실습 1 / ${guided.total} · ${guided.prompt}`;guidedDraw();$('completeLesson').disabled=true;$('lessonQuizBox').textContent='체스판에서 개념을 직접 실습하면 이해도 확인 문제가 활성화됩니다.';}
 catch(e){$('guidedPrompt').textContent=e.message;}
}
async function guidedClick(s){if(guidedBusy||!guided||guidedDone)return;
 if(guidedSelected===s){guidedSelected=null;guidedDraw();return;}
 const pos=fromFen(guided.fen);
 if(!guidedSelected){if(!pos[s]||pos[s]!==pos[s].toUpperCase())return;guidedSelected=s;guidedDraw();return;}
 if(!guided.legal.includes(guidedSelected+s)){if(pos[s]&&pos[s]===pos[s].toUpperCase()){guidedSelected=s;guidedDraw();}else{guidedSelected=null;guidedDraw()}return;}
 const move=guidedSelected+s;guidedSelected=null;guidedBusy=true;
 try{const r=await api('/guided/move','POST',{lesson_id:selectedLesson,move});
  if(r.correct){playMoveSound(pos[s]?'capture':'move');if(r.done){guidedDone=true;guided=null;$('guidedPrompt').textContent=r.message;$('completeLesson').disabled=false;$('lessonQuizBox').textContent='실습 완료! 이제 이해도 확인 문제를 진행하세요.';drawBoard('guidedBoard',pos);}else{guided=r;$('guidedPrompt').textContent=`실습 ${r.index+1} / ${r.total} · ${r.prompt}`;guidedDraw()}}
  else{$('guidedPrompt').textContent=r.message;guidedDraw()}}
 catch(e){$('guidedPrompt').textContent=e.message;}finally{guidedBusy=false}
}
const lessonOpenV2=openLesson;
openLesson=function(id){lessonOpenV2(id);guided=null;guidedDone=false;$('completeLesson').disabled=true;beginGuided();};
$('restartGuided').onclick=beginGuided;
const quizAfterPractice=openQuiz;
openQuiz=async function(){if(!guidedDone){notice('lessonStatus','체스판 실습을 완료한 뒤 이해도 문제를 풀 수 있습니다.');return;}await quizAfterPractice();};

function v3TestDraw(){
 if(v3Test?.phase==='game'&&v3Game){drawBoard('testBoard',v3Game.squares,{selected:v3Selected,targets:v3Selected?v3Game.legal.filter(m=>m.from===v3Selected):[],last:v3Game.last_move?[v3Game.last_move.slice(0,2),v3Game.last_move.slice(2,4)]:[],onClick:v3TestClick});return;}
 if(!v3Question)return;
 drawBoard('testBoard',fromFen(v3Question.fen),{selected:v3Selected,targets:v3Selected?moveTargets(v3Question.fen,v3Question.legal,v3Selected):[],onClick:v3TestClick});
}
function v3QuestionShown(data){v3Test={phase:'questions'};v3Question=data.question;v3Selected=null;v3Busy=false;
 $('testProgress').textContent=`${data.domain} · ${data.index+1} / 25`;
 notice('testStatus',data.question.description);
 $('testResult').textContent='현재 진단 진행 중 · 시험 종료 전 정답을 보여주지 않습니다.';
 v3TestDraw();}
function v3StartGame(data){v3Test={phase:'game'};v3Question=null;v3Game=data.board;v3Selected=null;v3Busy=false;
 $('testProgress').textContent='중급 AI 평가 대국 · 0/12수';
 $('testResult').textContent='25문항이 끝났습니다. 중급 AI와의 대국을 기반으로 실전 판단을 평가합니다.';
 notice('testStatus','백으로 착수하세요. 12회의 착수 또는 게임 종료까지 진행합니다.');
 v3TestDraw();}
async function v3Start(){if(!ready())return;$('startTest').disabled=true;
 try{const data=await api('/assessment-v3/start','POST');v3QuestionShown(data)}
 catch(e){notice('testStatus',e.message,'err')}finally{$('startTest').disabled=false}}
async function v3TestClick(s){if(v3Busy||!v3Test)return;
 if(v3Selected===s){v3Selected=null;v3TestDraw();return;}
 const isGame=v3Test.phase==='game';const board=isGame?v3Game?.squares:fromFen(v3Question.fen);
 const moves=isGame?v3Game?.legal.map(x=>x.from+x.to+(x.promotion||'')):v3Question.legal;
 if(!board||!moves)return;
 if(!v3Selected){if(!board[s]||board[s]!==board[s].toUpperCase())return;v3Selected=s;v3TestDraw();return;}
 const picked=moves.find(x=>x.slice(0,2)===v3Selected&&x.slice(2,4)===s);
 if(!picked){if(board[s]&&board[s]===board[s].toUpperCase())v3Selected=s;else v3Selected=null;v3TestDraw();return;}
 const from=v3Selected;v3Selected=null;v3Busy=true;
 try{
  if(isGame){const r=await api('/assessment-v3/game-move','POST',{from_sq:from,to_sq:s,promotion:'q'});playMoveSound(board[s]?'capture':'move');
   if(r.done){v3Game=r.board;v3Test=null;v3Result=r.result;v3TestDraw();showV3Result(r.result);}
   else{v3Game=r.board;$('testProgress').textContent=`중급 AI 평가 대국 · ${r.white_moves}/12수`;notice('testStatus','AI 응수가 끝났습니다. 다음 수를 두세요.');v3TestDraw();}}
  else{const r=await api('/assessment-v3/answer','POST',{question_id:v3Question.id,move:from+s});playMoveSound(board[s]?'capture':'move');if(r.phase==='game')v3StartGame(r);else v3QuestionShown(r)}
 }catch(e){notice('testStatus',e.message,'err');v3TestDraw();}
 finally{v3Busy=false}
}
function showV3Result(r){
 const scoreRows=Object.entries(r.skills||{}).map(([key,score])=>`${key} ${score}점`).join(' · ');
 $('testProgress').textContent='종합 진단 완료';
 $('testResult').textContent=`${r.stage} | ${r.correct}/25문항 | ${scoreRows}\n강점: ${(r.strengths||[]).join(', ')||'추가 관찰 필요'}\n보완: ${(r.weaknesses||[]).join(', ')}\n추천 교육: ${(r.recommendations||[]).join(', ')}\nAI 대국: ${r.game?.white_moves||0}수, 평균 평가 차이 ${r.game?.avg_evaluation_loss_cp??0}cp (${r.game?.evaluation_method||'참고 지표'})\n실전 강점: ${(r.game_strengths||[]).join(', ')||'추가 관찰 필요'}\n실전 보완: ${(r.game_weaknesses||[]).join(', ')||'뚜렷한 문제 미발견'}\n${r.confidence}`;
 $('testResult').style.whiteSpace='pre-line';
 notice('testStatus','진단 결과를 개인 기록에 저장했습니다. 추천 과정을 통해 학습하세요.','ok');
 $('homeGrade').textContent=r.stage;
}
$('startTest').onclick=v3Start;
const previousRefreshV3=refresh;
refresh=async function(){await previousRefreshV3();if(!user)return;
 const r=user.state?.assessment;
 if(r?.skills)showV3Result(r);
 const show=!r?.skills&&!sessionStorage.getItem('cma_diagnosis_dismissed');
 $('diagnosisInvite').style.display=show?'flex':'none';};
$('inviteStart').onclick=()=>{tab('assessment');v3Start();};
$('inviteLater').onclick=()=>{sessionStorage.setItem('cma_diagnosis_dismissed','1');$('diagnosisInvite').style.display='none';};
// Preserve unfinished assessment if a learner reconnects from another device.
async function v3Restore(){if(!token)return;try{const r=await api('/assessment-v3/status');if(!r.active)return;if(r.phase==='game')v3StartGame(r);else v3QuestionShown(r)}catch(e){}}
const priorAuthV3=auth;
auth=async function(mode){await priorAuthV3(mode);if(token){await v3Restore();if(user&&!user.state?.assessment?.skills){tab('home');$('diagnosisInvite').style.display='flex';}}};
const prevTabV3=tab;
tab=function(id){prevTabV3(id);if(id==='learn'&&token&&!guided&&!guidedDone)beginGuided()};
v3Restore();
