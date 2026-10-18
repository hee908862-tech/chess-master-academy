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
  $('practiceCount').textContent='새 문제 '+(++practiceAttempts)+'회차';
  notice('puzzleStatus','백 차례입니다. 전술을 찾아 기물을 이동시켜 주세요.');
  drawPracticeBoard();
 }catch(err){notice('puzzleStatus',err.message,'err')}
 finally{btn.disabled=false}
}
function drawPracticeBoard(){if(!activePractice)return;drawBoard('puzzleBoard',fromFen(activePractice.fen),{selected:practiceSelected,onClick:practiceClick})}
async function practiceClick(square){
 if(!activePractice||practicePending)return;
 ensureAudio();const position=fromFen(activePractice.fen);
 if(!practiceSelected){if(!position[square]||position[square]!==position[square].toUpperCase())return;practiceSelected=square;drawPracticeBoard();return}
 const move=practiceSelected+square;practiceSelected=null;practicePending=true;drawPracticeBoard();
 const type=position[square]?'capture':'move';playMoveSound(type);
 try{
  const result=await api('/practice/answer','POST',{exercise_id:activePractice.id,move});
  notice('puzzleStatus',result.explanation,result.correct?'ok':'err');
  $('puzzleSolved').textContent=result.correct?'✓ 정답':'오답 · 재학습';
  await refreshPuzzleStats();
 }catch(err){notice('puzzleStatus',err.message,'err')}
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
