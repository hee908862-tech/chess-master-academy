/* Presentation and read-only recommendations. Never grades, merges, or resets records. */
(()=>{'use strict';
const $=id=>document.getElementById(id),make=(p,t,text,id)=>{const e=document.createElement(t);if(text)e.textContent=text;if(id)e.id=id;p.append(e);return e;};
function fold(parent,id,label,nodes){const d=make(parent,'details',null,id);d.className='card flow-disclosure';make(d,'summary',label);for(const n of nodes)if(n)d.append(n);return d;}
function button(p,label,fn){const b=make(p,'button',label);b.className='btn';b.type='button';b.onclick=fn;return b;}
let stateOwner=null,observed={},last='',scheduled=false,installed=false,bootstrapOwner=null;
const routeFor=path=>path.startsWith('/foundations')?'learn':path.startsWith('/journey')?'diagnosis':path.startsWith('/learning')?'training':path.startsWith('/game')?'play':null;
function reset(){stateOwner=token;observed={};last='';}
function remember(route){if(!route||!observed.code)return;last=route;try{localStorage.setItem('cma_recent_activity_v1:'+observed.code,route);}catch(e){}}
const priorApi=api;api=async function(path,method,...args){const identity=token,r=await priorApi(path,method,...args);if(identity!==token)return r;if(stateOwner!==token)reset();
 if(path==='/me'){observed.code=r.code;try{last=localStorage.getItem('cma_recent_activity_v1:'+r.code)||'';}catch(e){}}
 if(path==='/foundations'||path==='/foundations/action')observed.foundation=r;
 if(path==='/journey')observed.journey=r;
 if(path==='/journey/start'||path==='/journey/action')observed.journey={...(observed.journey||{}),active:r.phase==='complete'?null:r,...(r.report?{latest:r.report}:{})};
 if(path==='/learning/dashboard')observed.learning=r;
 if(['/learning/start','/learning/action','/learning/resume'].includes(path))observed.learning={...(observed.learning||{}),active:r};
 if(path==='/game'||path==='/game/new'||path==='/game/move')observed.game=r;
 const route=routeFor(path),view=document.querySelector('.view.active')?.id;
 if(route&&route===view&&(method==='POST'||path==='/foundations'||path==='/journey'||path==='/learning/dashboard'||path==='/game'))remember(route);
 queue();return r;};
function queue(){if(installed&&!scheduled){scheduled=true;requestAnimationFrame(()=>{scheduled=false;render();});}}
function model(){if(observed.pending)return {label:'저장된 활동 확인 중…',detail:'기존 진행을 확인하고 있습니다.',reason:'조회 중에는 새 활동을 추천하지 않습니다.',run:()=>{},disabled:true,choices:{}};if(observed.failed)return {label:'저장된 활동 다시 확인',detail:'진행 정보를 모두 확인하지 못했습니다.',reason:'기존 기록은 바꾸지 않았습니다. 연결 후 다시 확인하세요.',run:()=>bootstrap(true),choices:{}};const f=observed.foundation,a=f?.active,j=observed.journey,l=observed.learning,g=observed.game;
 const choices={};
 if(a&&(!a.done||!a.solved||a.step+1<a.total))choices.learn={label:'기초 이어하기',detail:`${a.course_title} · ${a.step+1}/${a.total}단계 · ${a.title}`,run:()=>window.cmaNavigation.foundationStart()};
 if(j?.active)choices.diagnosis={label:'진단 이어하기',detail:`${j.active.index+1}/${j.active.total}문항 · 시작한 진단의 수순과 응답을 이어갑니다.`,run:()=>tab('diagnosis')};
 if(l?.active&&!l.active.done)choices.training={label:'훈련 이어하기',detail:`${l.active.category||'주제 비공개'} · ${l.active.assessment_scope==='first_move'?'첫 수 판단':'진행 중 수순'} · ${l.active.turns||0}수 진행`,run:()=>tab('training')};
 if(g?.board&&!g.board.is_over&&!g.finished)choices.play={label:'대국 이어하기',detail:`${g.board.turn==='black'?'흑':'백'} 차례 · 저장된 대국`,run:()=>tab('play')};
 const id=choices[last]?last:Object.keys(choices)[0];
 if(id)return {...choices[id],reason:id===last?'이 브라우저에서 최근 열어 둔 진행 활동입니다.':'완료하지 않은 저장 활동부터 이어갑니다.',active:true,choices};
 if(j?.latest?.diagnostic_scope){const report=j.latest,task=report.scoped_training?.tasks?.[0];return task?{label:task.label+' · 새 문제로 연습',detail:task.reason,reason:'이번 범위의 진단 결과와 같은 추천입니다. 종합 진단 과제와 별도로 진행합니다.',run:()=>window.learningScoped(report.id,task.item_id),active:false,choices}:{label:'같은 범위 추가 확인 선택',detail:report.scoped_training?.message||'추천할 수행 근거가 충분하지 않습니다.',reason:'미응답·미확정을 약점으로 단정하지 않습니다.',run:()=>{tab('diagnosis');window.cmaDiagnosticChoice.select(report.diagnostic_scope);},active:false,choices};}
 if(j?.latest)return {label:$('journeyHomeOpen').textContent,detail:$('journeyHomeStatus').textContent,reason:'진단 결과의 수행 근거와 같은 추천입니다. 미확정 응답은 약점으로 단정하지 않습니다.',run:()=>$('journeyHomeOpen').click(),active:false,choices};
 if(f?.total>0&&f.completed===f.total)return {label:'기초 복습하기',detail:'기초 과정을 모두 확인했습니다. 원하는 과정을 골라 복습하세요.',reason:'완료 기록에 따른 선택이며 실력 상승을 추정하지 않습니다.',run:()=>window.cmaNavigation.foundation(),active:false,choices};
 if(f?.completed>0&&f.completed<f.total)return {label:'다음 기초 이어하기',detail:`${f.completed}/${f.total}과정 완료 · 다음 권장 과정부터 이어갑니다.`,reason:'완료한 과정은 보존하고 아직 배우지 않은 기초를 이어갑니다.',run:()=>window.cmaNavigation.foundationStart(),active:false,choices};
 return {label:'기초부터 배우기',detail:'기물과 규칙을 한 단계씩 직접 연습합니다.',reason:'아직 추천할 수행 근거가 충분하지 않습니다. 익숙한 분은 원하는 활동을 고르세요.',run:()=>window.cmaGuestAccess.enter('basics'),active:false,choices};}
const cards=[];
function addRecommendation(parent,id){const card=make(parent,'section',null,id);card.className='card flow-recommendation';make(card,'h2','지금 할 일');const detail=make(card,'p');detail.className='flow-next-detail';const reason=make(card,'p');reason.className='subtle';const b=button(card,'저장된 활동 확인 중',()=>{});const more=make(card,'details');make(more,'summary','다른 진행 활동');const list=make(more,'div');list.className='btn-row';cards.push({card,detail,reason,b,more,list});return card;}
async function bootstrap(force=false){if(!token||(!force&&bootstrapOwner===token))return;const identity=token;bootstrapOwner=identity;observed.pending=true;observed.failed=false;queue();try{await api('/me');if(identity!==token)return;await Promise.all([api('/foundations'),api('/journey'),api('/learning/dashboard'),api('/game')]);}catch(e){if(identity===token)observed.failed=true;}finally{if(identity===token){observed.pending=false;queue();}}}
function render(){if(stateOwner!==token)reset();if(token&&bootstrapOwner!==token)bootstrap();const m=model();for(const c of cards){c.card.hidden=!token||(c.card.id==='resultNextAction'&&!$('journeyTask').hidden);c.detail.textContent=m.detail;c.reason.textContent=m.reason;c.b.textContent=m.label;c.b.disabled=!!m.disabled;c.b.onclick=m.run;c.list.replaceChildren();c.more.hidden=Object.keys(m.choices).length<2;for(const choice of Object.values(m.choices))button(c.list,choice.label+' · '+choice.detail,choice.run);}
 $('home').classList.toggle('flow-returning',!!token);$('guestAccess').hidden=!!token;
 const saved=$('learningSaved');if(saved)saved.hidden=!saved.querySelector('button');
 const summary=$('focusOpeningSelection')?.querySelector('summary');if(summary){const course=$('studyCourse'),mode=$('studyMode');summary.textContent=`${course.selectedOptions[0]?.textContent||'강의 선택'} · ${mode.value==='recall'?'혼자 복습하기':'설명 보며 배우기'} · 설정 변경`;}
}
function training(t){const brief=$('trainingTaskBrief');if(!brief)return;brief.hidden=!t;
 if(!t)return;const situation=t.mode?.startsWith('situation');
 const range=situation?'상황 연습 · 제시한 수와 평가 유지 조건까지':t.assessment_scope==='first_move'?'첫 수 1개만 판단 · 전체 수순 평가 아님':'전체 수순 · 문제 완료 표시까지 (정답 길이는 미리 알려주지 않음)';
 brief.querySelector('strong').textContent=range;
 brief.querySelector('p').textContent=t.done?'이번 시도가 끝났습니다. 아래 결과를 확인하고 같은 위치 복습 또는 다음 문제를 고르세요.':situation?t.goal:'지금 할 일: 내 수를 직접 두세요. '+(t.assessment_scope==='first_move'?'성공 조건: 첫 수가 기준을 충족하면 이 활동이 끝납니다.':'성공 조건: 상대 응수 뒤에도 끝까지 직접 두세요. 일부 정답은 완료가 아닙니다.');
}
function install(){
 const home=$('home');const start=$('guestAccess'),actions=start.querySelector('.btn-row');
 const primary=actions.firstElementChild;primary.id='flowBasicsStart';primary.classList.add('primary');
 const choose=fold(start,'flowActivityChoices','원하는 활동 고르기',[]);const chooseActions=make(choose,'div');chooseActions.className='btn-row';for(const b of [...actions.children].slice(1))chooseActions.append(b);
 button(chooseActions,'기초 과정 자유롭게 고르기',async()=>{await window.cmaGuestAccess.enter('learn');window.cmaNavigation.go('learn/basics');});
 start.append(start.querySelector('.subtle'));home.prepend(start);
 const free=fold(home,'flowFreeExamples','저장 없이 잠깐 체험하기',[$('firstEntry'),$('academyTry')]);
 const archive=fold(home,'flowSavedActivities','활동별 진행 · 기록 · 다른 학습',[$('homeBasics'),$('journeyHome'),$('entryReturn'),$('entrySavedBasics'),...home.querySelectorAll(':scope > .learning-home'),$('journeyActivity'),$('homeExplore')]);
 // Existing controls stay reachable, including account-specific legacy recommendations.
 const next=addRecommendation(home,'homeNextAction');home.prepend(next);home.prepend(home.querySelector('.feature-toolbar'),next,start);
 addRecommendation($('profileInformation'),'profileNextAction');$('profileInformation').prepend($('profileNextAction'));
 const result=addRecommendation($('diagnosis'),'resultNextAction');$('journeyResults').before(result);
 button(start,'기초 과정 목록',async()=>{await window.cmaGuestAccess.enter('learn');window.cmaNavigation.go('learn/basics');});
 const oldText=$('entryChoices').querySelector('p');if(oldText)oldText.textContent='이 보조 경로의 체험은 기록을 저장하지 않습니다. 저장되는 학습은 홈의 기초·활동 선택을 이용하세요.';
 // Library selection first; optional metrics and old paths below the purposeful actions.
 const setup=$('learningSetup'),records=fold($('trainingLibrary'),'trainingRecords','학습 기록 · 측정 기준 · 이전 경로',[$('learningRoute'),setup.querySelector('details'),$('learningCards').closest('details'),$('learningSkills').closest('details'),$('learningAttempts').closest('details')]);
 const guide=make(setup,'p','새 문제는 첫 수 판단 연습입니다. 진단에서 연결한 훈련은 해당 수순의 완료 조건을 따릅니다.');setup.prepend(guide);
 const review=button(setup,'복습 · 저장된 위치',()=>{records.open=true;$('learningCards').closest('details').open=true;$('learningCards').scrollIntoView({block:'start'});});review.id='flowTrainingReview';
 const brief=make($('trainingCore'),'section',null,'trainingTaskBrief');brief.className='notice';make(brief,'strong');make(brief,'p');$('trainingCore').prepend(brief);
 // Keep the route disclosure in the library; its full controls still work.

 const opening=$('openingStudy'),picker=$('focusOpeningSelection');picker.open=false;
 const primer=fold(opening,'openingHelp','처음 배우는 오프닝 · 추천 경로와 범위',[$('beginnerOpeningPath'),...opening.querySelectorAll(':scope > p:not(#studyContext):not(#studySaveStatus)')]);
 const layout=opening.querySelector('.study-layout');opening.append(primer);layout.before(picker);if($('studyContext'))picker.append($('studyContext'));const jumps=$('opening').querySelector('.feature-jumps');if(jumps)opening.append(jumps);
 const mode=$('studyMode');mode.options[0].textContent='설명 보며 배우기';mode.options[1].textContent='혼자 복습하기 · 해설 가리기';
 const toggle=make(opening,'div',null,'openingModeActions');toggle.className='btn-row';picker.before(toggle);
 for(const[value,label]of [['explore','설명 보며 배우기'],['recall','혼자 복습하기']])button(toggle,label,()=>{mode.value=value;mode.dispatchEvent(new Event('change',{bubbles:true}));queue();});
 opening.addEventListener('change',queue);
 // Same recommendation model on home, account overview and diagnosis results.
 new MutationObserver(queue).observe($('journeyHomeStatus'),{childList:true,subtree:true,characterData:true});
 const oldTab=tab;tab=function(...args){const r=oldTab(...args);queue();return r;};
 window.addEventListener('storage',e=>{if(e.key?.startsWith('cma_recent_activity_v1:')){last=e.newValue||'';queue();}});
 window.cmaActivityFlow={training,model:()=>model(),refresh:queue};installed=true;render();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
})();
