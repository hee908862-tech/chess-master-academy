/* Educational comparisons, independent of diagnostic credits. */
(()=>{'use strict';
const $=id=>document.getElementById(id),make=(p,t,text)=>{const e=document.createElement(t);if(text!=null)e.textContent=text;p.append(e);return e;};
const host=make($('learn'),'section');host.className='card education';host.id='educationPaths';
make(host,'h2','관찰 → 계획 → 종반 · 짧은 교육 경로');
make(host,'p','기초 규칙을 배운 뒤 실제 배치를 관찰하고 이유를 비교합니다. 5분은 한 경로, 15분은 위협·계획·종반에서 하나씩 선택하는 권장량(추정)이며 제한시간이 아닙니다.');
const btn=(p,t,f)=>{const b=make(p,'button',t);b.className='btn';b.type='button';b.onclick=f;return b;};
const help=make(host,'details');make(help,'summary','사용 방법');make(help,'p','목적: 공격·배치·규칙 사실과 계획 후보를 구분합니다. 시작: 경로와 학습/복습을 선택하세요. 조작: 칸 선택 또는 출발·도착 칸을 차례로 누르며, 목록 착수도 가능합니다. 저장: 입력마다 계정별 저장, 새로고침 후 이어하기. 결과: 교육 예시 완료이며 독립 숙련·진단 점수·추천5개·7일 확인에 합산하지 않습니다. 복습의 설명 힌트는 도움으로 기록되며 이 사용 방법 열기는 기록되지 않습니다. 재시도는 결과를 보관한 뒤 시작하고 누적 도움·다른 응답은 유지합니다. 보관64회/시도256행/전체1MiB 한도에서 자동 삭제하지 않으며 기존 결과 조회와 시도 종료가 가능합니다.');
const status=make(host,'p','경로 보기로 저장 상태를 확인하세요.');status.id='educationStatus';status.setAttribute('role','status');
const open=btn(host,'교육 경로 보기 · 이어하기',()=>{opened=true;request();});
const refresh=btn(host,'저장 상태 다시 확인',()=>request());
const body=make(host,'div');body.id='educationBody';
let data=null,owner=null,generation=0,busy=false,failed=false,opened=false,listVisible=false,selected=null,flip=false;
function controls(){host.setAttribute('aria-busy',String(busy));for(const b of body.querySelectorAll('button,select'))b.disabled=busy||b.dataset.blocked==='true'||(failed&&b.dataset.navigation!=='true');open.disabled=busy;refresh.disabled=busy;}
async function request(action,extra={}){if(busy)return false;const identity=token,stamp=++generation;busy=true;failed=false;selected=null;controls();
 try{const value=await api(action?'/education/action':'/education',action?'POST':'GET',action?{action,revision:data.revision,attempt_id:data.active?.id||'',...extra}:undefined);if(stamp!==generation||identity!==token)return false;data=value;owner=identity;status.textContent=action?'교육 기록을 저장했습니다.':'저장된 교육 경로입니다.';if(action==='start')listVisible=false;if(action==='finish')listVisible=true;render();if(action==='start'||action==='finish')window.cmaNavigation?.educationAction(action);return true;}
 catch(e){if(stamp===generation&&identity===token){failed=true;status.textContent=e.message+' 저장 상태를 다시 확인하세요.';}return false;}
 finally{if(stamp===generation){busy=false;controls();draw();}}}
function render(){body.replaceChildren();if(!data||!opened)return;const r=listVisible?null:data.active;
 if(listVisible&&data.active)btn(body,'저장된 교육 실습 이어하기',()=>window.cmaNavigation.go('learn/education/practice'));
 if(!data.can_start)make(body,'p','보관 한도입니다. 현재 시도 종료·기존 결과 조회·다른 학습 탐색은 가능합니다. 새 기록을 위해 기존 기록을 자동 삭제하지 않습니다.');
 if(!r){for(const c of data.catalog){const card=make(body,'article');make(card,'h3',c.title);make(card,'p',c.intro);const m=data.metrics[c.id];if(m)make(card,'p',`교육 완료 ${m.completed} · 시도 ${m.attempts} · 누적 도움 ${m.hints} · 다른 응답 ${m.misses}`);for(const [mode,label] of [['learn','설명 보며 학습'],['review','설명 가리고 복습']]){const b=btn(card,label,()=>request('start',{lesson_id:c.id,mode}));b.dataset.blocked=String(!data.can_start);}
 btn(card,'관련 기존 기초 보기',async()=>{if(window.cmaNavigation)window.cmaNavigation.go('learn/basics');else window.cmaAcademyNavigate?.('basics');const identity=token,stamp=generation;await window.cmaFoundations?.load();if(identity!==token||stamp!==generation||!$('learn').classList.contains('active'))return;$('foundationCourseList').open=true;const target=document.querySelector(`[data-course="${c.prerequisite}"]`);if(target){target.tabIndex=-1;target.focus();target.scrollIntoView({block:'start'});}});}}
 else{
 make(body,'h3',r.title);make(body,'p',`${r.mode==='review'?'복습':'학습'} · 관찰 ${r.index+1}/3 · 이번 도움 ${r.hints} · 다른 응답 ${r.misses}`);
 const m=data.metrics[r.lesson_id];make(body,'p',`레슨 누적 도움 ${m.hints} · 다른 응답 ${m.misses} · 완료 ${m.completed} (숙련 판정 아님)`);
 make(body,'p',r.outdated?'콘텐츠가 변경되었습니다. 기존 결과를 보관하고 새 버전을 선택하세요.':r.feedback);
 const layout=make(body,'div');layout.className='education-layout';make(layout,'div').id='educationBoard';$('educationBoard').className='board';const info=make(layout,'div');if(r.step.prior)make(info,'p',`상대 직전 수: ${r.step.prior.move.slice(0,2)} → ${r.step.prior.move.slice(2,4)} (${r.step.prior.san}) · 보드는 착수 후 위치입니다. 출발·도착 칸을 테두리로 표시합니다.`);make(info,'p',r.step.prompt);
 if(r.step.reason)make(info,'p',r.step.reason);
 if(r.phase==='playing'&&!r.outdated){
 if(!r.answered){for(const [value,label] of r.step.choices||[])btn(info,label,()=>request('answer',{answer:value}));
 if(r.step.kind==='move'){const list=make(info,'select');list.setAttribute('aria-label','교육 합법 착수 목록');for(const u of r.legal){const o=make(list,'option',u);o.value=u;}btn(info,'선택한 합법 수 두기',()=>request('answer',{answer:list.value}));}
 for(const u of r.step.examples)btn(info,'수업 예시 '+u,()=>request('answer',{answer:u}));
 btn(info,'설명 힌트 (도움 기록)',()=>request('hint'));}
 else btn(info,r.index===2?'비교 완료 기록':'이유 확인 · 다음 비교 위치',()=>request('next'));}
 btn(body,'보드 방향 바꾸기',()=>{flip=!flip;draw();});
 btn(body,r.phase==='complete'?'결과 보관 · 다시 선택':'현재 시도 기록하고 마치기',()=>request('finish'));
 const events=make(body,'details');make(events,'summary','이번 입력·도움 이력');for(const e of r.events)make(events,'p',`${e.step_id} · ${e.kind} · ${e.input||'설명 도움'}`);
 }
 if(!r||r.mode!=='review'||r.phase!=='playing'){const history=make(body,'details');make(history,'summary','보관한 교육 결과 '+data.history.length+'개');for(const row of [...data.history].reverse()){make(history,'p',`${row.title} · ${row.mode==='learn'?'학습':row.mode==='review'?'복습':'학습 방식 미기록'} · ${row.phase==='complete'?'완료':'중단'} · 도움 ${row.hints} · 다른 응답 ${row.misses}`);btn(history,'이 기록의 관찰·이유 보기',async()=>{const stamp=generation,identity=token;try{const v=await api('/education/history/'+row.id);if(stamp!==generation||identity!==token||!$('learn').classList.contains('active'))return;const out=make(history,'div');for(const s of v.snapshot.steps)make(out,'p',s.title+': '+s.reason);for(const e of v.events)make(out,'p',e.step_id+' · '+e.kind+' · '+e.input);}catch(e){if(stamp===generation&&identity===token&&$('learn').classList.contains('active'))status.textContent=e.message;}});}}
 const home=btn(body,'홈으로 돌아가기',()=>tab('home'));home.dataset.navigation='true';controls();draw();}
function draw(){const r=data?.active;if(!$('educationBoard')||!r)return;drawBoard('educationBoard',fromFen(r.fen),{flip,selected,opponent:r.step.prior?[r.step.prior.move.slice(0,2),r.step.prior.move.slice(2,4)]:[],targets:selected?r.legal.filter(u=>u.slice(0,2)===selected).map(u=>({to:u.slice(2,4)})):[],onClick:!busy&&!failed&&r.phase==='playing'&&!r.answered&&!r.outdated?click:undefined});if(selected)$('educationBoard').querySelector(`[aria-label^="${selected} "]`)?.focus({preventScroll:true});}
async function click(square){const r=data?.active;if(!r||busy||failed)return;if(r.step.kind==='square'){request('answer',{answer:square});return;}if(r.step.kind!=='move')return;
 const choices=r.legal.filter(u=>u.slice(0,2)===selected&&u.slice(2,4)===square);if(!choices.length){selected=r.legal.some(u=>u.slice(0,2)===square)?square:null;draw();return;}let move=choices[0];
 if(choices.length>1){const stamp=generation,identity=token;busy=true;controls();try{const suffix=await choosePromotion(selected,square,fromFen(r.fen)[selected],r.legal);if(!suffix||stamp!==generation||identity!==token||!$('learn').classList.contains('active'))return;move=choices.find(u=>u[4]===suffix);}finally{if(stamp===generation){busy=false;controls();draw();}}}if(move)request('answer',{answer:move});}
function clear(){data=null;owner=token;selected=null;body.replaceChildren();status.textContent='저장 상태를 확인하세요.';}
const previous=tab;tab=function(id){++generation;busy=false;if(owner!==token)clear();previous(id);if(id==='learn'&&opened)request();};
$('signout')?.addEventListener('click',()=>{++generation;busy=false;clear();});
window.cmaEducation={open(){if(window.cmaNavigation){window.cmaNavigation.education();return;}opened=true;tab('learn');host.scrollIntoView({block:'start'});},show(list){opened=true;listVisible=list;if(owner!==token||!data)return request();render();},hasActive:()=>owner===token&&!!data?.active};
const hub=$('academyHub');if(hub)btn(hub,'기초 적용 · 짧은 교육 경로',()=>window.cmaEducation.open());
})();
