/* Server-owned repertoire attempts, distinct from bookmarks and diagnostic credit. */
(()=>{'use strict';
const $=id=>document.getElementById(id),make=(p,t,text,cls)=>{const e=document.createElement(t);if(text!=null)e.textContent=text;if(cls)e.className=cls;p.append(e);return e;};
const host=make($('opening'),'section',null,'card repertoire');host.id='repertoire';$('openingStudy').before(host);
make(host,'h2','내 오프닝 레퍼토리');make(host,'p','선택 → 해설 학습 → 답을 가린 재현 → 도움·이탈 위치 재연습. 기존 강의 탐색과 북마크는 별도로 보존합니다.');make(host,'p','신규 심화 설명 15개는 런던·조바바의 백 차례 핵심 위치를 다룹니다. 흑 수 재현에서는 기존 착수 해설과 규칙 사실을 사용하며 동일한 심화 해설을 제공하지 않습니다.','subtle');
const open=make(host,'button','레퍼토리 선택·이어하기','btn primary'),refresh=make(host,'button','저장 상태 다시 확인','btn');
const status=make(host,'p','로그인한 계정별로 저장합니다.','notice');status.id='repertoireStatus';status.setAttribute('role','status');
const body=make(host,'div');body.id='repertoireBody';body.hidden=true;
let data=null,owner=null,serial=0,busy=false,failed=false,selected=null,opened=false;
const button=(p,label,fn)=>{const b=make(p,'button',label,'btn');b.type='button';b.onclick=fn;return b;};
function others(){for(const e of [...$('opening').children])if(e!==host&&!e.classList.contains('feature-toolbar'))e.hidden=opened;}
function clear(){data=null;owner=token;selected=null;body.replaceChildren();status.textContent='저장 상태를 확인하세요.';}
function controls(){host.setAttribute('aria-busy',String(busy));for(const b of body.querySelectorAll('button,select,input'))b.disabled=busy||b.dataset.blocked==='true'||(failed&&b.dataset.navigation!=='true');open.disabled=busy;refresh.disabled=busy;}
async function request(action,extra={}){if(busy)return false;const identity=token,stamp=++serial;busy=true;failed=false;selected=null;controls();
 try{const value=await api(action?'/repertoire/action':'/repertoire',action?'POST':'GET',action?{action,revision:data.revision,attempt_id:data.active?.id,...extra}:undefined);if(stamp!==serial||identity!==token)return false;data=value;owner=identity;status.textContent=action?'레퍼토리 기록을 저장했습니다.':'저장된 레퍼토리를 불러왔습니다.';render();return true;}
 catch(e){if(stamp===serial&&identity===token){failed=true;status.textContent=e.message+' 저장 상태를 다시 확인한 뒤 계속하세요.';}return false;}
 finally{if(stamp===serial){busy=false;controls();draw();}}}
function render(){body.replaceChildren();if(!data)return;const r=data.active,hiddenAnswers=r?.mode==='recall'&&r.phase==='playing';
 if(data.capacity_notice)make(body,'p',data.capacity_notice,'notice');if(data.retained_legacy_attempt)make(body,'p','이전 한도 예외 상태의 시도 1개를 정규64개와 별도로 보존했습니다. 기존 기록은 삭제하지 않았습니다.','subtle');
 const newAttempt=(label,fn)=>{const b=button(body,label,fn);b.dataset.blocked=String(data.can_start===false);};
 if(!r){const intro=make(body,'details');make(intro,'summary','레퍼토리 선택 · 최대16강');intro.open=!data.selected.length;const checks=[];const extra=make(intro,'details');make(extra,'summary','다른 기존 강의 선택');
 for(const c of [...data.catalog].sort((a,b)=>Number(b.core)-Number(a.core))){const label=make(c.core?intro:extra,'label',null,'repertoire-choice'),input=make(label,'input');input.type='checkbox';input.value=c.id;input.checked=data.selected.includes(c.id);checks.push(input);make(label,'span',(c.core?'핵심 · ':'')+c.title);}
 button(intro,'선택 저장',()=>request('select',{selected:checks.filter(c=>c.checked).map(c=>c.value)}));
 const pick=make(body,'select',null,'field');pick.setAttribute('aria-label','내 레퍼토리 레슨');for(const c of data.catalog.filter(c=>data.selected.includes(c.id))){const o=make(pick,'option',c.title);o.value=c.id;}
 const side=make(body,'select',null,'field');side.setAttribute('aria-label','레퍼토리 연습 색');for(const [v,t] of [['white','백 수 재현'],['black','흑 대응 재현']]){const o=make(side,'option',t);o.value=v;}
 if(data.selected.length){newAttempt('해설 보며 학습 시작',()=>request('start',{lesson_id:pick.value,side:side.value,mode:'learn'}));newAttempt('답 가리고 복습 시작',()=>request('start',{lesson_id:pick.value,side:side.value,mode:'recall'}));}
 }else{
 make(body,'h3',hiddenAnswers?'선택 레슨 · 답 가린 복습':r.title);make(body,'p',`${r.side==='white'?'백':'흑'} 수 재현 · 진행 ${r.moves.length}반수 · 이번 계열 누적 도움 ${r.hints} · 이탈 ${r.deviations}`);
 const metric=data.metrics[r.lesson_id];make(body,'p',`이 레슨 백·흑 통합 누적 도움 ${metric.hints} · 이탈 ${metric.deviations} · 복습 시도 ${metric.recall_attempts}회. 첫 복습 결과도 레슨 단위로 백·흑을 통합하며 재시도로 덮어쓰지 않습니다.`,'subtle');
 if(metric.first_recall){const first=metric.first_recall;make(body,'p',`레슨 통합 첫 복습 · ${first.side==='white'?'백':first.side==='black'?'흑':'색 미기록 (이전 결과)'} · `+(metric.first_recall.completed?(metric.first_recall.clean?'첫 복습: 전체 예시를 복습 중 도움·이탈 없이 재현 (이전 학습 노출과 별개).':'첫 복습: 도움·이탈 또는 부분 재연습을 포함한 완료.'):'첫 복습: 미완료 또는 재시도. 이후 완료와 구분합니다.'));}
 const layout=make(body,'div',null,'repertoire-layout');make(layout,'div',null,'board').id='repertoireBoard';const info=make(layout,'div');make(info,'p',r.outdated?'콘텐츠가 개정되었습니다. 기존 시도를 기록으로 마친 뒤 새 버전을 선택하세요.':r.feedback,'notice');
 if(r.guidance){for(const [k,label] of [['placement','배치 특징'],['opponent','상대 목표'],['plan','가능한 계획'],['exception','예외와 한계']]){make(info,'h4',label);make(info,'p',r.guidance[k]);}if(r.guidance.move_note){make(info,'p',r.guidance.move_note.facts);if(r.guidance.move_note.comment)make(info,'p',r.guidance.move_note.comment);}}
 for(const o of r.options)button(info,o.san+' · 등록 예시 수',()=>request('move',{move:o.move}));
 if(r.phase==='playing'&&!r.outdated)button(body,'현재 수·설명 힌트 (도움 기록)',()=>request('hint'));
 if(!r.outdated){newAttempt('처음부터 다시 연습 (이력 유지)',()=>request('retry'));if(r.weak_points.length)newAttempt('도움·이탈 위치부터 다시 연습',()=>request('weak'));}
 if(r.phase==='complete'&&r.mode==='learn')newAttempt('같은 레슨 답 가리고 복습',async()=>{const identity=token,generation=serial;const ok=await request('finish');if(ok&&identity===token&&generation+1===serial&&opened&&$('opening').classList.contains('active'))request('start',{lesson_id:r.lesson_id,side:r.side,mode:'recall'});});
 button(body,r.phase==='complete'?'결과 보관 후 레슨 선택':'이 시도 기록하고 마치기',()=>request('finish'));
 const log=make(body,'details');make(log,'summary','내 입력·도움·이탈 이력');for(const p of r.weak_points)make(log,'p',`이전 시도 포함 도움·이탈 위치: ${p.ply}반수${hiddenAnswers?'':(' · '+(p.moves.join(' → ')||'초기 위치'))}`);for(const e of r.events)make(log,'p',`${e.ply}반수 위치 · ${e.kind==='hint'?'힌트':e.kind==='deviation'?'등록 수순 이탈':'등록 수 재현'}${e.move?' · '+e.move:''}`);
 }
 if(!hiddenAnswers){const history=make(body,'details');make(history,'summary','완료·중단 기록 '+data.history.length+'개');for(const r of [...data.history].reverse())make(history,'p',`${r.title} · ${r.mode==='recall'?'복습':'학습'} · ${r.phase==='complete'?'완료':'중단'} · 도움 ${r.hints} · 이탈 ${r.deviations}`);}
 make(body,'p',data.policy,'subtle');const leave=button(body,hiddenAnswers?'기존 탐색 보기 (복습 도움 기록)':'기존 강의 탐색·북마크 보기',async()=>{if(hiddenAnswers){const identity=token,generation=serial;if(!await request('hint')||identity!==token||generation+1!==serial||!$('opening').classList.contains('active'))return;}opened=false;body.hidden=true;others();});if(!hiddenAnswers)leave.dataset.navigation='true';const home=button(body,'홈으로 돌아가기',()=>tab('home'));home.dataset.navigation='true';controls();draw();}
function draw(){const r=data?.active;if(!$('repertoireBoard')||!r)return;drawBoard('repertoireBoard',fromFen(r.fen),{flip:r.side==='black',selected,targets:selected?r.legal.filter(u=>u.slice(0,2)===selected).map(u=>({to:u.slice(2,4)})):[],onClick:!busy&&!failed&&r.phase==='playing'&&!r.outdated?click:undefined});}
async function click(square){const r=data?.active;if(!r||busy||failed)return;const choices=r.legal.filter(u=>u.slice(0,2)===selected&&u.slice(2,4)===square);if(!choices.length){selected=r.legal.some(u=>u.slice(0,2)===square)?square:null;draw();return;}let move=choices[0];if(choices.length>1){const stamp=serial,identity=token;busy=true;controls();try{const suffix=await choosePromotion(selected,square,fromFen(r.fen)[selected],r.legal);if(!suffix||stamp!==serial||identity!==token||!$('opening').classList.contains('active'))return;move=choices.find(u=>u[4]===suffix);}finally{busy=false;controls();draw();}}if(move)request('move',{move});}
open.onclick=()=>{opened=true;body.hidden=false;others();request();};refresh.onclick=()=>request();
const previous=tab;tab=function(id){++serial;busy=false;if(owner!==token)clear();previous(id);if(id==='opening'){others();if(opened)request();}};
$('signout')?.addEventListener('click',()=>{++serial;busy=false;clear();opened=false;body.hidden=true;others();});
})();
