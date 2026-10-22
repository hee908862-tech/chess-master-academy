/* One choice surface; server-owned scope, grading and old sessions are unchanged. */
(()=>{'use strict';
const $=id=>document.getElementById(id),make=(p,t,text)=>{const e=document.createElement(t);if(text)e.textContent=text;p.append(e);return e;};
const host=make($('diagnosis'),'details');host.className='card';host.id='diagnosticBlueprint';host.open=true;
make(host,'summary','진단 선택 · 목적과 범위 비교');$('journeyIntro').before(host);
const novice=make(host,'p','기물 움직임이나 규칙이 낯설다면 진단보다 기초 실습을 먼저 권합니다.');
const basics=make(novice,'button','기초부터 배우기');basics.className='btn';basics.onclick=()=>window.cmaGuestAccess.enter('basics');
const comparison=make(host,'div');comparison.className='diagnostic-options';comparison.setAttribute('aria-label','진단 목적 비교');
const level=make(host,'select');level.className='field';level.setAttribute('aria-label','진단 범위');
for(const[id,label]of [['balanced','종합 진단'],['domain','분야별 진단'],['subskill','분야별 부분 진단']]){const o=make(level,'option',label);o.value=id;}
const area=make(host,'select');area.className='field';area.setAttribute('aria-label','진단 분야');
const topic=make(host,'select');topic.className='field';topic.setAttribute('aria-label','진단 하위 기술');
const description=make(host,'p','구성을 확인하고 있습니다…');description.id='diagnosticChoiceDescription';description.setAttribute('role','status');
const begin=make(host,'button','선택한 진단 시작');begin.id='diagnosticBegin';begin.className='btn primary';begin.disabled=true;
const limits=make(host,'details');make(limits,'summary','점수 의미 · 측정 한계');const policy=make(limits,'p');
const old=make($('diagnosis'),'details');old.className='card';old.id='diagnosticOther';make(old,'summary','이전 방식 · 입문 관찰 · 간이 진단');host.after(old);
old.append($('journeyIntro'));$('journeyIntro').querySelector('h3').textContent='기존 방식으로 새로 시작하기';
$('journeyIntro').querySelector('p').textContent='입문 관찰: 최대 6문항, 예상 10–20분, 기초 수순 관찰(종합 점수와 별도). 간이 진단: 12문항, 예상 15–30분, 기초·응용을 짧게 확인합니다. 시간은 추정이며 제한이 아닙니다. 기존 진행과 완료 기록은 그대로 이어볼 수 있습니다.';
$('journeyIntro').querySelector('.subtle').textContent='기존 채점·측정 범위를 그대로 사용합니다. 다른 구성의 점수와 직접 비교하지 마세요.';
const resume=make($('diagnosis'),'section');resume.id='diagnosticResume';resume.className='card';host.before(resume);
make(resume,'h3','진행 중인 진단');const resumeText=make(resume,'p');resume.append($('journeyResume'));old.append($('journeyIntro').querySelector('.btn-row'),$('journeyEntryOffer'));
let catalog=null,loading=false,inFlight=false;
const purposes={balanced:['여러 분야를 함께 확인','종합 내부 지표와 분야별 수행'],domain:['한 분야를 집중 확인','선택 분야 지표 · 종합 점수 없음'],subskill:['한 기술을 짧게 확인','선택 기술의 수행 · 종합 점수 없음']};
function render(){if(!catalog)return;const spec=catalog.levels.find(s=>s.id===level.value),a=catalog.areas.find(a=>a.id===area.value);area.hidden=level.value==='balanced';topic.hidden=level.value!=='subskill';description.textContent=`${spec.label} · ${spec.questions}문항 · 예상 ${spec.minutes.join('–')}분 · ${purposes[spec.id][1]}. 기초 ${spec.bands[0]} / 응용 ${spec.bands[1]}문항의 전체 수순을 끝까지 풉니다.`;
 begin.disabled=inFlight||!token||!$('journeyTask').hidden||window.cmaJourney.status().busy||window.cmaJourney.status().needsRefresh||(level.value==='subskill'&&!a?.topics.find(t=>t.id===topic.value)?.available);
 if(!token)description.textContent+=' 먼저 홈에서 로그인 없이 학습을 시작하거나 계정을 연결하세요.';
}
function topics(){topic.replaceChildren();for(const t of catalog?.areas.find(a=>a.id===area.value)?.topics||[]){const o=make(topic,'option',t.label+(t.available?'':' · 자료 부족'));o.value=t.id;o.disabled=!t.available;}const available=[...topic.options].find(o=>!o.disabled);if(available)topic.value=available.value;render();}
async function load(){if(loading||catalog)return;loading=true;try{catalog=await api('/journey/blueprint');for(const spec of catalog.levels){const card=make(comparison,'article');make(card,'h3',spec.label);make(card,'p',purposes[spec.id][0]);make(card,'p',`${spec.questions}문항 · 예상 ${spec.minutes.join('–')}분`);make(card,'p',purposes[spec.id][1]);}
 for(const a of catalog.areas.filter(a=>a.measured)){const o=make(area,'option',a.label);o.value=a.id;}policy.textContent=catalog.scoring+' '+catalog.limits;topics();}catch(e){description.textContent=e.message+' 진단 선택을 닫았다 다시 열면 재시도합니다.';}finally{loading=false;}}
function sync(){const active=!$('journeyTask').hidden;resume.hidden=!active;resumeText.textContent=active?`${$('journeyProgress').textContent} · 저장된 수순을 이어갑니다. 새 구성은 이 진단을 마친 뒤 선택하세요.`:'';if(active)host.open=false;render();}
host.addEventListener('toggle',()=>{if(host.open)load();});level.onchange=render;area.onchange=topics;topic.onchange=render;
begin.onclick=async()=>{if(begin.disabled||inFlight)return;inFlight=true;render();try{await window.cmaJourney.startScoped(level.value,level.value==='balanced'?undefined:area.value,level.value==='subskill'?topic.value:undefined);}finally{inFlight=false;sync();}};
new MutationObserver(sync).observe($('journeyTask'),{attributes:true,attributeFilter:['hidden']});
new MutationObserver(render).observe($('journeyStart'),{attributes:true,attributeFilter:['disabled']});
window.cmaDiagnosticChoice={async select(scope){await load();if(!catalog)return;level.value=scope.level;if(scope.competency)area.value=scope.competency;topics();if(scope.topic)topic.value=scope.topic;render();this.open();},open(){host.open=true;host.scrollIntoView({block:'start'});level.focus({preventScroll:true});},legacy(){old.open=true;}};load();sync();
})();
