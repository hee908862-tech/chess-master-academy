/* Authored same-piece movement sandbox. Deliberately separate from game legality and scores. */
(()=>{'use strict';
const $=id=>document.getElementById(id),files='abcdefgh';
const stages={rook:'룩',bishop:'비숍',queen:'퀸',king:'킹',knight:'나이트',pawn:'폰',capture:'잡기',protection:'보호',combat:'잡기와 안전',check1:'체크',outOfCheck:'체크에서 벗어나기',checkmate1:'체크메이트',setup:'처음 배치',castling:'캐슬링',enpassant:'앙파상',stalemate:'스테일메이트',value:'말의 가치',check2:'두 수 연결'};
const point=s=>[files.indexOf(s[0]),Number(s[1])-1],square=(x,y)=>files[x]+(y+1);
const same=(a,b)=>a&&b&&(a===a.toUpperCase())===(b===b.toUpperCase());
function legalTargets(pieces,from){
 const piece=pieces[from];if(!piece)return [];const [x,y]=point(from),type=piece.toLowerCase(),result=[];
 const add=(dx,dy,slide=false)=>{for(let n=1;n<=(slide?7:1);n++){const xx=x+dx*n,yy=y+dy*n;if(xx<0||xx>7||yy<0||yy>7)break;const to=square(xx,yy),target=pieces[to];if(same(piece,target)||target?.toLowerCase()==='k')break;result.push(to);if(target)break;}};
 if('rq'.includes(type))for(const d of [[1,0],[-1,0],[0,1],[0,-1]])add(...d,true);
 if('bq'.includes(type))for(const d of [[1,1],[1,-1],[-1,1],[-1,-1]])add(...d,true);
 if(type==='n')for(const d of [[1,2],[2,1],[-1,2],[-2,1],[1,-2],[2,-1],[-1,-2],[-2,-1]])add(...d);
 if(type==='k')for(const dx of [-1,0,1])for(const dy of [-1,0,1])if(dx||dy)add(dx,dy);
 if(type==='p'){const dy=piece==='P'?1:-1,yy=y+dy;if(yy>0&&yy<7){const to=square(x,yy);if(!pieces[to]){result.push(to);if(y===(piece==='P'?1:6)&&!pieces[square(x,y+2*dy)])result.push(square(x,y+2*dy));}for(const dx of [-1,1])if(x+dx>=0&&x+dx<8){const target=square(x+dx,yy);if(pieces[target]&&!same(piece,pieces[target])&&pieces[target].toLowerCase()!=='k')result.push(target);}}}
 return result;
}
function movePieces(pieces,uci){const next={...pieces};next[uci.slice(2,4)]=next[uci.slice(0,2)];delete next[uci.slice(0,2)];return next;}
const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;};
const button=(text,fn)=>{const n=node('button',text,'btn');n.type='button';n.onclick=fn;return n;};
const host=node('section',null,'movement-studio');host.id='movementStudio';host.hidden=true;
host.innerHTML='<div class="movement-heading"><div id="movementPiece" aria-hidden="true"></div><div><h2 id="movementTitle" tabindex="-1">기초 직접 연습</h2><p id="movementRule"></p></div></div><div class="movement-task"><strong id="movementGoal"></strong><span id="movementProgress"></span></div><div id="movementBoard" class="board" aria-label="말 움직이기 연습판"></div><p id="movementFeedback" role="status" aria-live="polite"></p><div id="movementActions" class="btn-row"></div><details id="movementHelp"><summary>도움말 · 다른 과정 · 저장 상태</summary><p id="movementScope">이 판은 말의 움직임만 연습해요. 상대 차례와 체크는 없고, 같은 말을 계속 움직여요. 정식 대국 규칙이나 실력 점수와는 별도예요.</p><p id="movementSave" role="status"></p><div id="movementRetry"></div><label>보드 대신 도착 칸 고르기<select id="movementDestination" class="field"></select></label><button id="movementSubmit" class="btn">선택한 칸으로 이동</button><div id="movementChoices" class="btn-row"></div></details>';
$('v9LearnRoot').prepend(host);
window.cmaMovementRules={legalTargets,movePieces};
let entryRequested=false;
let owner=null,epoch=0,data=null,unit=null,pieces={},source=null,selected=null,moves=[],remaining=[],visited=[],mistakes=0,helped=false,done=false,stuck=false,pending=false,starting=false,loading=false,conflict=false,ruleState=null,demonstrating=false,demoGeneration=0,saveTimer=null,nextTimer=null,error='',localError=false;
const visible=()=>window.cmaNavigation?.current()==='learn/movement'&&host.getClientRects().length>0;
let clipIntro=false;
const lessonPhase=()=>unit?.teaching?.phase;
let clip=null,clipIndex=0,clipTimer=null,clipPlaying=false,clipRequest=0;
const clipPanel=node('div',null,'movement-clip');clipPanel.id='movementClip';clipPanel.hidden=true;$('movementFeedback').after(clipPanel);
const lessonPanel=node('div',null,'movement-lesson');lessonPanel.id='movementLesson';$('movementFeedback').after(lessonPanel);
const seenPrelude=new Set();
const key=id=>'cma_movement_draft_v1:'+id;
const prefix=(a,b)=>a.length<=b.length&&a.every((v,i)=>v===b[i]);
const dirty=()=>!!unit&&(!data?.active||moves.length!==data.active.moves.length||mistakes>(data.active.mistakes||0)||helped&&!data.active.helped);
function checkpoint(){if(!unit||conflict)return;try{localStorage.setItem(key(unit.session_id),JSON.stringify({version:unit.version,policy:unit.policy,moves,mistakes,helped}));localError=false;}catch{localError=true;error='이 기기의 임시 저장을 사용할 수 없어요. 서버 저장을 확인한 뒤 나가세요.';}}
function discardAcknowledged(){if(!unit||dirty())return;try{localStorage.removeItem(key(unit.session_id));}catch{}}
function clear(){closeClip(false);demoGeneration++;demonstrating=false;clearTimeout(saveTimer);clearTimeout(nextTimer);epoch++;owner=token;data=null;unit=null;pieces={};source=null;selected=null;moves=[];remaining=[];visited=[];mistakes=0;helped=false;done=false;stuck=false;pending=false;starting=false;loading=false;conflict=false;error='';localError=false;ruleState=null;render();}
function reconstruct(task,path){if(task.mode==='rule'){const r=cmaBasicRules.replay(task,path);return {board:fromFen(r.fen),pos:null,left:[],seen:r.visited,pathDone:r.done,rule:r};}let board=fromFen(task.fen),pos=task.source,left=[...task.remaining],seen=[...task.visited],pathDone=task.done;for(const value of path.slice(task.moves.length)){if(pathDone||value.slice(0,2)!==pos||!legalTargets(board,pos).includes(value.slice(2,4)))throw Error('기기에 남은 이동을 현재 저장 위치와 맞출 수 없어요.');board=movePieces(board,value);pos=value.slice(2,4);left=left.filter(s=>s!==pos);if(pos!==task.original_source&&!seen.includes(pos))seen.push(pos);pathDone=task.mode==='collect'?!left.length:seen.length>=task.required_moves;}return {board,pos,left,seen,pathDone};}
function apply(d,restore=true){conflict=false;data=d;unit=d.active;if(unit?.teaching?.phase==='explain'&&visible()){clip=unit.teaching.clip;clipIndex=0;clipIntro=true;}if(unit)unit.original_source=unit.moves[0]?.slice(0,2)||unit.source;if(!unit){pieces={};render();return;}moves=[...unit.moves];mistakes=unit.mistakes||0;helped=!!unit.helped;let draft=null;if(restore)try{const raw=localStorage.getItem(key(unit.session_id));draft=raw===null?null:JSON.parse(raw);if(raw!==null&&(!draft||typeof draft!=='object'||!Array.isArray(draft.moves)||draft.moves.length>unit.max_moves||draft.moves.some(m=>typeof m!=='string'||m.length>24)||!Number.isInteger(draft.mistakes??0)||(draft.mistakes??0)<0||(draft.mistakes??0)>10000||draft.helped!==undefined&&typeof draft.helped!=='boolean'||draft.version!==unit.version||draft.policy!==unit.policy)){conflict=true;error='기기의 임시 기록 형식을 확인하지 못했어요. 원본을 보관한 뒤 서버 위치로 이어갈 수 있어요.';draft=null;}}catch{conflict=true;error='기기의 임시 기록을 읽지 못했어요. 서버 기록은 유지됩니다.';}
 if(draft&&draft.version===unit.version&&draft.policy===unit.policy){if(prefix(unit.moves,draft.moves||[])){try{reconstruct(unit,draft.moves);moves=[...draft.moves];mistakes=Math.max(mistakes,draft.mistakes||0);helped=helped||!!draft.helped;}catch(e){conflict=true;error=e.message;}}else if(!prefix(draft.moves||[],unit.moves)){conflict=true;error='다른 화면의 이동과 달라요. 임시 이동을 보관한 채 저장 위치를 확인해 주세요.';}}
 const local=reconstruct(unit,moves);pieces=local.board;source=local.pos;selected=moves.length?source:null;remaining=local.left;visited=local.seen;done=local.pathDone;ruleState=local.rule||null;stuck=!done&&unit.symbol==='P'&&remaining.some(s=>Number(s[1])<=Number(source[1]));render();if(unit.prelude&&!moves.length&&!seenPrelude.has(unit.session_id)){seenPrelude.add(unit.session_id);queueMicrotask(()=>showPrelude());}if(dirty()&&!error)scheduleSave();}
function render(){host.classList.toggle('movement-error',!!error);$('movementTitle').textContent=unit?(unit.mode==='rule'?unit.name:unit.name+' 움직이기'):'기초 직접 연습';$('movementPiece').replaceChildren(unit?renderPiece(ruleState?.place_symbol||(unit.side==='black'?unit.symbol.toLowerCase():unit.symbol)):renderPiece('R'));$('movementRule').textContent=unit?.rule||'말을 한 번 골라 계속 움직여 보세요.';
 $('movementScope').textContent=unit?.mode==='rule'?(unit.kind==='place'?'말의 시작 자리를 놓는 연습이에요. 대국 중의 이동과는 달라요.':unit.kind==='square'?'설명에 맞는 칸을 직접 고르는 규칙 확인이에요.':'이 판은 체크와 킹의 안전을 포함한 합법 수로 연습해요. 상대 응수는 표시된 교육 예시이며 최선수 분석은 아니에요.'):'이 판은 말의 움직임만 연습해요. 상대 차례와 체크는 없고, 같은 말을 계속 움직여요. 실력 점수와 별도예요.';
 $('movementGoal').textContent=unit?(stuck?'폰은 뒤로 못 가요. 새 판에서 다시 해 보세요.':unit.goal):'룩부터 시작하거나 원하는 말을 골라요.';
 if(unit?.kind==='place'&&ruleState?.place_symbol)$('movementGoal').textContent=({R:'룩',N:'나이트',B:'비숍',Q:'퀸',K:'킹',P:'폰'})[ruleState.place_symbol]+'을 알맞은 시작 칸에 놓아보세요.';
 const idx=data?.units.findIndex(u=>u.id===unit?.unit_id);$('movementProgress').textContent=unit?(idx+1)+'/'+data.units.length+' · '+(unit.mode==='rule'?(ruleState?.failed?'다시 확인':done?'확인 완료':unit.kind==='place'?visited.length+'/'+Object.keys(unit.predicate.pieces).length+'개 배치':'직접 확인'):unit.mode==='collect'?remaining.length+'개 남음':Math.min(visited.length,unit.required_moves)+'/'+unit.required_moves+'곳'):'';
 $('movementFeedback').textContent=clip?clip.frames[clipIndex].text:demonstrating?'상대의 이동을 보세요. 잠시 뒤 내 차례예요.':error||ruleState?.feedback||(!unit?'':done?(dirty()||pending?'움직임 완료 · 저장을 확인하고 있어요.':'잘했어요! 다음 움직임으로 이어가요.'):unit.note||'');
 $('movementSave').textContent=error?'서버 저장 미확인 · 임시 이동은 이 기기에 보관합니다.':dirty()||pending?'서버에 저장 중 · 같은 말을 계속 움직일 수 있어요.':unit?'서버 저장 확인됨':'아직 시작하지 않았어요.';
 $('movementRetry').replaceChildren();if(error){$('movementRetry').append(button('저장 위치 확인 · 다시 저장',()=>load(false,true)));}
 const actions=$('movementActions');actions.replaceChildren();if(error){$('movementHelp').open=true;actions.append(button('저장 위치 확인 · 다시 저장',()=>load(false,true)));if(conflict)actions.append(button('기기 이동을 보관하고 서버 위치로 이어가기',recoverConflict));}if(!unit)actions.append(button(token?'룩부터 움직이기':'로그인 없이 시작',()=>window.cmaMovement.enter()));else if(stuck||ruleState?.failed||moves.length>=unit.max_moves&&!done)actions.append(button('새 판에서 다시 해보기',()=>restart()));else if(done&&!pending&&!dirty()&&!error){const last=idx+1===data.units.length;actions.append(button(last?'원하는 활동 고르기':'다음 확인 계속하기',()=>last?window.cmaNavigation.go('learn'):start('next')));}
 if(unit?.mode==='rule'){actions.append(button('짧은 시연 · 정답 도움',()=>openClip(unit.unit_id)));if(done)actions.append(button('같은 문제 직접 다시',()=>restart()));}
 if(unit?.relationship_available&&!unit.teaching)actions.append(button('기록 보존 · 설명부터 새로',()=>restart()));
 const previous=data?.units[idx-1];if(unit&&previous?.mode==='rule')actions.append(button('직전 문제 시연',()=>openClip(previous.id)));
 if(unit?.prelude&&!moves.length)actions.append(button('상대 이동 다시 보기',showPrelude));
 const choices=$('movementChoices');choices.replaceChildren();const selector=node('select');selector.id='movementUnit';selector.className='field';selector.setAttribute('aria-label','움직임 연습 선택');let group=null,groupId=null;for(const [i,u] of (data?.units||[]).entries()){if(groupId!==u.stage){group=node('optgroup');group.label=stages[u.stage]||u.stage;selector.append(group);groupId=u.stage;}group.append(new Option((i+1)+'. '+(u.short_title||u.name)+(u.mode==='rule'?' · 규칙 확인':u.mode==='apply'?' · 표시 없이 확인':' · 표시 모으기')+(u.done?' · 해봄':u.completed_before?' · 이전 완료·다시 연습 중':''),u.id));}if(unit)selector.value=unit.unit_id;choices.append(selector,button('고른 연습 열기',()=>choose(selector.value)),button('이전 기초 과정 · 저장된 학습',()=>window.cmaNavigation.go('learn/basics')));
 for(const b of actions.querySelectorAll('button'))b.disabled=starting||demonstrating||loading||(b.textContent.startsWith('새 판')&&(dirty()||pending));selector.disabled=starting||pending||dirty();choices.querySelector('button').disabled=starting||pending||dirty();
 $('movementHelp').querySelector('label').hidden=!unit||done;$('movementSubmit').hidden=!unit||done;$('movementSubmit').disabled=lessonPhase()==='explain'||lessonPhase()==='guided'||!unit||done||starting||loading||conflict||demonstrating;
 const dest=$('movementDestination'),old=dest.value;dest.replaceChildren();for(let r=1;r<=8;r++)for(const f of files)dest.add(new Option(f+r,f+r));if(old)dest.value=old;
 if(clip){$('movementTitle').textContent=clip.name+(clipIntro?' · 설명':' · 시연');$('movementRule').textContent=clipIntro?'짧게 보고 → 따라 두고 → 혼자 확인해요.':clip.label;$('movementGoal').textContent=clip.frames[clipIndex].text;$('movementProgress').textContent=clipIntro?'1/3 · 관계 이해':'직접 연습은 잠시 보관 중';}$('movementFeedback').hidden=!!clip;renderClip();renderLesson();if(unit)paint();else $('movementBoard').replaceChildren();
}
function paint(){if(!unit)return;if(lessonPhase()==='explain'&&!clip){drawBoard('movementBoard',fromFen(unit.initial_fen),{flip:unit.side==='black'});return;}if(lessonPhase()==='guided'&&!clip){paintGuide();return;}if(clip){const f=clip.frames[clipIndex];drawBoard('movementBoard',fromFen(f.fen),{flip:clip.side==='black',last:f.move?[f.move.slice(0,2),f.move.slice(2,4)]:[]});for(const sq of f.marks){const cell=$('movementBoard').querySelector(`[aria-label^="${sq} "]`);if(cell){cell.classList.add('clip-mark');cell.setAttribute('aria-label',cell.getAttribute('aria-label')+' · 시연 강조');}}window.cmaFoundationVisual?.draw('movementBoard',{arrows:f.arrows||[]},clip.side==='black');return;}const focus=$('movementBoard').contains(document.activeElement)?document.activeElement.getAttribute('aria-label')?.split(' ')[0]:null;
 const allowed=unit.mode==='rule'?(ruleState?.legal||[]).filter(m=>m.slice(0,2)===selected).map(m=>m.slice(2,4)):legalTargets(pieces,source),guide=unit.mode==='collect'||unit.mode==='rule'&&!unit.teaching;drawBoard('movementBoard',pieces,{flip:unit.side==='black',selected,targets:selected&&guide?allowed.map(to=>({to})):[],onClick:!done&&!ruleState?.failed&&!starting&&!loading&&!conflict&&!demonstrating?s=>click(s):undefined});
 for(const s of [...remaining,...(unit.teaching?[]:unit.target_squares||[])]){const cell=$('movementBoard').querySelector(`[aria-label^="${s} "]`);if(cell){const mark=node('span','◆','movement-target');mark.setAttribute('aria-hidden','true');cell.append(mark);cell.setAttribute('aria-label',cell.getAttribute('aria-label')+' · 모을 표시');}}
 if(focus)$('movementBoard').querySelector(`[aria-label^="${focus} "]`)?.focus({preventScroll:true});
}
function renderLesson(){
 lessonPanel.replaceChildren();lessonPanel.hidden=!unit?.teaching||!!clip;if(lessonPanel.hidden)return;
 const t=unit.teaching;lessonPanel.append(node('strong',t.phase==='explain'?'1/3 · 먼저 관계 이해하기':t.phase==='guided'?'2/3 · 안내 따라 하기':'3/3 · 안내 없이 직접 확인'));
 if(t.phase==='explain'){
  lessonPanel.append(button('설명 다시 열기',()=>{clip=t.clip;clipIndex=0;clipIntro=true;render();}));
 }else if(t.phase==='guided'){
  lessonPanel.append(node('p',t.guide_done?'따라 하기를 마쳤어요. 이제 처음 위치에서 화살표 없이 해보세요.':'실선 화살표를 따라 두어요. 완료 확인은 다음 혼자 풀기에서 해요.'));
  if(t.guide_done)lessonPanel.append(button('이제 혼자 풀기',()=>lessonAction('independent')));
  lessonPanel.append(button('따라 하기 건너뛰기',()=>lessonAction('skip')),button('설명부터 다시',()=>restart()));
 }else{
  lessonPanel.append(node('p',done?(unit.practice_result==='assisted_application'?'시연 도움을 받아 직접 완료했어요.':'안내 없이 완료 · 앞서 본 같은 문제예요.'):'정답 화살표 없이 직접 해보세요. 다시 시연을 보면 도움받은 완료로 구분해요.'));
 }
 for(const b of lessonPanel.querySelectorAll('button'))b.disabled=starting||loading||pending||!!error;
}
function paintGuide(){
 const focus=$('movementBoard').contains(document.activeElement)?document.activeElement.getAttribute('aria-label')?.slice(0,2):null;
 const t=unit.teaching,f=t.guide_state,action=t.next_action,from=action?.slice(0,2),to=action?.startsWith('square:')?action.slice(7):action?.slice(2,4);
 drawBoard('movementBoard',fromFen(f.fen),{flip:unit.side==='black',selected,onClick:!starting&&!loading&&!error&&!t.guide_done?guideClick:undefined});
 const arrows=(t.relations||[]).slice(0,1);if(action&&!action.startsWith('square:'))arrows.push({from,to,kind:'guide'});
 window.cmaFoundationVisual?.draw('movementBoard',{arrows},unit.side==='black');
 for(const [sq,label] of [[from,'출발'],[to,'도착']]){const cell=$('movementBoard').querySelector(`[aria-label^="${sq} "]`);if(cell){cell.classList.add('clip-mark');cell.setAttribute('aria-label',cell.getAttribute('aria-label')+' · 따라 하기 '+label);}}
 $('movementGoal').textContent=t.guide_done?'따라 하기 완료 · 다음은 혼자 풀기':action?.startsWith('square:')?to+' 칸을 눌러요.':from+' → '+to+' · 실선 화살표를 따라 두어요.';
 $('movementFeedback').textContent=t.relations?.[0]?.label||'이동 후 공격 관계도 현재 배치로 다시 확인해요.';
 if(focus)[...$('movementBoard').querySelectorAll('.sq')].find(cell=>cell.getAttribute('aria-label').startsWith(focus+' '))?.focus({preventScroll:true});
}
function guideClick(to){
 if(starting||loading||pending||error||clip||owner!==token)return;
 const action=unit?.teaching?.next_action;if(!action)return;
 if(action.startsWith('square:')){if(action==='square:'+to)lessonAction('step',action);else $('movementFeedback').textContent='안내된 '+action.slice(7)+' 칸을 찾아보세요.';return;}
 const from=action.slice(0,2),target=action.slice(2,4);
 if(to===from){selected=from;paint();return;}
 if(selected===from&&to===target){lessonAction('step',action);return;}
 $('movementFeedback').textContent=from+'의 말을 고른 뒤 '+target+' 칸을 눌러요.';
}
async function lessonAction(action,move=''){
 if(starting||loading||pending||error||!unit?.teaching||owner!==token)return;
 pauseClip();const id=token,stamp=epoch,session=unit.session_id;starting=true;render();
 try{const d=await api('/movement/lesson','POST',{session_id:session,revision:data.revision,action,move});if(id!==token||stamp!==epoch||session!==unit?.session_id)return;
 const played=action==='step'?d.active.teaching.guide_state.played.slice(unit.teaching.guide_state.played.length):[];closeClip(false);selected=null;if(played.length)cmaBoardPresentation.transition('movementBoard',played,()=>apply(d,false));else apply(d,false);
 }catch(e){if(id===token&&stamp===epoch)error=e.message;}
 finally{if(id===token&&stamp===epoch){starting=false;render();}}
}
function pauseClip(){clearTimeout(clipTimer);clipPlaying=false;if(clip)renderClip();}
function closeClip(draw=true){cmaBoardPresentation.cancel('movementBoard');pauseClip();clipRequest++;clip=null;clipIntro=false;clipIndex=0;clipPanel.hidden=true;if(draw){render();$('movementActions button')?.focus({preventScroll:true});}}
function showClipFrame(index){const previous=clipIndex;clipIndex=index;const move=clip.frames[Math.max(previous,index)].move;if(Math.abs(previous-index)===1&&move)cmaBoardPresentation.transition('movementBoard',move,render,index<previous);else render();}
function stepClip(index){pauseClip();showClipFrame(Math.max(0,Math.min(clip.frames.length-1,index)));}
function tickClip(){clearTimeout(clipTimer);clipTimer=setTimeout(()=>{if(!clip||!clipPlaying||!visible()||document.hidden){pauseClip();return;}if(clipIndex>=clip.frames.length-1){pauseClip();return;}showClipFrame(clipIndex+1);tickClip();},1600);}
function renderClip(){const focused=clipPanel.contains(document.activeElement)?document.activeElement.textContent:null;clipPanel.hidden=!clip;clipPanel.replaceChildren();if(!clip)return;
 const f=clip.frames[clipIndex];if(clipIntro)clipPanel.append(node('strong','1/3 · 먼저 관계 이해하기'));clipPanel.append(node('span',`${clipIndex+1}/${clip.frames.length} · ${f.turn} 차례`));
 const controls=node('div',null,'btn-row');clipPanel.append(controls);
 const previous=button('이전 수',()=>stepClip(clipIndex-1));previous.disabled=clipIndex===0;
 const next=button('다음 수',()=>stepClip(clipIndex+1));next.disabled=clipIndex===clip.frames.length-1;
 controls.append(previous,button(clipPlaying?'멈춤':'재생',()=>{if(clipPlaying)pauseClip();else{if(clipIndex===clip.frames.length-1)clipIndex=0;clipPlaying=true;render();tickClip();}}),next,button('처음부터',()=>stepClip(0)),button(clipIntro?'건너뛰고 혼자 풀기':'닫고 직접 연습',()=>clipIntro?lessonAction('skip'):closeClip()));
 if(clipIntro)controls.append(button('설명 확인 · 따라 하기',()=>lessonAction('guided')));
 clipPanel.append(node('small','파선: 공격 · 실선: 따라 둘 수. 공격 표시만으로 항상 잡을 수 있다는 뜻은 아니에요.'));
 for(const b of $('movementActions').querySelectorAll('button'))b.disabled=true;
 $('movementSubmit').disabled=true;
 if(focused){const label=['재생','멈춤'].includes(focused)?(clipPlaying?'멈춤':'재생'):focused;([...controls.querySelectorAll('button')].find(b=>b.textContent===label&&!b.disabled)||controls.querySelector('button:not(:disabled)'))?.focus({preventScroll:true});}
}
async function openClip(unitId){if(clip||starting||pending||loading||demonstrating||conflict||error)return;
 clearTimeout(nextTimer);if(dirty()){await save();if(dirty()||error)return;}
 const id=token,stamp=epoch,session=unit.session_id,request=++clipRequest;
 starting=true;render();
 try{const response=await api('/movement/demo','POST',{unit_id:unitId,session_id:session,revision:data.revision});
 if(id!==token||stamp!==epoch||session!==unit?.session_id)return;
 data=response.dashboard;unit={...unit,...data.active};helped=unit.helped;discardAcknowledged();
 if(request===clipRequest&&visible()){clip=response.clip;clipIntro=false;clipIndex=0;selected=null;}
 }catch(e){if(id===token&&stamp===epoch){error=e.message;}}
 finally{if(id===token&&stamp===epoch){starting=false;render();}}
}
function reason(to){const p=pieces[source],target=pieces[to];if(target&&same(p,target))return '내 말이 있는 칸에는 갈 수 없어요.';return ({R:'룩은 가로나 세로로 가요. 막힌 길은 지나갈 수 없어요.',B:'비숍은 비스듬히 가요. 막힌 길은 지나갈 수 없어요.',N:'나이트는 두 칸 간 뒤 옆으로 한 칸 뛰어요.',Q:'퀸은 가로·세로·비스듬히 가요. 막힌 길은 지나갈 수 없어요.',K:'킹은 주변 한 칸으로 가요.',P:'폰은 빈 앞칸으로 가고, 비스듬한 앞칸의 상대 말을 잡아요.'})[unit.symbol];}
function click(to){if(lessonPhase()==='explain')return;if(lessonPhase()==='guided'&&!clip){guideClick(to);return;}if(clip||!unit||done||ruleState?.failed||starting||loading||conflict||demonstrating||owner!==token)return;if(unit.mode==='rule'){ruleClick(to);return;}if(to===source){selected=selected?null:source;paint();return;}if(!selected){selected=null;paint();$('movementFeedback').textContent='먼저 '+unit.name+'을 눌러 주세요.';return;}
 if(!legalTargets(pieces,source).includes(to)){mistakes=Math.min(10000,mistakes+1);selected=null;checkpoint();paint();$('movementFeedback').textContent=reason(to);scheduleSave();return;}
 if(moves.length>=unit.max_moves){$('movementFeedback').textContent='이 판의 연습 한도예요. 기록을 보존하고 새 판에서 이어갈 수 있어요.';render();return;}
 const uci=source+to;pieces=movePieces(pieces,uci);source=to;selected=to;moves.push(uci);remaining=remaining.filter(s=>s!==to);if(to!==unit.original_source&&!visited.includes(to))visited.push(to);done=unit.mode==='collect'?!remaining.length:visited.length>=unit.required_moves;stuck=!done&&unit.symbol==='P'&&remaining.some(s=>Number(s[1])<=Number(source[1]));checkpoint();window.cmaBoardPresentation.transition('movementBoard',uci,render);scheduleSave();
}
async function showPrelude(){if(!unit?.prelude||moves.length||demonstrating)return;const id=token,session=unit.session_id,generation=++demoGeneration,prelude=unit.prelude;demonstrating=true;selected=null;pieces=fromFen(prelude.before_fen);render();await new Promise(r=>setTimeout(r,400));if(id!==token||session!==unit?.session_id||generation!==demoGeneration)return;cmaBoardPresentation.transition('movementBoard',prelude.moves,()=>{pieces=fromFen(ruleState.fen);render();});await new Promise(r=>setTimeout(r,500));if(id===token&&session===unit?.session_id&&generation===demoGeneration){demonstrating=false;render();}}
function cancelPrelude(){demoGeneration++;if(demonstrating){demonstrating=false;if(ruleState)pieces=fromFen(ruleState.fen);render();}}
async function ruleClick(to){let action;if(unit.kind==='square')action='square:'+to;else if(unit.kind==='place')action='place:'+ruleState.place_symbol+':'+to;else{const legal=ruleState.legal;if(legal.some(m=>m.slice(0,2)===to)){selected=selected===to?null:to;paint();return;}if(!selected){$('movementFeedback').textContent='먼저 움직일 내 말을 눌러 주세요.';return;}const options=legal.filter(m=>m.slice(0,2)===selected&&m.slice(2,4)===to);if(!options.length){selected=null;mistakes++;checkpoint();paint();$('movementFeedback').textContent='그 이동은 둘 수 없어요. 막힌 길과 킹의 안전을 확인해 주세요.';scheduleSave();return;}action=options.find(m=>m.length===4);if(!action){const id=token,stamp=epoch,view=cmaNavigation.version(),from=selected;starting=true;render();const promotion=await choosePromotion(from,to,pieces[from],options);if(id!==token||stamp!==epoch)return;starting=false;render();if(promotion===null||view!==cmaNavigation.version())return;action=from+to+promotion;}}
try{const priorPlayed=ruleState.played.length,result=cmaBasicRules.replay(unit,[...moves,action]);moves.push(action);ruleState=result;pieces=fromFen(result.fen);remaining=[];visited=result.visited;source=null;selected=null;done=result.done;checkpoint();if(action.length<=5)cmaBoardPresentation.transition('movementBoard',result.played.slice(priorPlayed),render);else render();scheduleSave();}catch(e){$('movementFeedback').textContent=e.message;}}
function scheduleSave(){clearTimeout(saveTimer);saveTimer=setTimeout(()=>save(),120);}
async function save(){if(pending||starting||loading||conflict||!unit||!dirty()||owner!==token||error&&!localError)return;const id=token,stamp=epoch,session=unit.session_id,body={unit_id:unit.unit_id,session_id:session,revision:data.revision,version:unit.version,policy:unit.policy,moves:[...moves],mistakes,helped};pending=true;render();try{const d=await api('/movement/save','POST',body);if(id!==token||stamp!==epoch||unit?.session_id!==session)return;if(!d.active||d.active.session_id!==session||!prefix(d.active.moves,moves))throw Error('다른 화면에서 연습이 바뀌었어요. 임시 이동은 보관했습니다.');data=d;unit={...unit,...d.active};error='';discardAcknowledged();}catch(e){if(id===token&&stamp===epoch){error=e.message;checkpoint();}}finally{if(id===token&&stamp===epoch){pending=false;render();if(!error&&dirty())scheduleSave();else if(!error&&done&&visible())autoNext();}}}
function autoNext(){clearTimeout(nextTimer);if(clip||unit?.mode==='rule'||!unit||$('movementHelp').open||unit.predicate?.type==='stalemate'||data.units.findIndex(u=>u.id===unit.unit_id)+1>=data.units.length)return;const id=token,stamp=epoch,session=unit.session_id,route=window.cmaNavigation.version();nextTimer=setTimeout(()=>{if(id===token&&stamp===epoch&&session===unit?.session_id&&route===window.cmaNavigation.version()&&visible()&&!document.hidden&&!$('movementHelp').open&&!dirty()&&!pending)start('next');},unit.mode==='rule'?2400:650);}
async function recoverConflict(){if(!conflict||!unit||loading||pending)return;try{const activeKey=key(unit.session_id),draft=localStorage.getItem(activeKey);if(draft!==null){localStorage.setItem(activeKey+':preserved:'+crypto.randomUUID(),draft);localStorage.removeItem(activeKey);}conflict=false;await load();}catch{error='기기 이동을 따로 보관하지 못했어요. 원래 임시 기록을 유지합니다.';render();}}
async function load(enter=false,retry=false){if(enter)entryRequested=true;if(owner!==token)clear();if(!token){render();return;}if(starting||pending||loading)return;closeClip(false);const id=token,stamp=++epoch;clearTimeout(nextTimer);clearTimeout(saveTimer);loading=true;error='';render();let loaded=null;try{const d=await api('/movement');if(id!==token||stamp!==epoch)return;if(d.active?.mode==='rule')await cmaBasicRules.load();if(id!==token||stamp!==epoch)return;loaded=d;apply(d,true);}catch(e){if(id===token&&stamp===epoch){error=e.message;}}finally{if(id===token&&stamp===epoch){loading=false;render();if(!error&&dirty())scheduleSave();}}if(loaded&&id===token&&stamp===epoch&&entryRequested){entryRequested=false;if(!loaded.active)await start('start');}}

async function start(action,unit_id){if(starting||pending||loading||conflict||owner!==token||!data)return;if(dirty()){error='아직 저장을 확인하지 못했어요. 현재 이동을 먼저 저장해 주세요.';render();return;}closeClip(false);const id=token,stamp=epoch,request_id=crypto.randomUUID();starting=true;clearTimeout(nextTimer);render();try{const d=await api('/movement/start','POST',{action,unit_id,revision:data.revision,request_id,relationship_flow:true});if(id!==token||stamp!==epoch)return;if(d.active?.mode==='rule')await cmaBasicRules.load();if(id!==token||stamp!==epoch)return;error='';apply(d,true);if(visible())$('movementTitle').focus({preventScroll:true});}catch(e){if(id===token&&stamp===epoch){error=e.message;render();}}finally{if(id===token&&stamp===epoch){starting=false;render();}}}
async function choose(id){if(dirty()||pending){error='현재 이동의 저장을 확인한 뒤 다른 연습으로 갈 수 있어요.';render();return;}await start('start',id);}
async function restart(){if(dirty()||pending){error='현재 이동의 저장을 확인한 뒤 새 판으로 갈 수 있어요.';render();return;}await start('restart',unit.unit_id);}
$('movementHelp').addEventListener('toggle',()=>{if($('movementHelp').open)clearTimeout(nextTimer);});
$('movementSubmit').onclick=()=>{if(unit?.mode!=='rule')selected=source;click($('movementDestination').value);};
window.cmaMovement={load,async enter(){entryRequested=true;window.cmaNavigation.go('learn/movement',{load:false});if(!token)await window.cmaGuestAccess.enter('learn/movement',message=>{$('movementFeedback').textContent=message;});if(token)await load(true);},route(path){if(path!=='learn/movement'){closeClip(false);cancelPrelude();clearTimeout(nextTimer);if(unit&&dirty())checkpoint();}else if(owner!==token)clear();},preferred:summary=>!!summary?.movement?.preferred,state:()=>({data,unit,moves:[...moves],source,selected,remaining:[...remaining],done,pending,loading,conflict,ruleState,demonstrating,error,clip,clipIndex,clipPlaying}),cancel(){closeClip(false);cancelPrelude();clearTimeout(nextTimer);if(unit&&dirty())checkpoint();}};
window.addEventListener('pagehide',()=>{pauseClip();cancelPrelude();if(unit&&dirty())checkpoint();clearTimeout(nextTimer);});document.addEventListener('visibilitychange',()=>{if(document.hidden){pauseClip();cancelPrelude();clearTimeout(nextTimer);if(unit&&dirty())checkpoint();}});$('signout')?.addEventListener('click',clear);
})();
