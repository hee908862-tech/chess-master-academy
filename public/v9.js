/* V9: Lichess CC0 themes + levelled 15-problem academy. No unverified generated puzzles. */
(()=>{'use strict';
const el=id=>document.getElementById(id), modes={puzzle:{task:null,selected:null,busy:false,solved:false,last:[],mistakes:0,revision:0},course:{task:null,selected:null,busy:false,solved:false,last:[],mistakes:0,revision:0}};
let catalog=null,courseTheme=null,courseSaved=null,courseRead=0;
const savedBox=document.createElement("div");savedBox.id="v9SavedCourse";savedBox.className="notice";el("v9CourseCards").before(savedBox);
function invalidate(kind,message){window.cmaMate?.clear(boardName(kind));window.cmaBoardTools.cancel(boardName(kind));const st=modes[kind];st.revision++;st.task=null;st.selected=null;st.solved=false;st.last=[];st.busy=false;el(boardName(kind)).replaceChildren();el('v9'+props(kind)+'Next').hidden=true;el('v9'+props(kind)+'Hint').disabled=true;el('v9'+props(kind)+'Meta').textContent='새 문제 대기 중';if(message)status(kind,message);window.cmaFeedback.clear(boardName(kind));}
async function failed(kind,error){
 const st=modes[kind],revision=st.revision,identity=token,session=st.task?.session_id;
 window.cmaBoardTools.cancel(boardName(kind));st.selected=null;
 try{
  const saved=await api('/v9/session/'+kind);
  if(revision!==st.revision||identity!==token)return;
  if(!session||saved.session_id!==session){invalidate(kind,error.message+' · 새 문제를 시작해 주세요.');return;}
  if(saved.result){window.cmaMate?.show(boardName(kind),saved.result.mate_explanation,st.side==='black');st.solved=true;el('v9'+props(kind)+'Next').hidden=false;el('v9'+props(kind)+'Hint').disabled=true;
   drawBoard(boardName(kind),fromFen(saved.result.completed_fen),{flip:st.side==='black'});status(kind,saved.result.message+' · 저장된 결과를 확인했습니다.');boardFeedback(kind,'문제 완료 · 저장 결과 복원','저장 조회 확인됨','complete');
  }else if(saved.fen){st.task=saved;st.solved=false;el('v9'+props(kind)+'Hint').disabled=false;el('v9'+props(kind)+'Next').hidden=true;paint(kind);status(kind,error.message+' · 저장된 위치를 복원했습니다.');boardFeedback(kind,'저장된 위치에서 다시 확인','저장 조회 확인됨','error');}
  else invalidate(kind,error.message+' · 새 문제를 시작해 주세요.');
 }catch(recovery){
  if(revision!==st.revision||identity!==token)return;
  st.solved=true;el('v9'+props(kind)+'Hint').disabled=true;
  if(st.task)drawBoard(boardName(kind),fromFen(st.task.fen),{flip:st.side==='black'});
  boardFeedback(kind,'판정 미확인 · 상태를 다시 확인하세요','저장 여부 미확인','error');status(kind,'저장 상태를 확인하지 못했습니다. 마지막 확인 위치를 표시합니다. 착수를 재전송하지 않고 상태를 다시 확인해 주세요.');
  const retry=document.createElement('button');retry.className='btn';retry.textContent='저장 상태 다시 확인';
  retry.onclick=async()=>{if(st.busy)return;st.busy=true;retry.disabled=true;try{await failed(kind,error)}finally{st.busy=false}};
  el('v9'+props(kind)+'Message').append(retry);
 }
}
function boardFeedback(kind,title,save='저장 응답 확인됨',type='ready'){window.cmaFeedback.set(boardName(kind),{title,save,kind:type,facts:null,detail:el('v9'+props(kind)+'Message').textContent});}
function status(kind,msg){el('v9'+(kind==='course'?'Course':'Puzzle')+'Message').textContent=msg}
function boardName(kind){return 'v9'+(kind==='course'?'Course':'Puzzle')+'Board'}
function props(kind){return kind==='course'?'Course':'Puzzle'}
function paint(kind){const st=modes[kind];if(!st.task)return;
 const data=st.task, fen=data.fen, p=fromFen(fen), turn=st.side==='white';
 const targets=st.selected?(data.legal||[]).filter(u=>u.slice(0,2)===st.selected).map(u=>({to:u.slice(2,4)})):[];
 drawBoard(boardName(kind),p,{flip:!turn,opponent:data.opponent_last_move?[data.opponent_last_move.slice(0,2),data.opponent_last_move.slice(2,4)]:[],hint:st.hint||[],selected:st.selected,targets,last:st.last,onClick:sq=>tap(kind,sq)});
 el('v9'+props(kind)+'Meta').textContent=`${kind==='course'?`${data.index+1}/${data.total} · `:''}${data.rating} 퍼즐 레이팅 · ${data.themes.join(' / ')} · ${data.ply}번째 반수`;
}
function optimisticPosition(fen,from,to,promotion){
 const pos=fromFen(fen), piece=pos[from];if(!piece)return pos;
 const out={...pos};out[to]=piece;delete out[from];
 if(piece.toLowerCase()==='p'){
  if(from[0]!==to[0]&&!pos[to])delete out[to[0]+from[1]];
  if(to[1]==='1'||to[1]==='8')out[to]=piece===piece.toUpperCase()?(promotion||'q').toUpperCase():(promotion||'q');
 }
 if(piece.toLowerCase()==='k'&&Math.abs(FILES.indexOf(from[0])-FILES.indexOf(to[0]))===2){
  const rank=from[1],k=to[0]==='g';out[(k?'f':'d')+rank]=out[(k?'h':'a')+rank];delete out[(k?'h':'a')+rank];
 }
 return out;
}
async function tap(kind,sq){const st=modes[kind];if(st.busy){window.cmaBoardTools.pick(boardName(kind),sq);return;}if(st.busy||st.solved||!st.task)return;
 const task=st.task,p=fromFen(task.fen),white=task.fen.split(' ')[1]==='w';
 if(st.selected===sq){st.selected=null;paint(kind);return;}
 const friendly=s=>p[s]&&(white?p[s]===p[s].toUpperCase():p[s]===p[s].toLowerCase());
 if(!st.selected){if(friendly(sq)){st.selected=sq;paint(kind)}return;}
 const u=(task.legal||[]).find(m=>m.slice(0,2)===st.selected&&m.slice(2,4)===sq);
 if(!u){st.selected=friendly(sq)?sq:null;paint(kind);return;}
 const from=st.selected;
 const revision=st.revision,accountToken=token,viewVersion=window.cmaBoardTools.version();st.busy=true;
 const promotion=await choosePromotion(from,sq,p[from],task.legal||[]);
 if(revision!==st.revision)return;
 if(promotion===null||accountToken!==token||viewVersion!==window.cmaBoardTools.version()){st.busy=false;return;}
 const selectedMove=promotion?from+sq+promotion:u;
 st.busy=true;st.selected=null;st.hint=null;boardFeedback(kind,'착수 판정 중','판정·저장 응답 대기','pending');
 const priorLast=st.last;
 const temporary=optimisticPosition(task.fen,from,sq,promotion);
 if(task.session_id)window.cmaBoardTools.begin(boardName(kind),task,temporary,st.side);else window.cmaBoardTools.unavailable(boardName(kind));
 animateBoardTransition(boardName(kind),from,sq,()=>drawBoard(boardName(kind),temporary,{flip:st.side==='black',last:[from,sq],onClick:s=>tap(kind,s)}));
 playMoveSound(p[sq]?'capture':'move');
 try{const r=await api(`/v9/${kind}/move`,'POST',{move:selectedMove,session_id:task.session_id,expected_fen:task.fen});if(revision!==st.revision||accountToken!==token)return;
  if(!r.correct){window.cmaBoardTools.cancel(boardName(kind));}
  if(!r.correct){st.last=priorLast;st.mistakes++;status(kind,`${r.message} (${st.mistakes}회 오답)${st.mistakes>=2?' · 정답 확인 버튼으로 수순을 확인할 수 있습니다.':''}`);st.task=r;paint(kind);boardFeedback(kind,'이번 수는 기준과 다름','저장 응답 확인됨','error');return;}
  st.mistakes=0;st.last=[from,sq];
  if(r.solved){window.cmaMate?.show(boardName(kind),r.mate_explanation,st.side==='black');window.cmaBoardTools.cancel(boardName(kind));st.solved=true;status(kind,r.done?(kind==='puzzle'?r.message:`${r.message} · 첫 시도 정답 ${r.correct_count}/${r.total} ${r.mastered?'· 숙련 달성':''}`):r.message);
   el('v9'+props(kind)+'Next').hidden=false;boardFeedback(kind,r.done&&kind==='course'?'과정 완료 · 문제 수순 확인':'문제 완료 · 수순 확인','저장 응답 확인됨','complete');
   if(r.completed_fen){const draw=()=>drawBoard(boardName(kind),fromFen(r.completed_fen),{flip:st.side==='black',last:st.last});if(r.reply)window.cmaBoardPresentation.transition(boardName(kind),r.reply,draw);else draw();}
   await refreshSummaryOnly();if(kind==='course'&&r.done)await history();
  }else{st.task=r;status(kind,r.reply?`정답: ${selectedMove} · 상대 응수: ${r.reply}. 마지막 이동 칸을 강조했습니다. 다음 수를 찾아보세요.`:r.message);if(r.reply)window.cmaBoardPresentation.transition(boardName(kind),r.reply,()=>paint(kind));else paint(kind);boardFeedback(kind,'한 수 정답 · 계속 풀어보세요');}
 }catch(e){if(revision===st.revision&&accountToken===token)await failed(kind,e)}finally{if(revision===st.revision)st.busy=false;}
 const queued=window.cmaBoardTools.take(boardName(kind),task,st.task?.legal,revision===st.revision&&accountToken===token&&!el(boardName(kind)).closest('[hidden],[inert]')&&el(boardName(kind)).closest('.view.active')&&!st.solved&&st.task?.session_id===task.session_id&&st.task?.id===task.id&&st.task?.fen.split(' ')[1]===(st.side==='white'?'w':'b'));
 if(queued){st.selected=queued.from;await tap(kind,queued.to);}
}
async function start(kind){if(!ready(kind==='course'?(window.cmaNavigation?.tacticDestination()||'learn'):'puzzle'))return;const st=modes[kind];if(st.busy)return;
 let replacement=null;
 if(kind==='course'){const identity=token,rev=st.revision;st.busy=true;try{const saved=await api('/v9/session/course');if(identity!==token||rev!==st.revision)return;if(saved.active&&!saved.done){if(!confirm('저장된 과정의 착수·힌트·진행을 보존하고 새 과정을 시작할까요? 저장된 과정 목록에서 다시 이어갈 수 있습니다.'))return;replacement=saved.replace_token;}}catch(e){if(identity===token)status(kind,e.message);return;}finally{if(identity===token&&rev===st.revision)st.busy=false;}}
 invalidate(kind);const revision=st.revision,identity=token;st.busy=true;try{
  const theme=kind==='course'?courseTheme:el('v9PuzzleTheme').value;
  const level=el('v9'+props(kind)+'Level').value;
  const task=await api(`/v9/${kind}/start`,'POST',{theme,level,...(kind==='course'?{replace_token:replacement}:{})});if(revision!==st.revision||identity!==token)return;
  st.task=task;st.side=task.side||(task.fen.split(' ')[1]==='w'?'white':'black');st.hint=null;el('v9'+props(kind)+'Hint').disabled=false;st.solved=false;st.selected=null;st.last=[];st.mistakes=0;el('v9'+props(kind)+'Next').hidden=true;
  if(kind==='course')loadSavedCourse();
  status(kind,`새 ${task.themes.join(' · ')} 문제입니다. ${task.side==='white'?'백':'흑'}의 최선 수를 찾아보세요. ${task.opponent_last_move?'상대 직전 수: '+task.opponent_last_move+' (청록 표시)':'직전 수 기록이 없어 표시할 수 없습니다.'}`);paint(kind);boardFeedback(kind,(st.side==='white'?'백':'흑')+' 차례 · 직접 풀어보세요');
 }catch(e){if(revision===st.revision&&identity===token)await failed(kind,e)}finally{if(revision===st.revision)st.busy=false}
}
async function next(kind){const st=modes[kind];if(!st.solved||st.busy)return;
 if(kind==='puzzle')return start('puzzle');
 const revision=st.revision,identity=token;st.busy=true;try{const r=await api('/v9/course/next','POST',{session_id:st.task?.session_id});if(revision!==st.revision||identity!==token)return;if(r.done){status(kind,`15문제 과정 완료 · 첫 시도 정답 ${r.correct_count}/15`);return;}
 window.cmaMate?.clear(boardName(kind));window.cmaBoardTools.cancel(boardName(kind));st.task=r;st.side=r.side||(r.fen.split(' ')[1]==='w'?'white':'black');st.hint=null;st.solved=false;st.selected=null;st.last=[];st.mistakes=0;el('v9CourseNext').hidden=true;
 status(kind,'다음 상황입니다. 상대의 위협과 후속 수순까지 계산해 보세요.');paint(kind);
 }catch(e){if(revision===st.revision&&identity===token)await failed(kind,e)}finally{if(revision===st.revision)st.busy=false}
}
async function restore(kind,force=false,choice=null){const navigationVersion=window.cmaNavigation?.version();const st=modes[kind];if(!token||(!force&&st.task)||st.busy)return;const revision=st.revision,identity=token;
 try{const r=await api('/v9/session/'+kind);if(revision!==st.revision||identity!==token||st.busy||!r.active)return;
  if(kind==='course'){if(navigationVersion!==window.cmaNavigation?.version()||(choice&&(r.theme!==choice.theme||r.level!==choice.level)))return;selectCourse(r.theme,{navigate:!choice,level:r.level});courseSaved=r;}
  if(r.result){st.task={session_id:r.session_id,fen:r.result.completed_fen,theme:r.theme,level:r.level};st.side=r.result.completed_fen.split(' ')[1]==='w'?'black':'white';st.solved=true;
   drawBoard(boardName(kind),fromFen(st.task.fen),{flip:st.side==='black'});status(kind,r.result.message);if(kind==='course')el('v9CourseMeta').textContent=`${r.index}/${r.total} 해결 · ${r.done?'과정 완료':'다음 문제 대기'}`;el('v9'+props(kind)+'Next').hidden=false;el('v9'+props(kind)+'Hint').disabled=true;
   window.cmaMate?.show(boardName(kind),r.result.mate_explanation,st.side==='black');boardFeedback(kind,'문제 완료 · 저장 결과 복원','저장 조회 확인됨','complete');
  }else if(r.fen){st.task=r;st.side=r.side;st.solved=false;el('v9'+props(kind)+'Hint').disabled=false;paint(kind);status(kind,'진행 중인 문제를 복원했습니다.');boardFeedback(kind,(st.side==='black'?'흑':'백')+' 차례 · 저장된 문제 이어하기','저장 조회 확인됨');}
 }catch(e){if(revision===st.revision&&identity===token)status(kind,'저장된 문제 확인 실패: '+e.message);}
}
let modeOwner=token;const previousTab=tab;tab=function(id){if(modeOwner!==token){modeOwner=token;courseRead++;courseSaved=null;courseTheme=null;invalidate('course');invalidate('puzzle');savedBox.replaceChildren();}previousTab(id);if(id==='puzzle')restore('puzzle');if(id==='learn')loadSavedCourse();};
async function loadSavedCourse(){const identity=token,rev=++courseRead;if(!identity){savedBox.textContent='로그인하면 저장된 과정을 이어갈 수 있습니다.';return;}savedBox.textContent='저장된 과정 확인 중…';try{const d=await api('/v9/session/course');if(identity!==token||rev!==courseRead)return;courseSaved=d;savedBox.replaceChildren();const add=(text,fn)=>{const b=document.createElement('button');b.className='btn';b.textContent=text;b.onclick=fn;savedBox.append(b);};if(d.active&&!d.done)add(`진행 중인 과정 이어하기 · ${catalog?.themes.find(t=>t.id===d.theme)?.name||d.theme} 현재 ${Math.min(d.index+1,d.total)}/${d.total} 문항`,()=>restore('course',true));else savedBox.append(document.createTextNode('진행 중인 과정 없음 · 아래에서 과목을 선택하세요.'));for(const item of d.paused||[])add(`보존한 과정 · ${catalog?.themes.find(t=>t.id===item.theme)?.name||item.theme} 현재 ${Math.min(item.index+1,item.total)}/${item.total} 문항 이어하기`,async()=>{const st=modes.course;if(st.busy)return;st.busy=true;const auth=token,version=st.revision;try{await api('/v9/course/resume/'+item.session_id,'POST',{theme:item.theme,level:item.level,replace_token:d.replace_token});if(auth!==token||version!==st.revision)return;st.busy=false;invalidate('course');await restore('course',true);await loadSavedCourse();}catch(e){if(auth===token)savedBox.textContent=e.message;}finally{if(auth===token&&version===st.revision)st.busy=false;}});}catch(e){if(identity===token&&rev===courseRead){savedBox.textContent='저장 과정 확인 실패: '+e.message;const retry=document.createElement('button');retry.className='btn';retry.textContent='저장 과정 다시 확인';retry.onclick=loadSavedCourse;savedBox.append(retry);}}}
async function history(){const identity=token;if(!identity)return;try{const d=await api('/v9/progress');if(identity!==token)return;
 const a=d.courses||[];el('v9CourseHistory').textContent=a.length?'최근 과정: '+a.slice(-8).reverse().map(r=>`${catalog?.themes.find(t=>t.id===r.theme)?.name||r.theme} ${r.level} · 15문제 해결 · 첫 시도 ${r.first_try}/15 ${r.mastered?'✓ 숙련':'복습 권장'}`).join(' | '):'완료한 새 교육 과정이 아직 없습니다.';
 }catch(e){if(identity===token)el('v9CourseHistory').textContent=e.message}}
async function hint(kind){const st=modes[kind];if(!st.task||st.busy||st.solved)return;const revision=st.revision,identity=token;st.busy=true;try{const r=await api(`/v9/${kind}/hint?`+new URLSearchParams({session_id:st.task.session_id,expected_fen:st.task.fen}));if(revision!==st.revision||identity!==token)return;st.hint=[r.from,r.to];status(kind,`추천 이동: ${r.move_label} · ${r.explanation}`);paint(kind)}catch(e){if(revision===st.revision&&identity===token)await failed(kind,e)}finally{if(revision===st.revision)st.busy=false}}

function selectCourse(theme,{navigate=true,level=null}={}){if(courseTheme===theme&&modes.course.task&&(!level||modes.course.task.level===level)&&window.cmaNavigation){if(navigate)window.cmaNavigation.tacticSelected();if(level)el('v9CourseLevel').value=level;return;}invalidate('course');courseTheme=theme;el('v9LearnMode').hidden=false;const st=modes.course;st.task=null;st.selected=null;st.solved=false;st.last=[];st.mistakes=0;el('v9CourseBoard').replaceChildren();el('v9CourseMeta').textContent='새 과목 대기 중';el('v9CourseNext').hidden=true;el('v9CourseHint').disabled=true;
 const m=catalog?.themes.find(x=>x.id===theme);
 el('v9CourseTitle').textContent=(m?.name||theme)+' · 난이도 선택';
 const concept=window.cmaAcademyConcept(theme);el('v9CourseMessage').textContent='학습 목표: '+concept.goal+' '+concept.example+' 이 설명은 개념 예시이며 현재 문제의 정답 해설이 아닙니다. 15문제에서 직접 확인해 보세요.';
 el('v9CourseLevel').innerHTML='';for(const level of catalog.levels){const op=new Option(`${level} (${m?.counts[level]||0}개)`,level);op.disabled=(m?.counts[level]||0)<15;el('v9CourseLevel').add(op)}
 const available=[...el('v9CourseLevel').options].filter(o=>!o.disabled);el('v9CourseStart').disabled=!available.length;if(available.length)el('v9CourseLevel').value=available[0].value;else el('v9CourseMessage').textContent='이 과목은 준비된 문제가 부족하여 시작할 수 없습니다.';
 if(level)el('v9CourseLevel').value=level;if(navigate&&window.cmaNavigation)window.cmaNavigation.tacticSelected();else if(navigate)el('v9LearnMode').scrollIntoView({block:'nearest',behavior:'smooth'});
}
async function init(){try{
 catalog=await api('/v9/catalog');el('v9DataCount').textContent=catalog.ready?`공개 검증 퍼즐 ${catalog.count.toLocaleString()}개`:'공개 문제 데이터 설치 필요';
 const select=el('v9PuzzleTheme');select.replaceChildren();select.add(new Option('모든 주제 · 랜덤','random'));
 const card=el('v9CourseCards');card.replaceChildren();
 for(const t of catalog.themes){const total=Object.values(t.counts).reduce((a,b)=>a+b,0);
  const option=new Option(`${t.name} (${total})`,t.id);option.disabled=total===0;select.add(option);
  const btn=document.createElement('button');btn.className='v9-course-card';btn.disabled=total===0;
  const title=document.createElement('strong');title.textContent=t.name;const goal=document.createElement('p');goal.textContent=window.cmaAcademyConcept(t.id).goal;const small=document.createElement('small');small.textContent=`전술 문제 수 · 낮은 난도(기존 입문) ${t.counts['입문']} · 중급 ${t.counts['중급']} · 고급 ${t.counts['고급']}`;
  btn.id='tactic-'+t.id;btn.append(title,goal,small);btn.onclick=()=>selectCourse(t.id);card.append(btn);
 }
 if(!catalog.ready){const warning='공개 퍼즐 원본은 별도로 내려받아야 합니다. 배포 파일에 데이터가 없어 현재 15문제 과정과 공개 랜덤 퍼즐을 시작할 수 없습니다. README의 데이터 가져오기 안내를 확인하세요.';
 status('puzzle',warning);el('v9CourseHistory').textContent=warning;}
 else {status('puzzle','테마와 난이도를 고른 뒤 랜덤 문제를 출제하세요.');await history();await loadSavedCourse();}
 }catch(e){status('puzzle','데이터 확인 실패: '+e.message);el('v9CourseHistory').textContent=e.message}}
// Hide legacy inaccurate exercises. New mode remains visible even when corpus is missing.
document.body.classList.add('v9-active');
const css=document.createElement('style');css.textContent='#puzzle > .row,#puzzle > .two,#puzzle > .card:not(#v9PuzzleRoot),#learn > .two,#learn > div:first-child:not(#v9LearnRoot){display:none!important}';document.head.append(css);
el('v9PuzzleHint').onclick=()=>hint('puzzle');el('v9CourseHint').onclick=()=>hint('course');
el('v9PuzzleStart').onclick=()=>start('puzzle');el('v9PuzzleNext').onclick=()=>next('puzzle');
el('v9CourseStart').textContent='새 15문제 과정 시작';
el('v9CourseStart').onclick=()=>start('course');el('v9CourseNext').onclick=()=>next('course');
el('v9CourseBack').onclick=()=>{if(window.cmaNavigation){window.cmaNavigation.go('learn/tactics');return;}invalidate('course');el('v9LearnMode').hidden=true;courseTheme=null};
el('v9CourseLevel').addEventListener('change',()=>{if(window.cmaNavigation?.current()==='learn/tactics/practice')window.cmaNavigation.go('learn/tactics/practice',{replace:true,load:false,focus:false});});
window.cmaTacticView={choice:()=>courseTheme?{theme:courseTheme,level:el('v9CourseLevel').value}:null,async restoreChoice(choice,version){const account=token;await catalogReady;if(account!==token||version!==window.cmaNavigation.version())return false;if(!catalog?.themes.some(t=>t.id===choice.theme)||!catalog.levels.includes(choice.level))return false;selectCourse(choice.theme,{navigate:false,level:choice.level});window.cmaNavigation.go('learn/tactics/practice',{replace:true,load:false,focus:false});await restore('course',false,choice);return true;},hasSelection:()=>!!courseTheme,refreshSaved:()=>loadSavedCourse(),loadSaved:async()=>{const account=token,version=window.cmaNavigation?.version();await catalogReady;if(account!==token||version!==window.cmaNavigation?.version())return;await restore('course');}};
const catalogReady=init();
window.cmaOpenV9Course=async(theme)=>{await catalogReady;if(!catalog)return false;const m=catalog.themes.find(t=>t.id===theme);if(!m)return false;selectCourse(theme);return true};
})();
