/* v5 integrated learning flows; existing account and games are backward compatible. */
let v5Review=null,v5ReviewIndex=0,v5Scenario=null,v5ScenarioSelected=null,v5ScenarioBusy=false,v5HintMove=null;
const v5UserNotice=id=>$(id);

// Puzzle replays require server re-arming, not only visual reset.
$('puzzleReset').onclick=async()=>{
 if(!ready()||!activePractice)return;
 try{
  activePractice=await api('/practice/retry','POST');practiceSelected=null;practicePending=false;
  $('nextPuzzle').style.display='none';$('v5NextPuzzle').style.display='none';
  $('puzzleSolved').textContent='재도전';notice('puzzleStatus','같은 퍼즐을 처음부터 다시 풀 수 있습니다.');drawPracticeBoard();
 }catch(e){notice('puzzleStatus',e.message,'err')}
};
const v5PracticeClick=practiceClick;
practiceClick=async function(s){
 const wasPending=practicePending;
 await v5PracticeClick(s);
 if(!wasPending&&!practicePending&&$('puzzleSolved').textContent.includes('정답'))$('v5NextPuzzle').style.display='inline-flex';
};
$('v5NextPuzzle').onclick=async()=>{await freshPractice();$('v5NextPuzzle').style.display='none'};
const v5FreshPractice=freshPractice;
freshPractice=async function(){await v5FreshPractice();$('v5NextPuzzle').style.display='none'};

// Standalone miniature tactical scenes; never a generic full opening game.
function v5ScenarioRender(){
 if(!v5Scenario||v5Scenario.done)return;
 const pos=fromFen(v5Scenario.fen);
 const targets=v5ScenarioSelected?(v5Scenario.legal||[]).filter(u=>u.slice(0,2)===v5ScenarioSelected).map(u=>({to:u.slice(2,4)})):[];
 drawBoard('guidedBoard',pos,{selected:v5ScenarioSelected,targets,onClick:v5ScenarioClick});
 $('v5ScenarioProgress').textContent=`${v5Scenario.index+1} / ${v5Scenario.total} · 실제 포지션 실습`;
 academyText(v5Scenario.prompt);
}
async function v5ScenarioStart(){
 if(!ready())return;
 v5ScenarioBusy=true;v5ScenarioSelected=null;
 try{
  v5Scenario=await api('/academy/scenario/start/'+encodeURIComponent(selectedLesson),'POST');
  $('completeLesson').style.display='none';$('lessonQuizBox').textContent='각기 다른 포지션을 직접 해결한 뒤 다음 상황으로 넘어갑니다.';
  v5ScenarioRender();
 }catch(e){academyText(e.message)}finally{v5ScenarioBusy=false}
}
async function v5ScenarioClick(square){
 if(!v5Scenario||v5ScenarioBusy||v5Scenario.done)return;
 if(v5ScenarioSelected===square){v5ScenarioSelected=null;v5ScenarioRender();return}
 const pos=fromFen(v5Scenario.fen);
 if(!v5ScenarioSelected){if(pos[square]&&pos[square]===pos[square].toUpperCase()){v5ScenarioSelected=square;v5ScenarioRender()}return}
 const from=v5ScenarioSelected;
 if(!(v5Scenario.legal||[]).some(u=>u.slice(0,2)===from&&u.slice(2,4)===square)){
  v5ScenarioSelected=pos[square]&&pos[square]===pos[square].toUpperCase()?square:null;v5ScenarioRender();return;
 }
 v5ScenarioSelected=null;v5ScenarioBusy=true;
 try{
  const r=await api('/academy/scenario/move','POST',{lesson_id:selectedLesson,move:from+square});
  if(!r.correct){academyText(r.message);v5ScenarioRender();return}
  playMoveSound(pos[square]?'capture':'move');
  drawBoard('guidedBoard',fromFen(r.played_fen),{last:[from,square]});
  academyText('✓ '+r.explanation+'\n다른 상황에서도 같은 원리를 적용해 보세요.');
  if(r.done){v5Scenario={done:true};$('v5ScenarioProgress').textContent='실습 완료';$('lessonQuizBox').textContent='서로 다른 실전 포지션을 완료했습니다. 학습 기록이 저장되었습니다.';await refreshSummaryOnly()}
  else{v5Scenario=r.next;setTimeout(()=>{if(v5Scenario&&!v5Scenario.done)v5ScenarioRender()},850)}
 }catch(e){academyText(e.message);v5ScenarioRender()}finally{v5ScenarioBusy=false}
}
openLesson=function(id){
 selectedLesson=id;
 const l=lessons.find(x=>x[0]===id);$('lessonHeading').textContent=l?.[1]||id;$('lessonBody').textContent=l?.[2]||'';
 v5ScenarioStart();
};
$('restartGuided').onclick=v5ScenarioStart;
renderLessons();

// Opening arrows use rendered square geometry so arrows align at all responsive widths.
function v5ArrowClear(){
 $('openingArrow').style.display='none';
 $('openingHintText').style.display='none';
 document.querySelectorAll('#openingBoard .hint-from,#openingBoard .hint-to').forEach(e=>e.classList.remove('hint-from','hint-to'));
}
function v5ArrowDraw(uci){
 if(!uci)return;
 const board=$('openingBoard'),src=board.querySelector(`[aria-label^="${uci.slice(0,2)} "]`),dst=board.querySelector(`[aria-label^="${uci.slice(2,4)} "]`);
 if(!src||!dst)return;
 src.classList.add('hint-from');dst.classList.add('hint-to');
 const b=board.getBoundingClientRect(),a=src.getBoundingClientRect(),z=dst.getBoundingClientRect();
 const scaleX=800/b.width,scaleY=800/b.height;
 $('openingArrowLine').setAttribute('x1',((a.left+a.right)/2-b.left)*scaleX);
 $('openingArrowLine').setAttribute('y1',((a.top+a.bottom)/2-b.top)*scaleY);
 $('openingArrowLine').setAttribute('x2',((z.left+z.right)/2-b.left)*scaleX);
 $('openingArrowLine').setAttribute('y2',((z.top+z.bottom)/2-b.top)*scaleY);
 $('openingArrow').style.display='block';
}
$('showOpeningHint').onclick=async()=>{
 if(!ready()||!openingScene)return;
 try{const h=await api('/openings/hint');v5ArrowClear();if(h.done){$('openingHintText').textContent='해당 오프닝의 기본 수순을 완료했습니다.';$('openingHintText').style.display='block';return}
  v5HintMove=h.move;v5ArrowDraw(h.move);$('openingHintText').textContent=`추천 착수: ${h.move.slice(0,2)} → ${h.move.slice(2,4)}\n이유: ${h.explanation}${h.opponent_next?'\n이후 상대의 가능한 기본 대응: '+h.opponent_next:''}`;$('openingHintText').style.whiteSpace='pre-line';$('openingHintText').style.display='block';
 }catch(e){$('openingStatus').textContent=e.message}
};
const v5StartOpening=openingStart;
openingStart=async function(){v5ArrowClear();v5HintMove=null;await v5StartOpening()};
$('openingBegin').onclick=openingStart;
const v5OpeningClick=openingClick;
openingClick=async function(square){v5ArrowClear();await v5OpeningClick(square)};

// Labels describe recorded assistance, not an inferred quality judgement.
function reviewAssistanceLabels(row){
 if(v5Review&&row.side!==(v5Review.color==='black'?'흑':'백'))return ['AI 착수'];
 const a=row.assistance;
 if(!a?.known)return ['도움 기록 없음'];
 const labels=[];
 if(a.hint_viewed)labels.push(a.hint_adopted?'힌트 채택':'힌트 제공 · 다른 수');
 if(a.undo_replayed)labels.push('무르기 후 재착수');
 if(a.hint_viewed===null||a.undo_replayed===null)labels.push('이전 도움 기록 불명');
 return labels.length?labels:['도움 제공 기록 없음'];
}
const assistanceGuide=document.createElement('p');assistanceGuide.className='lead';assistanceGuide.id='reviewAssistanceGuide';
assistanceGuide.textContent='힌트 채택: 이 위치에서 제공된 추천 수와 실제 착수가 일치합니다. 힌트 제공 · 다른 수: 추천을 제공했지만 다른 수를 뒀습니다. 무르기 후 재착수: 되돌린 위치에서 다시 둔 수입니다. 두 도움은 함께 표시합니다. 같은 대국의 같은 위치에서 앞서 받은 도움도 포함합니다. 과거 기록 없음은 도움을 안 썼다는 뜻이 아닙니다. 서버가 힌트를 제공한 기록이며 실제 화면 열람 여부는 확정하지 않습니다.';
$('reviewStatus').before(assistanceGuide);
// Completed games: selectable ply-by-ply, preserving both players' moves and evidence.
let reviewMotionContext=null;
function v5RenderReview(){
 if(!v5Review)return;
 const rows=v5Review.moves;const i=v5ReviewIndex;
 const fen=i?rows[i-1].after_fen:chessStart;
 const draw=()=>drawBoard('reviewBoard',fromFen(fen),{flip:v5Review.color==='black',last:i?[rows[i-1].uci.slice(0,2),rows[i-1].uci.slice(2,4)]:[]});
 const previous=reviewMotionContext;reviewMotionContext={game:v5Review,index:i};if(previous?.game===v5Review&&Math.abs(previous.index-i)===1)window.cmaBoardPresentation.transition('reviewBoard',rows[Math.max(i,previous.index)-1].uci,draw,i<previous.index);else draw();
 $('reviewStep').textContent=`${i} / ${rows.length} 반수`;
 document.querySelectorAll('.review-move').forEach((e,n)=>e.classList.toggle('active',n===i-1));
 const step=i?rows[i-1]:null;
 if(step){$('reviewStatus').textContent=`${step.side} ${step.san} · ${step.category} · 손실 ${step.centipawn_loss}cp\n${step.comment}\n도움: ${reviewAssistanceLabels(step).join(' · ')}\n${step.best_move?'엔진 추천 수: '+step.best_move:''}\n분석: ${step.source}`;$('reviewStatus').style.whiteSpace='pre-line'}
 else $('reviewStatus').textContent='시작 포지션입니다. 착수를 눌러 하나씩 복기하세요.';
}
let reviewListReady=false,reviewListRevision=0;
$('reviewLoad').disabled=true;
async function v5HistoryList(){
 if(!ready('review'))return;
 const revision=++reviewListRevision,identity=token;reviewListReady=false;$('reviewLoad').disabled=true;$('reviewGameSelect').replaceChildren(new Option('대국 기록 불러오는 중',''));$('reviewStatus').textContent='대국 목록을 불러오고 있습니다.';
 try{const h=await api('/games/history');if(revision!==reviewListRevision||identity!==token)return;$('reviewGameSelect').replaceChildren();
  if(!h.length){const option=document.createElement('option');option.textContent='완료된 대국이 없습니다';option.value='';$('reviewGameSelect').appendChild(option);$('reviewStatus').textContent='대국을 완료하거나 기권하면 기록이 생성됩니다.';return}
  h.forEach(g=>{const o=document.createElement('option');o.value=g.index;o.textContent=`${g.ended?.slice(0,10)||'날짜 미상'} · ${g.color==='black'?'흑':'백'} · 난이도 ${g.difficulty??'미기록'} · ${{win:'승리',loss:'패배',draw:'무승부'}[g.result]||'결과 확인 필요'} · ${g.plies}반수`;$('reviewGameSelect').appendChild(o)});reviewListReady=true;$('reviewLoad').disabled=false;$('reviewStatus').textContent='대국을 선택한 뒤 분석하세요.';
 }catch(e){if(revision!==reviewListRevision||identity!==token)return;$('reviewGameSelect').replaceChildren(new Option('목록 확인 실패',''));$('reviewStatus').textContent=e.message+' · 목록 새로고침으로 재시도하세요.';}
}
async function v5ReviewLoad(){if(!ready())return;const index=$('reviewGameSelect').value;if(!reviewListReady||!/^\d+$/.test(index)){$('reviewStatus').textContent='목록을 불러온 뒤 분석할 대국을 선택하세요.';return;}const identity=token,listRevision=reviewListRevision;
 $('reviewLoad').disabled=true;$('reviewStatus').textContent='Stockfish가 각 수를 분석 중입니다. 긴 대국은 시간이 걸릴 수 있습니다.';
 try{const result=await api('/games/review/'+index);if(identity!==token||listRevision!==reviewListRevision)return;v5Review=result;v5ReviewIndex=0;$('reviewMoves').replaceChildren();
  v5Review.moves.forEach((m,i)=>{const b=document.createElement('button');b.className='review-move';if(m.assistance?.hint_viewed)b.classList.add('hint-assisted');if(m.assistance?.undo_replayed)b.classList.add('undo-assisted');
   const name=document.createElement('b');name.textContent=`${Math.ceil((i+1)/2)}${i%2?'...':'.'} ${m.san}`;
   const meta=document.createElement('small');meta.textContent=`${m.category} · ${m.centipawn_loss}cp`;
   b.append(name,meta);const labels=document.createElement('span');labels.className='review-assistance-labels';reviewAssistanceLabels(m).forEach(text=>{const tag=document.createElement('span');tag.className='review-assistance-label';tag.textContent=text;labels.append(tag)});b.append(labels);b.onclick=()=>{v5ReviewIndex=i+1;v5RenderReview()};$('reviewMoves').appendChild(b)
  });v5RenderReview();
 }catch(e){$('reviewStatus').textContent=e.message}finally{if(identity===token&&listRevision===reviewListRevision)$('reviewLoad').disabled=!reviewListReady;}
}
$('reviewRefresh').onclick=v5HistoryList;
$('reviewLoad').onclick=v5ReviewLoad;
$('reviewPrev').onclick=()=>{if(v5Review){v5ReviewIndex=Math.max(0,v5ReviewIndex-1);v5RenderReview()}};
$('reviewNext').onclick=()=>{if(v5Review){v5ReviewIndex=Math.min(v5Review.moves.length,v5ReviewIndex+1);v5RenderReview()}};
const v5Tab=tab;
tab=function(id){v5Tab(id);if(id==='review')v5HistoryList();};
drawBoard('reviewBoard',fromFen(chessStart));

// Reset keeps account ID but removes learning and gameplay records; require current PIN.
$('resetProfileV5').onclick=async()=>{
 if(!ready())return;
 const identity=token,pin=$('resetPinV5').value,confirmation=$('resetConfirmV5').value.trim();
 if(!pin||confirmation!=='초기화'){$('resetStatusV5').textContent='현재 PIN과 확인 문구 “초기화”를 입력하세요.';return}
 if(!confirm('이 계정의 대국·퍼즐·모든 진단·훈련·노출 이력과 처음 안내를 삭제합니다. 복원할 수 없습니다. 계속할까요?')){$('resetStatusV5').textContent='초기화를 취소했습니다. 기록은 유지됩니다.';return;}
 $('resetProfileV5').disabled=true;$('resetStatusV5').textContent='계정과 저장 상태를 확인하고 있습니다…';
 try{
  const snapshot=await api('/me');if(token!==identity)return;
  $('resetStatusV5').textContent='기록 초기화를 저장 중입니다. 완료 여부를 확인할 때까지 다시 누르지 마세요.';
  const r=await api('/profile/reset','POST',{pin,confirmation,revision:snapshot.reset_revision});if(token!==identity)return;
  $('resetStatusV5').textContent=r.message;$('resetPinV5').value='';$('resetConfirmV5').value='';v5Review=null;
  // Reload clears every module's in-memory session without deleting account or preferences.
  location.reload();
 }catch(e){if(token===identity)$('resetStatusV5').textContent=e.message+' 초기화 완료는 확인되지 않았습니다. 기록을 새로 확인한 뒤 판단해 주세요.';}
 finally{$('resetProfileV5').disabled=false;}
};
