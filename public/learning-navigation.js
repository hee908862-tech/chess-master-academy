/* UI routes only. No session identifiers or learning writes in navigation/history. */
(()=>{'use strict';
function install(){
const $=id=>document.getElementById(id),make=(p,t,text,cls)=>{const n=document.createElement(t);if(text)n.textContent=text;if(cls)n.className=cls;p.append(n);return n;};
const button=(p,id,text,fn)=>{const b=make(p,'button',text,'btn');b.type='button';b.id=id;b.onclick=fn;return b;};
const outer=new Set(['home','learn','diagnosis','assessment','training','play','puzzle','opening','review','profile','help','rookTrial']);
const topics=[['basics','기초 규칙','기물과 규칙부터'],['tactics','전술 과목','주제별 문제 연습'],['education','위협·계획·종반','짧은 적용 수업'],['training','맞춤 훈련','개념과 새 문제'],['puzzle','퍼즐','일반 연습·연속 도전'],['opening','오프닝','강의·내 레퍼토리']];
const valid=new Set([...outer,'learn/basics','learn/basics/practice','learn/tactics','learn/tactics/practice','learn/education','learn/education/practice','learn/resume']);
const normalize=s=>valid.has(s)?s:'home',base=tab;let route='',owner=token,serial=0,restoring=false;const memories=new Map();
const learn=$('learn'),root=$('v9LearnRoot'),hub=$('academyHub'),foundation=$('foundationAcademy'),tactics=$('academyTactics'),education=$('educationPaths'),resume=$('academyResume');
root.append(education);hub.replaceChildren();const hubTitle=make(hub,'h1','배우기');hubTitle.tabIndex=-1;make(hub,'p','배울 주제를 고르세요. 선택한 활동에 집중해서 연습합니다.');const grid=make(hub,'div',null,'feature-options');
for(const [id,title,desc]of topics)button(grid,'learn-choice-'+id,title+' · '+desc,()=>choose(id));
button(hub,'learn-saved','저장 활동 · 복습과 이어하기',()=>go('learn/resume'));
const nav=make(learn,'nav',null,'learning-route-nav');nav.setAttribute('aria-label','학습 위치와 돌아가기');learn.querySelector('.feature-toolbar').after(nav);
button(nav,'learn-hub-back','학습 선택으로',()=>go('learn'));const listBack=button(nav,'learn-list-back','과정 목록으로',()=>go(route.replace('/practice','')));const crumb=make(nav,'span');crumb.id='learning-location';
const learnLabel=learn.querySelector('.feature-toolbar span');if(learnLabel)learnLabel.textContent='배우기';$('foundationHeading').textContent='기초 규칙 · 과정 선택';$('academyTacticsTitle').textContent='전술 과목 · 선택';
// Same six topics and saved-activity entry in the existing disclosure; keep its lifecycle.
const menu=$('academyNavigationDialog');menu.querySelectorAll('[data-academy]').forEach(b=>b.remove());
for(const [id,title,desc] of [...topics,['resume','저장 활동','복습·이어하기'],['hub','배우기 전체','주제 선택']]){const b=button(menu,'learn-menu-'+id,title+' · '+desc,()=>{menu.close();choose(id);});b.dataset.academy=id;}
$('academyNavigationTitle').textContent='배우기';
const homeBasics=make($('home'),'section',null,'card home-basics');homeBasics.id='homeBasics';make(homeBasics,'h2','기초 배우기');make(homeBasics,'p','체스가 처음이라면 기물과 규칙부터. 저장된 단계가 있으면 이어갑니다.');button(homeBasics,'homeBasicsOpen','기초 배우기 · 시작/이어가기',()=>foundationEntry());$('journeyHome').before(homeBasics);$('foundationHome').hidden=true;
const homeStats=$('journeyActivity');if(homeStats)$('homeExplore').before(homeStats);
// Existing completed-course link now selects the foundation list, not a hidden anchor.
const basicsLink=[...resume.querySelectorAll('button')].find(b=>b.textContent.includes('기초 완료'));
if(basicsLink)basicsLink.onclick=()=>go('learn/basics');
function visible(node,on){node.hidden=!on;node.inert=!on;}
function remember(){if(!route)return;let id=document.activeElement?.id;if(!id){const card=document.activeElement?.closest('[data-course]');if(card){card.id='foundation-card-'+card.dataset.course;id=card.id;}}memories.set(route,{id,y:scrollY});}
function paint(){const [view,topic,mode]=route.split('/');const learning=view==='learn';document.body.classList.toggle('learning-practice',learning&&mode==='practice');nav.hidden=!learning||!topic;listBack.hidden=mode!=='practice';crumb.textContent='배우기'+(topic?' › '+(topics.find(x=>x[0]===topic)?.[1]||'저장 활동'):'')+(mode?' › 실습':'');
 for(const [node,key]of [[hub,undefined],[foundation,'basics'],[tactics,'tactics'],[education,'education'],[resume,'resume']])visible(node,learning&&topic===key);
 if(topic==='basics'){const active=window.cmaFoundations.state()?.active,practice=mode==='practice'&&!!active;visible($('foundationWorkspace'),practice);visible($('foundationPrimary'),!practice);visible($('foundationCourseList'),!practice);visible(foundation.querySelector('.foundation-header'),!practice);$('foundationCourseList').open=true;const state=window.cmaFoundations.status();visible($('foundationStatus'),!practice||state.busy||state.failed);visible($('foundationReload'),!practice||state.failed);}
 if(topic==='tactics'){tactics.open=true;const practice=mode==='practice'&&window.cmaTacticView.hasSelection();for(const node of tactics.children)visible(node,node===$('v9LearnMode')?practice:!practice);}
 // Guest first-entry/skip remain intact, with a direct foundation action alongside them.
 homeBasics.hidden=false;
}
function focusRoute(restore){const old=restore&&memories.get(route);if(old){const n=old.id&&$(old.id);if(n&&!n.closest('[hidden],[inert]')){n.tabIndex=n.tabIndex<0?-1:n.tabIndex;n.focus({preventScroll:true});}scrollTo({top:old.y,behavior:'instant'});return;}
 const [,topic,mode]=route.split('/');const n=route==='learn'?hubTitle:topic==='basics'?(mode==='practice'?$('foundationStepTitle'):$('foundationHeading')):topic==='tactics'?(mode==='practice'?$('v9CourseTitle'):$('academyTacticsTitle')):topic==='education'?education.querySelector('h2'):topic==='resume'?resume:$(route.split('/')[0]);if(n){n.tabIndex=-1;n.focus({preventScroll:true});}scrollTo({top:0,behavior:'instant'});}
function go(next,{replace=false,restore=true,focus=true,load=true}={}){next=normalize(next);const old=route,from=document.querySelector('.view.active')?.id,to=next.split('/')[0],accountChanged=owner!==token;if(accountChanged){owner=token;memories.clear();serial++;}if(old!==next&&!accountChanged)remember();route=next;const stamp=++serial;
 if(from!==to||accountChanged)base(to); // Do not run cancellation/load wrappers for an in-screen list/hub choice.
 if(!restoring){const hash='#'+next;if(location.hash!==hash)history[replace?'replaceState':'pushState']({cmaRoute:next},'',hash);}
 paint();if(focus&&old!==next)focusRoute(restore);
 if(load&&next.startsWith('learn/basics'))window.cmaFoundations.load().then(()=>{if(stamp!==serial||owner!==token||route!==next)return;paint();if(focus&&next.endsWith('/practice'))focusRoute(false);});
 if(load&&next.startsWith('learn/education'))window.cmaEducation.show(!next.endsWith('/practice'));
 if(load&&next==='learn/tactics/practice'&&!window.cmaTacticView.hasSelection())window.cmaTacticView.loadSaved().then(()=>{if(stamp===serial&&route===next)paint();});
 return next;
}
async function foundationEntry(){const account=token;go('learn/basics',{load:false,restore:false});const stamp=serial;await window.cmaFoundations.load();if(stamp!==serial||account!==token)return;if(window.cmaFoundations.state()?.active)go('learn/basics/practice',{load:false,restore:false});else{paint();focusRoute(false);}}
async function educationEntry(){const account=token;go('learn/education',{load:false});const stamp=serial;await window.cmaEducation.show(false);if(stamp!==serial||account!==token)return;if(window.cmaEducation.hasActive())go('learn/education/practice',{load:false,restore:false});}
function choose(id){if(id==='education')return educationEntry();if(id==='basics')return foundationEntry();go(id==='hub'?'learn':['training','puzzle','opening'].includes(id)?id:'learn/'+id);}
window.cmaNavigation={go,foundation:foundationEntry,education:educationEntry,refresh(){if(route.startsWith('learn/basics'))paint();},foundationLoaded(){queueMicrotask(()=>{if(route.startsWith('learn/basics'))paint();});},foundationAction(action,version){if(version!==serial)return;if((route==='learn'||route.startsWith('learn/basics'))&&['start','review','next'].includes(action))go('learn/basics/practice',{load:false,restore:false});},tacticSelected(){if(['learn','learn/resume','learn/tactics','learn/tactics/practice'].includes(route))go('learn/tactics/practice',{load:false,restore:false});},educationAction(action){if(route.startsWith('learn/education'))go(action==='finish'?'learn/education':'learn/education/practice',{load:false,restore:false});},current:()=>route,version:()=>serial};
window.cmaAcademyNavigate=choose;
tab=function(id){if(!outer.has(id))return;return go(id);};
window.addEventListener('popstate',()=>{restoring=true;go(normalize(location.hash.slice(1)),{restore:true});restoring=false;});
$('signout').addEventListener('click',()=>{memories.clear();serial++;});
const initial=normalize(location.hash.slice(1)||document.querySelector('.view.active')?.id||'home');go(initial,{replace:true,focus:initial!=='home',restore:false});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
})();
