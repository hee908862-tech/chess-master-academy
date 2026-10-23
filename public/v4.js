/* v4: Interactive lessons, opening courses and visual move progression. */
let academyScene=null,academySelect=null,academyPending=false,academyFinished=false;
let openingScene=null,openingSelected=null,openingPending=false,openingList=[];

function courseMoves(scene,from){return (scene?.legal||[]).filter(uci=>uci.slice(0,2)===from).map(uci=>({to:uci.slice(2,4)}));}
function academyBoard(){
 if(!academyScene)return;window.cmaExplore?.offer('guidedBoard',academyScene.done?academyScene.fen:null);
 drawBoard('guidedBoard',academyScene.squares||fromFen(academyScene.fen),{
  selected:academySelect, targets:academySelect?courseMoves(academyScene,academySelect):[],onClick:academyClick
 });
}
function academyText(message){$('guidedPrompt').textContent=message;}
async function academyStart(){
 if(!ready())return;
 academyPending=true;academyScene=null;academySelect=null;academyFinished=false;
 $('completeLesson').disabled=true;
 $('lessonQuizBox').textContent='체스판에서 짧은 실전 수순을 직접 진행하면 교육이 완료됩니다.';
 try{
  academyScene=await api('/academy/play/start/'+encodeURIComponent(selectedLesson),'POST');
  academyText(`${academyScene.title} · ${academyScene.explanation}`);
  academyBoard();
 }catch(err){academyText(err.message)}finally{academyPending=false}
}
async function academyClick(square){
 if(!academyScene||academyPending||academyFinished)return;
 if(academySelect===square){academySelect=null;academyBoard();return;}
 const positions=academyScene.squares||fromFen(academyScene.fen);
 if(!academySelect){if(positions[square]&&positions[square]===positions[square].toUpperCase()){academySelect=square;academyBoard()}return;}
 const from=academySelect;
 if(!(academyScene.legal||[]).some(uci=>uci.slice(0,2)===from&&uci.slice(2,4)===square)){
  academySelect=positions[square]&&positions[square]===positions[square].toUpperCase()?square:null;academyBoard();return;
 }
 academySelect=null;academyPending=true;
 const previous=academyScene;
 const temp={...positions,[square]:positions[from]};delete temp[from];
 animateBoardTransition('guidedBoard',from,square,()=>drawBoard('guidedBoard',temp,{last:[from,square]}));
 document.querySelector(`#guidedBoard [aria-label^="${square} "]`)?.classList.add('moving-to');

 academyText('착수 완료 · 상대의 응수와 설명을 확인하고 있습니다...');
 try{
  const result=await api('/academy/play/move','POST',{lesson_id:selectedLesson,move:from+square});
  if(!result.correct){academyScene=previous;academyBoard();academyText(result.message);return;}
  academyScene=result;
  academyFinished=result.done;
  if(result.opponent_move)window.cmaBoardPresentation.transition('guidedBoard',result.opponent_move,academyBoard);else academyBoard();
  const aiTo=result.opponent_move?.slice(2,4);
  if(aiTo)document.querySelector(`#guidedBoard [aria-label^="${aiTo} "]`)?.classList.add('moving-to');
  const steps=Math.ceil(result.index/2);
  academyText(`실전 ${steps}회차 · ${result.player_note}${result.opponent_note?'\n상대 응수: '+result.opponent_note:''}${result.done?'\n✓ 이 과정의 플레이 실습을 완료했습니다.':''}`);
  $('guidedPrompt').style.whiteSpace='pre-line';
  if(result.done){$('lessonQuizBox').textContent='체스판에서 과정을 직접 플레이해 완료했습니다. 학습 기록이 개인 계정에 저장됐습니다.';}
 }catch(err){academyScene=previous;academyBoard();academyText(err.message)}
 finally{academyPending=false}
}
// V3 legacy quiz is not required for progress; server now awards completion after valid interactive lines.
beginGuided=academyStart;
$('restartGuided').onclick=academyStart;
const openLessonBeforeV4=openLesson;
openLesson=function(id){
  // Keep text context, but play with the real board instead of isolated one-move quizzes.
  selectedLesson=id;
  const l=lessons.find(row=>row[0]===id);
  $('lessonHeading').textContent=l?.[1]||'과정';
  $('lessonBody').textContent=l?.[2]||'';
  $('completeLesson').style.display='none';
  $('lessonQuizBox').textContent='실전 진행 과정을 통해 자동 이수됩니다.';
  academyStart();
};
renderLessons();

function openingBoard(){
 if(!openingScene)return;
 window.cmaExplore?.offer('openingBoard',openingScene.fen,{flip:openingScene.color==='black'});
 drawBoard('openingBoard',openingScene.squares||fromFen(openingScene.fen),{
   flip:openingScene.color==='black',selected:openingSelected,
   targets:openingSelected?courseMoves(openingScene,openingSelected):[],onClick:openingClick
 });
}
function openingText(message){$('openingExplanation').textContent=message;$('openingExplanation').style.whiteSpace='pre-line';}
async function openingCatalog(){
 try{
  openingList=await api('/openings');
  $('openingSelect').replaceChildren();
  openingList.forEach(item=>{
   const option=document.createElement('option');option.value=item.id;option.textContent=item.name;
   $('openingSelect').appendChild(option);
  });
 }catch(err){$('openingStatus').textContent=err.message}
}
async function openingStart(){
 if(!ready())return;
 openingPending=true;openingSelected=null;
 try{
  const id=$('openingSelect').value;
  openingScene=await api('/openings/start','POST',{line_id:id});
  $('openingTitle').textContent=openingScene.title;
  openingText(openingScene.explanation);
  $('openingProgress').textContent='기본 수순 '+openingScene.index+'/'+openingScene.total;
  $('openingStatus').textContent='해당 색의 기물을 골라 다음 수를 직접 두세요.';
  openingBoard();
 }catch(err){$('openingStatus').textContent=err.message}
 finally{openingPending=false}
}
async function openingClick(square){
 if(!openingScene||openingScene.done||openingPending)return;
 if(openingSelected===square){openingSelected=null;openingBoard();return;}
 const pos=openingScene.squares||fromFen(openingScene.fen);
 const currentColor=openingScene.color==='white';
 const myPiece=p=>!!p&&(p===p.toUpperCase())===currentColor;
 if(!openingSelected){if(myPiece(pos[square])){openingSelected=square;openingBoard()}return;}
 if(!(openingScene.legal||[]).some(uci=>uci.slice(0,2)===openingSelected&&uci.slice(2,4)===square)){
  openingSelected=myPiece(pos[square])?square:null;openingBoard();return;
 }
 const from=openingSelected;openingSelected=null;openingPending=true;
 const before=openingScene;
 const temp={...pos,[square]:pos[from]};delete temp[from];
 animateBoardTransition('openingBoard',from,square,()=>drawBoard('openingBoard',temp,{flip:openingScene.color==='black',last:[from,square]}));
 document.querySelector(`#openingBoard [aria-label^="${square} "]`)?.classList.add('moving-to');

 try{
  const r=await api('/openings/move','POST',{line_id:$('openingSelect').value,move:from+square});
  if(!r.correct){openingScene=before;openingBoard();$('openingStatus').textContent=r.message;return;}
  openingScene=r;if(r.opponent_move)window.cmaBoardPresentation.transition('openingBoard',r.opponent_move,openingBoard);else openingBoard();
  if(r.opponent_move){document.querySelector(`#openingBoard [aria-label^="${r.opponent_move.slice(2,4)} "]`)?.classList.add('moving-to');}
  openingText(`${r.player_note}${r.opponent_note?'\n상대 응수: '+r.opponent_note:''}`);
  $('openingProgress').textContent='기본 수순 '+r.index+'/'+r.total;
  $('openingStatus').textContent=r.done?'✓ 오프닝 실습 완료 · 다른 변화를 선택해서 이어서 학습할 수 있습니다.':'다음 내 수를 두세요. 체스판의 이동 가능 표시를 확인할 수 있습니다.';
 }catch(err){openingScene=before;openingBoard();$('openingStatus').textContent=err.message}
 finally{openingPending=false}
}
$('openingBegin').onclick=openingStart;
const oldTabV4=tab;
tab=function(id){oldTabV4(id);if(id==='opening'&&token&&!openingList.length)openingCatalog();};
if(token)openingCatalog();
drawBoard('openingBoard',fromFen(chessStart));
