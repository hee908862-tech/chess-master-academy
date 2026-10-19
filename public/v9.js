/* V9: Lichess CC0 themes + levelled 15-problem academy. No unverified generated puzzles. */
(()=>{'use strict';
const el=id=>document.getElementById(id), modes={puzzle:{task:null,selected:null,busy:false,solved:false,last:[],mistakes:0},course:{task:null,selected:null,busy:false,solved:false,last:[],mistakes:0}};
let catalog=null,courseTheme=null;
function status(kind,msg){el('v9'+(kind==='course'?'Course':'Puzzle')+'Message').textContent=msg}
function boardName(kind){return 'v9'+(kind==='course'?'Course':'Puzzle')+'Board'}
function props(kind){return kind==='course'?'Course':'Puzzle'}
function paint(kind){const st=modes[kind];if(!st.task)return;
 const data=st.task, fen=data.fen, p=fromFen(fen), turn=fen.split(' ')[1]==='w';
 const targets=st.selected?(data.legal||[]).filter(u=>u.slice(0,2)===st.selected).map(u=>({to:u.slice(2,4)})):[];
 drawBoard(boardName(kind),p,{flip:!turn,selected:st.selected,targets,last:st.last,onClick:sq=>tap(kind,sq)});
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
async function tap(kind,sq){const st=modes[kind];if(st.busy||st.solved||!st.task)return;
 const task=st.task,p=fromFen(task.fen),white=task.fen.split(' ')[1]==='w';
 if(st.selected===sq){st.selected=null;paint(kind);return;}
 const friendly=s=>p[s]&&(white?p[s]===p[s].toUpperCase():p[s]===p[s].toLowerCase());
 if(!st.selected){if(friendly(sq)){st.selected=sq;paint(kind)}return;}
 const u=(task.legal||[]).find(m=>m.slice(0,2)===st.selected&&m.slice(2,4)===sq);
 if(!u){st.selected=friendly(sq)?sq:null;paint(kind);return;}
 const from=st.selected;
 const promotion=await choosePromotion(from,sq,p[from],task.legal||[]);
 const selectedMove=promotion?from+sq+promotion:u;
 st.busy=true;st.selected=null;
 const priorLast=st.last;
 const temporary=optimisticPosition(task.fen,from,sq,promotion);
 animateBoardTransition(boardName(kind),from,sq,()=>drawBoard(boardName(kind),temporary,{flip:!white,last:[from,sq]}));
 playMoveSound(p[sq]?'capture':'move');
 try{const r=await api(`/v9/${kind}/move`,'POST',{move:selectedMove});
  if(!r.correct){st.last=priorLast;st.mistakes++;status(kind,`${r.message} (${st.mistakes}회 오답)${st.mistakes>=2?' · 정답 확인 버튼으로 수순을 확인할 수 있습니다.':''}`);st.task=r;paint(kind);return;}
  st.mistakes=0;st.last=r.reply?[r.reply.slice(0,2),r.reply.slice(2,4)]:[from,sq];
  if(r.solved){st.solved=true;status(kind,r.done?`${r.message} · 첫 시도 정답 ${r.correct_count}/15 ${r.mastered?'· 숙련 달성':''}`:r.message);
   el('v9'+props(kind)+'Next').hidden=false;
   if(r.completed_fen)drawBoard(boardName(kind),fromFen(r.completed_fen),{flip:task.fen.split(' ')[1]==='b',last:st.last});
   if(kind==='course'&&r.done)await history();
  }else{st.task=r;status(kind,r.reply?`정답: ${selectedMove} · 상대 응수: ${r.reply}. 마지막 이동 칸을 강조했습니다. 다음 수를 찾아보세요.`:r.message);paint(kind);}
 }catch(e){st.last=priorLast;status(kind,e.message);paint(kind)}finally{st.busy=false;}
}
async function start(kind){if(!token){tab('profile');return;}const st=modes[kind];if(st.busy)return;
 st.busy=true;try{
  const theme=kind==='course'?courseTheme:el('v9PuzzleTheme').value;
  const level=el('v9'+props(kind)+'Level').value;
  const task=await api(`/v9/${kind}/start`,'POST',{theme,level});
  st.task=task;st.solved=false;st.selected=null;st.last=[];st.mistakes=0;el('v9'+props(kind)+'Next').hidden=true;
  status(kind,`새 ${task.themes.join(' · ')} 문제입니다. ${task.side==='white'?'백':'흑'}의 최선 수를 찾아보세요.`);paint(kind);
 }catch(e){status(kind,e.message)}finally{st.busy=false}
}
async function next(kind){const st=modes[kind];if(!st.solved)return;
 if(kind==='puzzle')return start('puzzle');
 try{const r=await api('/v9/course/next','POST');if(r.done){status(kind,`15문제 과정 완료 · 첫 시도 정답 ${r.correct_count}/15`);return;}
 st.task=r;st.solved=false;st.selected=null;st.last=[];st.mistakes=0;el('v9CourseNext').hidden=true;
 status(kind,'다음 상황입니다. 상대의 위협과 후속 수순까지 계산해 보세요.');paint(kind);
 }catch(e){status(kind,e.message)}
}
async function history(){if(!token)return;try{const d=await api('/v9/progress');
 const a=d.courses||[];el('v9CourseHistory').textContent=a.length?'최근 과정: '+a.slice(-8).reverse().map(r=>`${catalog?.themes.find(t=>t.id===r.theme)?.name||r.theme} ${r.level} · 15문제 해결 · 첫 시도 ${r.first_try}/15 ${r.mastered?'✓ 숙련':'복습 권장'}`).join(' | '):'완료한 새 교육 과정이 아직 없습니다.';
 }catch(e){el('v9CourseHistory').textContent=e.message}}
async function hint(kind){const st=modes[kind];if(!st.task||st.busy||st.solved)return;try{const r=await api(`/v9/${kind}/hint`);st.last=[r.from,r.to];status(kind,`추천 이동: ${r.move_label} · ${r.explanation}`);paint(kind)}catch(e){status(kind,e.message)}}
function selectCourse(theme){courseTheme=theme;el('v9LearnMode').hidden=false;
 const m=catalog?.themes.find(x=>x.id===theme);
 el('v9CourseTitle').textContent=(m?.name||theme)+' · 난이도 선택';
 el('v9CourseMessage').textContent='난이도에 따라 다른 실제 대국 퍼즐을 15개 무작위로 출제합니다. 같은 포지션은 한 세션에 중복되지 않습니다.';
 el('v9CourseLevel').innerHTML='';for(const level of catalog.levels){const op=new Option(`${level} (${m?.counts[level]||0}개)`,level);op.disabled=(m?.counts[level]||0)<15;el('v9CourseLevel').add(op)}
 if([...el('v9CourseLevel').options].some(o=>!o.disabled))el('v9CourseLevel').value=[...el('v9CourseLevel').options].find(o=>!o.disabled).value;
 el('v9LearnMode').scrollIntoView({block:'nearest',behavior:'smooth'});
}
async function init(){try{
 catalog=await api('/v9/catalog');el('v9DataCount').textContent=catalog.ready?`공개 검증 퍼즐 ${catalog.count.toLocaleString()}개`:'공개 문제 데이터 설치 필요';
 const select=el('v9PuzzleTheme');select.replaceChildren();select.add(new Option('모든 주제 · 랜덤','random'));
 const card=el('v9CourseCards');card.replaceChildren();
 for(const t of catalog.themes){const total=Object.values(t.counts).reduce((a,b)=>a+b,0);
  select.add(new Option(`${t.name} (${total})`,t.id));
  const btn=document.createElement('button');btn.className='v9-course-card';
  const title=document.createElement('strong');title.textContent=t.name;const small=document.createElement('small');small.textContent=`입문 ${t.counts['입문']} · 중급 ${t.counts['중급']} · 고급 ${t.counts['고급']}`;
  btn.append(title,small);btn.onclick=()=>selectCourse(t.id);card.append(btn);
 }
 if(!catalog.ready){const warning='공개 퍼즐 원본은 별도로 내려받아야 합니다. 배포 파일에 데이터가 없어 현재 15문제 과정과 공개 랜덤 퍼즐을 시작할 수 없습니다. README의 데이터 가져오기 안내를 확인하세요.';
 status('puzzle',warning);el('v9CourseHistory').textContent=warning;}
 else {status('puzzle','테마와 난이도를 고른 뒤 랜덤 문제를 출제하세요.');await history();}
 }catch(e){status('puzzle','데이터 확인 실패: '+e.message);el('v9CourseHistory').textContent=e.message}}
// Hide legacy inaccurate exercises. New mode remains visible even when corpus is missing.
document.body.classList.add('v9-active');
const css=document.createElement('style');css.textContent='#puzzle > .row,#puzzle > .two,#puzzle > .card:not(#v9PuzzleRoot),#learn > .two,#learn > div:first-child:not(#v9LearnRoot){display:none!important}';document.head.append(css);
el('v9PuzzleHint').onclick=()=>hint('puzzle');el('v9CourseHint').onclick=()=>hint('course');
el('v9PuzzleStart').onclick=()=>start('puzzle');el('v9PuzzleNext').onclick=()=>next('puzzle');
el('v9CourseStart').onclick=()=>start('course');el('v9CourseNext').onclick=()=>next('course');
el('v9CourseBack').onclick=()=>{el('v9LearnMode').hidden=true;courseTheme=null};
init();
})();
