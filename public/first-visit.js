/* Ephemeral rule demonstration. No trial moves, score or completion are persisted. */
(()=>{'use strict';
const $=id=>document.getElementById(id),make=(p,t,text,cls)=>{const n=document.createElement(t);if(text)n.textContent=text;if(cls)n.className=cls;p.append(n);return n;};
const button=(p,id,text,fn)=>{const b=make(p,'button',text,'btn');b.id=id;b.type='button';b.onclick=fn;return b;};
let selected=false,done=false,intent=null,generation=0,authBusy=false,handoff=null;
let explored=false;try{explored=localStorage.getItem('cma_entry_preference_v1')==='explore';}catch(e){}
const home=$('home'),entry=make(home,'section',null,'card first-entry');entry.id='firstEntry';home.querySelector('.feature-toolbar').after(entry);
make(entry,'h1','어디서 시작할까요?');make(entry,'p','기물을 처음 움직여 보거나, 원하는 체스 활동을 바로 고르세요.');
const start=button(entry,'firstTry','체스가 처음이에요 · 말 움직여 보기',()=>openTrial());start.classList.add('primary');
button(entry,'firstSkip','체스를 둘 줄 알아요 · 건너뛰기',()=>explore());
const routes=make(entry,'section');routes.id='entryChoices';const routeTitle=make(routes,'h2','원하는 활동 선택');routeTitle.tabIndex=-1;
for(const [id,label] of [['diagnosis','실력 진단 · 나에게 맞는 연습 찾기'],['training','훈련 · 개념과 새 문제 연습'],['play','대국 · AI와 직접 두기'],['learn','배우기 · 기초와 오프닝 찾기']])button(routes,'entry-'+id,label,()=>tab(id));
make(routes,'p','체스를 둘 줄 안다면 실력 진단부터 추천해요. 기록을 저장하는 기능은 로그인 후 이용합니다.','subtle');
make(entry,'p','로그인 없이 한 수만 체험해요. 기록에는 남지 않아요.','subtle');const storage=make(entry,'details');make(storage,'summary','체험과 설정 저장 안내');make(storage,'p','체험 착수는 저장하지 않습니다. 건너뛰기를 선택하면 이 브라우저에 활동 선택 화면 선호만 저장하며 계정이나 완료 기록과 연결하지 않습니다.','subtle');
const trial=make(document.querySelector('.main'),'section',null,'view');trial.id='rookTrial';trial.setAttribute('aria-labelledby','trialTitle');
const bar=make(trial,'header',null,'feature-toolbar');make(bar,'h2','룩 하나 움직여 보기').id='trialTitle';button(bar,'trialExit','나가기 · 홈',()=>leaveTrial(false));
button(trial,'trialSkip','체스를 둘 줄 알아요 · 건너뛰기',()=>leaveTrial(true));
const instruction=make(trial,'p','아래 흰 룩을 누르세요.');instruction.id='trialInstruction';instruction.setAttribute('role','status');
const board=make(trial,'div',null,'board');board.id='trialBoard';board.setAttribute('aria-label','저장하지 않는 룩 체험 체스판');
const feedback=make(trial,'p',null,'notice');feedback.id='trialFeedback';feedback.setAttribute('role','status');
const next=button(trial,'trialContinue','계속 배우기 · 로그인하고 기초 시작',()=>continueLearning());next.hidden=true;
button(trial,'trialAgain','처음부터 다시 해보기',()=>openTrial());
make(trial,'p','룩은 가로·세로로 움직입니다. 이번에는 a1 → a4만 연습해요. 키보드는 방향키로 칸을 이동하고 Enter로 선택하세요. 이 체험은 점수·수료·독립 숙련 기록이 아닙니다.','subtle');
const pending=make($('profile'),'section',null,'notice');pending.id='entryLoginNotice';pending.hidden=true;const pendingText=make(pending,'p');button(pending,'entryLoginCancel','로그인 연결 취소 · 홈',()=>{cancelIntent();tab('home');});const accountCard=$('codeField').closest('.card');accountCard.classList.add('entry-auth-card');accountCard.parentElement.classList.add('entry-auth-layout');accountCard.querySelector('.auth-grid').before(pending);$('codeField').setAttribute('aria-label','개인 코드');$('pinField').setAttribute('aria-label','PIN 또는 비밀번호');
const result=make(home,'section',null,'card');result.id='entryReturn';result.hidden=true;const resultText=make(result,'p');button(result,'entryReturnBasics','기초 시작 / 이어하기',()=>window.cmaFoundations.openRecommended());button(result,'entryReturnExplore','다른 활동 고르기',()=>{$('homeExplore').open=true;$('homeExplore').scrollIntoView({block:'start'});});entry.after(result);
function preferExplore(){explored=true;try{localStorage.setItem('cma_entry_preference_v1','explore');}catch(e){}}
function sync(){const active=document.querySelector('.view.active')?.id;document.body.classList.toggle('entry-home',active==='home');const primary=['learn','training','puzzle','opening'].includes(active)?'learn':active==='review'?'profile':active==='assessment'?'diagnosis':active;for(const b of document.querySelectorAll('.mobile-nav > [data-tab],.nav > [data-tab]')){const current=b.dataset.tab===primary;b.classList.toggle('active',current);if(current)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');}document.body.classList.toggle('entry-login',!!intent);document.body.classList.toggle('entry-guest',!token);document.body.classList.toggle('entry-trial',document.querySelector('.view.active')?.id==='rookTrial');entry.hidden=!!token;routes.hidden=!explored;start.textContent=explored?'말 움직이기 체험 다시 보기':'체스가 처음이에요 · 말 움직여 보기';pending.hidden=!intent;for(const id of ['signup','signin'])$(id).disabled=authBusy;}
function explore(){preferExplore();sync();routeTitle.focus();routes.scrollIntoView({block:'nearest'});}
function paint(focus){const pieces=fromFen('7k/8/8/8/8/8/8/R5K1 w - - 0 1');if(done){delete pieces.a1;pieces.a4='R';}
 drawBoard('trialBoard',pieces,{hint:!selected&&!done?['a1']:[],selected:selected?'a1':null,targets:selected?[{to:'a4'}]:[],onClick:s=>{if(done)return;if(s==='a1'){selected=!selected;instruction.textContent=selected?'같은 세로줄의 표시된 a4 칸을 누르세요.':'흰 룩 a1을 먼저 누르세요.';paint(s);return;}if(selected&&s==='a4'){done=true;selected=false;instruction.textContent='룩을 세로로 움직였어요!';feedback.textContent='a1에서 a4까지 빈 칸을 따라 이동했어요. 계속 배우면 다른 기물도 직접 움직일 수 있어요.';next.hidden=false;paint(s);return;}feedback.textContent=selected?'이번에는 표시된 a4 칸으로 옮겨 보세요. 다른 수를 실력 오답으로 기록하지 않습니다.':'먼저 흰 룩 a1을 눌러 주세요.';}});
 for(const b of board.querySelectorAll('.sq'))b.tabIndex=b.getAttribute('aria-label').startsWith((focus||(done?'a4':'a1'))+' ')?0:-1;
 if(focus)board.querySelector(`[aria-label^="${focus} "]`)?.focus({preventScroll:true});}
board.addEventListener('keydown',e=>{const delta={ArrowUp:[0,1],ArrowDown:[0,-1],ArrowLeft:[-1,0],ArrowRight:[1,0]}[e.key];if(!delta||!e.target.matches('.sq'))return;e.preventDefault();const sq=e.target.getAttribute('aria-label').slice(0,2),f=FILES.indexOf(sq[0])+delta[0],r=Number(sq[1])+delta[1];if(f<0||f>7||r<1||r>8)return;const target=board.querySelector(`[aria-label^="${FILES[f]}${r} "]`);e.target.tabIndex=-1;target.tabIndex=0;target.focus({preventScroll:true});});
function openTrial(){cancelIntent();selected=false;done=false;next.hidden=true;feedback.textContent='로그인 없이 체험합니다. 착수는 이 화면을 나가면 사라집니다.';instruction.textContent='왼쪽 아래 흰 룩을 누르세요. 다음에는 표시된 칸으로 옮겨요.';tab('rookTrial');paint('a1');}
function leaveTrial(skip){selected=false;done=false;next.hidden=true;board.replaceChildren();tab('home');if(skip)explore();else start.focus();}
function cancelIntent(){generation++;authBusy=false;handoff=null;intent=null;pending.hidden=true;window.cmaCancelAuth?.();}
function continueLearning(){if(intent)return;if(token){tab('home');result.hidden=false;resultText.textContent='저장된 활동을 먼저 확인하세요. 체험 결과는 기존 학습에 합산하지 않습니다.';return;}
 intent={generation:++generation};pendingText.textContent='로그인하거나 새 계정을 만들면 기초 학습으로 연결합니다. 체험 성공은 수료로 옮기지 않습니다.';loginDestination='home';tab('profile');sync();pending.scrollIntoView({block:'start'});$('codeField').focus({preventScroll:true});}
const previousTab=tab;tab=function(id){const old=document.querySelector('.view.active')?.id;if(handoff&&id!=='learn'&&old!==id)cancelIntent();if(intent&&(id!=='profile'||token)&&!window.cmaAuthNavigating)cancelIntent();if(old==='rookTrial'&&id!=='rookTrial'){selected=false;done=false;board.replaceChildren();}previousTab(id);sync();};
const previousAuth=auth;auth=async function(mode){if(authBusy)return;const captured=intent,stamp=generation,prior=token;authBusy=true;if(captured)loginDestination=mode==='signup'?'learn':'home';notice('accountStatus','계정을 확인하고 있습니다. 연결을 취소해도 기존 기록은 바뀌지 않습니다.');sync();try{await previousAuth(mode);if(!captured||intent!==captured||stamp!==generation||!token||token===prior)return;const account=token;intent=null;pending.hidden=true;preferExplore();sync();if(mode==='signup'){
 result.hidden=true;handoff={stamp,account};await window.cmaFoundations.startFirstIfEmpty(()=>generation===stamp&&token===account&&document.querySelector('.view.active')?.id==='learn');
 }else{tab('home');if(generation!==stamp||token!==account)return;result.hidden=false;resultText.textContent='로그인한 계정의 저장된 활동을 먼저 확인하세요. 기존 진행은 바꾸지 않았습니다. 기초 또는 다른 활동을 선택할 수 있어요.';result.tabIndex=-1;result.focus({preventScroll:true});}
 }finally{if(handoff?.stamp===stamp)handoff=null;if(stamp===generation)authBusy=false;sync();}};
$('signout').addEventListener('click',()=>{cancelIntent();result.hidden=true;});
// Five primary destinations; keep existing secondary routes and disclosure handlers.
const labels={home:'홈',learn:'배우기',diagnosis:'실력 진단',play:'대국',profile:'내 기록'};
const nav=document.querySelector('.nav'),extra=document.createElement('details');extra.id='navigationTools';make(extra,'summary','다른 학습 도구 · 도움말');
for(const b of [...nav.children])if(b.dataset.tab&&!labels[b.dataset.tab])extra.append(b);
for(const id of Object.keys(labels)){const b=nav.querySelector(`[data-tab="${id}"]`);if(b){b.textContent=labels[id];nav.append(b);}}
nav.append(extra);$('moreNavigation').textContent='기능 전체 · 도움말';$('profile').querySelector('.feature-toolbar').append($('moreNavigation'));
$('homeExplore').prepend($('startingLevelInvitation'));$('journeyHome').querySelector('h1').nextElementSibling.hidden=true;$('journeyHome').querySelector('h1').textContent='지금 이어갈 활동';$('journeyHome').querySelector('.tag').textContent='저장된 진행과 다음 학습';
const savedBasics=make(home,'section',null,'card');savedBasics.id='entrySavedBasics';savedBasics.hidden=true;const basicsText=make(savedBasics,'p');button(savedBasics,'entryResumeBasics','기초 실습 이어하기',()=>window.cmaFoundations.openRecommended());$('journeyHome').after(savedBasics);
const priorFoundation=window.cmaHomeFoundation;window.cmaHomeFoundation=d=>{priorFoundation?.(d);savedBasics.hidden=!token||!d?.active||d.active.done;if(!savedBasics.hidden)basicsText.textContent=`기초 · ${d.active.course_title} · ${d.active.step+1}/${d.active.total}단계 · ${d.active.title}`;};
const activity=$('journeyActivity');if(activity)$('journeyHome').after(activity);
button($('homeExplore'),'replayTrial','저장 없이 말 움직이기 체험',()=>openTrial());
button($('help'),'helpTrial','말 움직이기 체험 다시 보기',()=>openTrial());
// Account banners remain available in account/help screens, without blocking first action.
sync();window.cmaEntry={openTrial,cancel:cancelIntent};
})();
