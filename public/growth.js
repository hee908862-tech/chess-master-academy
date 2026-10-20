/* User-facing progress; the server owns scores, task credit and unlock decisions. */
(()=>{'use strict';
const node=(parent,tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;parent.append(e);return e;};
const button=(parent,label,fn)=>{const b=node(parent,'button',label,'btn');b.type='button';b.onclick=fn;return b;};
const date=value=>{const d=new Date(value);return isNaN(d)?'날짜 미기록':d.toLocaleDateString('ko-KR');};
const labels={mate:'메이트',calculation:'이어지는 수 읽기',capture:'포획과 교환',defense:'위협에 대응',promotion:'승격',endgame:'종반 전술',strategy:'전략과 계획'};
window.growthReport=(host,report,cycle,train,recheck,additional,readOnly=false)=>{
 const intro=node(host,'section',null,'card growth-intro');node(intro,'span','나의 분야별 실력','tag');node(intro,'h2','잘한 부분을 살리고, 다음 수를 연습해요');
 node(intro,'p',report.insights?.message||'이번에 관찰한 수행을 확인하세요.');
 const strengths=report.insights?.strengths||[],priorities=report.insights?.priorities||[];
 const insights=node(intro,'div',null,'growth-insights');
 for(const [title,list,empty] of [['잘한 부분',strengths,'아직 완주한 수순이 적어요. 첫 수를 찾은 경험부터 쌓아 봐요.'],['먼저 연습할 부분',priorities,'뚜렷한 차이보다 고르게 확인할 부분이 보여요. 추천 과제로 함께 연습해요.']]){const box=node(insights,'div');node(box,'h3',title);if(!list.length)node(box,'p',empty);for(const a of list.slice(0,2)){node(box,'strong',labels[a.id]||a.label);node(box,'p',a.reason.split('。')[0].split('. ')[0]);}}
 const abilities=node(host,'section',null,'card');node(abilities,'h3','분야별 수행 지표');node(abilities,'p','기초·응용 문제에서 직접 이어 둔 수를 0–100으로 나타냈어요. 실전 레이팅이 아니며, 작은 변화는 다음 진단에서도 확인해 보세요.','subtle');
 const grid=node(abilities,'div',null,'ability-grid');
 for(const area of report.areas||[]){const card=node(grid,'article',null,'ability-card'),p=area.performance||{};node(card,'h4',labels[area.id]||area.label);node(card,'strong',p.score==null?(area.id==='strategy'?'미측정':(p.observed||area.unverified||area.equivalent||area.partial||area.first_success)?'추가 확인 필요':'아직 응답 없음'):`${p.score} / 100`,'ability-score');const meter=node(card,'div',null,'ability-meter');meter.setAttribute('aria-hidden','true');if(p.score!=null){const fill=node(meter,'span');fill.style.width=p.score+'%';}node(card,'p',area.observation);node(card,'small',p.score==null?(area.id==='strategy'?'검증된 전략 과제가 준비되기 전까지 점수를 표시하지 않습니다.':`점수는 기초·응용 양쪽 관찰이 필요해요. 기초 ${p.band_counts?.[0]||0}개, 응용 ${p.band_counts?.[1]||0}개 확인. 각 난도 2개씩 확인하면 성장 비교 조건을 충족해요. 판단 보류와 건너뛰기는 0점이 아닙니다.`):`${p.observed}문제 관찰 · ${p.comparable?'균형 진단 조건 충족':'간이·부분 관찰'} · ${p.confidence}`);if(p.range){const detail=node(card,'details');node(detail,'summary','점수 해석');node(detail,'small',`불확실성 범위 ${p.range[0]}–${p.range[1]} · 표본이 적어 넓게 표시돼요. 검증된 실력 범위가 아닌 문제 표본에 따른 참고 범위입니다.`);}if(!readOnly&&area.id!=='strategy')button(card,'이 분야 더 확인하기',()=>additional(area.id));}
 if(readOnly)return;
 const plan=node(host,'section',null,'card growth-plan');node(plan,'h3','다음 진단까지, 추천 훈련 5개');
 const current=cycle?.report_id===report.id?cycle:null;
 node(plan,'p',current?.message||'이전 진단의 추천 목록입니다. 최신 결과에서 현재 훈련을 시작하세요.','cycle-message');
 const progress=node(plan,'progress');progress.max=5;progress.value=current?.completed||0;progress.setAttribute('aria-label',`추천 훈련 ${progress.value}/5 완료`);
 node(plan,'p',`${current?.completed||0} / 5 완료 · 원본 연습 2개와 새 적용 3개`);
 node(plan,'p','힌트를 보거나 답안을 살펴봐도 괜찮아요. 실제로 수순을 끝까지 두면 한 과제 완료예요. 같은 과제를 반복해도 횟수는 늘지 않습니다.','subtle');
 for(const task of current?.tasks||report.training_plan||[]){const row=node(plan,'article',null,'growth-task'+(task.completion?' completed':''));node(row,'h4',task.label);node(row,'p',task.reason);if(task.completion)node(row,'p',task.completion.helped?'완료 · 도움을 받아 연습했어요.':'완료 · 이번 과제를 도움 없이 풀었어요.','tag');else{const b=button(row,task.kind==='original'?'설명과 함께 다시 익히기':'새 문제 풀기',()=>train(task));b.dataset.ineligible=String(!current);b.disabled=!current;}}
 const again=button(plan,'새 문제로 다시 진단하기',recheck);again.classList.add('primary');again.dataset.ineligible=String(!current?.unlocked);again.disabled=!current?.unlocked;
};
const profile=node(document.getElementById('profile'),'section',null,'card growth-profile');profile.id='growthProfile';document.getElementById('profile').prepend(profile);
let saved=null,chosen='mate',chosenSeries=null;
function chart(host,points,label){
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 600 220');svg.classList.add('growth-chart');svg.setAttribute('role','img');svg.setAttribute('aria-label',label+' — 아래 기록 목록에서 수치를 확인할 수 있습니다.');host.append(svg);
 const shape=(tag,attrs)=>{const e=document.createElementNS(svg.namespaceURI,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);svg.append(e);return e;};
 for(const v of [0,50,100]){const y=190-v*1.5;shape('line',{x1:40,y1:y,x2:570,y2:y,stroke:'#41536c'});const t=shape('text',{x:4,y:y+5,fill:'#b8c9da','font-size':14});t.textContent=v;}
 const valid=points.map((p,i)=>({...p,x:points.length===1?300:50+i*510/Math.max(1,points.length-1),y:p.value==null?null:190-p.value*1.5}));
 valid.forEach((p,i)=>{const previous=valid[i-1];if(p.y==null)return;if(previous?.y!=null&&p.comparable&&previous.comparable&&p.group===previous.group)shape('line',{x1:previous.x,y1:previous.y,x2:p.x,y2:p.y,stroke:'#8fe5c8','stroke-width':3});shape('circle',{cx:p.x,cy:p.y,r:6,fill:p.comparable?'#8fe5c8':'#f2ca7a'});});
}
function renderProfile(){profile.replaceChildren();node(profile,'span','MY GROWTH','tag');node(profile,'h2','분야별로 쌓이는 나의 변화');
 const reports=saved?.results||[];if(!reports.length){node(profile,'p','첫 진단을 마치면 여기에 첫 번째 점이 생겨요. 아직 점수가 없는 분야는 0점으로 표시하지 않습니다.');button(profile,'첫 진단 시작',()=>tab('diagnosis'));return;}
 const select=node(profile,'select',null,'field');select.setAttribute('aria-label','성장 그래프 분야');for(const [id,label] of Object.entries(labels)){const option=node(select,'option',label);option.value=id;}select.value=chosen;select.onchange=()=>{chosen=select.value;renderProfile();};
 const seriesKey=r=>{const s=r.snapshot;return s?[s.version,s.assessment_version,s.competency_version,s.scope,s.mode,s.corpus].join('|'):null;};
 const measured=reports.filter(r=>r.snapshot),groups=[...new Set(measured.map(seriesKey))];
 if(!groups.includes(chosenSeries))chosenSeries=measured.length?seriesKey(measured.at(-1)):null;
 if(groups.length>1){const modes=node(profile,'select',null,'field');modes.setAttribute('aria-label','성장 그래프 비교 조건');for(const key of groups){const r=measured.find(r=>seriesKey(r)===key);const option=node(modes,'option',`${r.snapshot.mode==='balanced'?'균형':'간이'} 진단 · ${date(r.at)} 시작 · 비교 조건 ${groups.indexOf(key)+1}`);option.value=key;}modes.value=chosenSeries;modes.onchange=()=>{chosenSeries=modes.value;renderProfile();};}
 const recent=measured.filter(r=>seriesKey(r)===chosenSeries).slice(-12);
 const legacy=reports.filter(r=>!r.snapshot);if(legacy.length){const history=node(profile,'details');node(history,'summary',`이전·분야 추가 진단 ${legacy.length}개 기록`);for(const r of legacy)node(history,'p',`${date(r.at)} · ${r.version||'이전 버전'}`);}const points=recent.map(r=>{const s=r.snapshot,p=s?.areas?.[chosen];return {value:p?.score??null,comparable:!!p?.comparable,group:s?[s.version,s.assessment_version,s.competency_version,s.scope,s.mode,s.corpus].join('|'):null};});chart(profile,points,labels[chosen]+' 성장');
 node(profile,'p','같은 진단 방식·난도·버전의 충분한 관찰만 선으로 연결해요. 노란 점은 간이·부분 관찰이며 이전 버전과 직접 비교하지 않습니다.','subtle');
 const list=node(profile,'ol',null,'growth-records');recent.forEach((r,i)=>{const p=r.snapshot?.areas?.[chosen];node(list,'li',`${date(r.at)} · ${points[i].value==null?'점수 없음':points[i].value+'점'} · ${p?.observed??0}문제 관찰 · ${r.snapshot?.mode==='balanced'?'균형 진단':r.snapshot?.mode==='quick'?'간이 진단':'이전·추가 진단'}${r.snapshot?.training_completed!=null?' · 직전 추천 훈련 '+r.snapshot.training_completed+'개 완료':''}`);});
 const audit=node(profile,'details');node(audit,'summary','성장 비교의 기술 근거');node(audit,'p',chosenSeries||'비교 가능한 기록 없음');
 const latest=points.at(-1),previous=points.at(-2);if(latest?.comparable&&previous?.comparable&&latest.group===previous.group&&latest.value!=null&&previous.value!=null){const d=latest.value-previous.value;node(profile,'p',d===0?'이전과 같은 점수예요. 다양한 위치에서 꾸준히 확인해 보세요.':`이전보다 ${Math.abs(d)}점 ${d>0?'높아졌어요':'낮아졌어요'}. 문항 차이도 있으므로 한 번의 변화로 단정하지 않아요.`);}
 if(saved.cycle)node(profile,'p',`현재 추천 훈련 ${saved.cycle.completed}/5 완료 · ${saved.cycle.remaining}개 남음`);
 button(profile,'진단 결과와 추천 훈련',()=>tab('diagnosis'));
}
window.growthProfile=d=>{saved=d;renderProfile();};renderProfile();
const analysis=node(document.getElementById('profile'),'section',null,'card');analysis.id='gamePerformance';profile.after(analysis);
let analysisSerial=0,poll=null,analysisOwner=null,ratingMode='unlimited';
async function loadAnalysis(){const identity=token,rev=++analysisSerial;clearTimeout(poll);if(analysisOwner!==identity){analysisOwner=identity;analysis.replaceChildren();node(analysis,'p','대국 분석 기록을 불러오고 있어요…');}if(!identity){analysis.replaceChildren();node(analysis,'h2','AI 대국에서 배운 것');node(analysis,'p','로그인하면 저장한 대국을 분석할 수 있어요.');return;}
 try{const data=await api('/games/analysis');if(identity!==token||rev!==analysisSerial)return;renderAnalysis(data);if(data.games.some(g=>['queued','running'].includes(g.status))&&document.getElementById('profile').classList.contains('active'))poll=setTimeout(loadAnalysis,3000);}
 catch(e){if(identity!==token||rev!==analysisSerial)return;analysis.replaceChildren();node(analysis,'h2','대국 분석');node(analysis,'p',e.message,'notice');button(analysis,'다시 확인',loadAnalysis);}}
function renderAnalysis(data){analysis.replaceChildren();
 const rating=node(analysis,'section',null,'app-rating');node(rating,'h2','앱 내 추정 레이팅 · 베타');
 const modes={unlimited:'무제한',rapid:'래피드',blitz:'블리츠',bullet:'불릿'};const selector=node(rating,'select',null,'field');selector.setAttribute('aria-label','내부 레이팅 시계 형식');for(const [id,label] of Object.entries(modes)){const o=node(selector,'option',label);o.value=id;}selector.value=ratingMode;selector.onchange=()=>{ratingMode=selector.value;renderAnalysis(data);};
 const model=data.app_rating?.series?.[ratingMode];node(rating,'strong',model?`${model.value.toFixed(1)} / 100 · ${model.games}판${model.games<10?' · 잠정':''}`:'아직 반영할 대국이 없어요.');node(rating,'p',data.app_rating?.note||'승무패로 계산하는 미보정 앱 내부 지표입니다. 공식 Elo·사람 레이팅과 다르며, 내 수 품질과 별도로 계산합니다.');
 const rated=data.games.filter(g=>g.app_rating?.eligible&&g.time_mode===ratingMode&&g.app_rating.version===data.app_rating?.version).slice(-12);chart(rating,rated.map(g=>({value:g.app_rating.after,comparable:true,group:g.app_rating.version+'|'+g.time_mode})),'앱 내 추정 레이팅');const ratingList=node(rating,'ol',null,'growth-records');for(const g of rated){const r=g.app_rating;node(ratingList,'li',`${date(g.at)} · ${r.result==='win'?'승':r.result==='draw'?'무':'패'} · ${r.before.toFixed(1)} → ${r.after.toFixed(1)} · AI 내부 기준 ${r.anchor}`);}node(rating,'p','첫 50점은 제품 계산의 시작값으로 그래프에 별도 실력 점을 만들지 않습니다. 표본이 늘어도 미보정 베타 지표입니다.','subtle');
node(analysis,'h2','AI 대국에서 배운 것');node(analysis,'p',data.average==null?'분석을 마친 충분한 길이의 대국이 쌓이면 내 수 품질의 평균을 보여 드려요.':`대표 대국 ${data.representative_games}판의 내 수 품질 평균 ${data.average}/100`);node(analysis,'p','내 수 품질은 엔진 평가 손실을 줄였는지 보는 앱 자체 지표예요. 다른 체스 서비스의 정확도와 직접 비교하지 않습니다.','subtle');node(analysis,'p','외부 사람 레이팅 환산 · 산출 보류');node(analysis,'p',data.rating_reason,'subtle');
 if(!data.games.length){node(analysis,'p','AI와 첫 대국을 마치고 내 수를 돌아보세요.');button(analysis,'AI 대국 시작',()=>tab('play'));return;}
 const games=data.games.slice(-12);chart(analysis,games.map(g=>({value:g.quality??null,comparable:g.representative&&g.status==='complete',group:g.score_version})), '대국별 내 수 품질');
 const states={not_started:'분석 전',queued:'분석 대기',running:'분석 중',complete:'분석 완료',partial:'일부 분석',failed:'분석 실패',outdated:'이전 방식 분석'};
 for(const g of [...games].reverse()){const row=node(analysis,'article',null,'growth-task');node(row,'h3',`${date(g.at)} · ${g.color==='black'?'흑':'백'} 대국`);node(row,'p',`${states[g.status]||g.status}${g.quality!=null?' · 내 수 품질 '+g.quality+'/100':''}`);if(g.app_rating&&!g.app_rating.eligible)node(row,'p','내부 레이팅 제외: '+g.app_rating.reasons.join(' · '),'subtle');if(g.user_moves!=null)node(row,'p',`내 착수 ${g.user_moves}/${g.expected_moves}개 분석 · ${(g.flags||[]).join(' · ')||'대표 평균에 포함'}`);if(g.mate_unscored)node(row,'p',`수치 평균은 ${g.quality_moves}착수 기준 · 메이트 평가 ${g.mate_unscored}착수는 cp로 환산하지 않고 별도 기록`,'subtle');if(g.engine)node(row,'small',`${g.engine} · ${g.settings.seconds_per_position}초/국면 · ${g.score_version}`);if(g.error)node(row,'p',g.error,'notice');if(['not_started','failed','outdated'].includes(g.status))button(row,g.status==='failed'?'분석 다시 시도':g.status==='outdated'?'새 방식으로 분석':'이 대국 분석',async()=>{const identity=token;try{await api('/games/analysis/'+g.game_key,'POST');if(identity===token)loadAnalysis();}catch(e){if(identity===token)node(row,'p',e.message,'notice');}});}
}
const oldTab=tab;tab=function(id){oldTab(id);if(id==='profile')loadAnalysis();else clearTimeout(poll);};
const signout=document.getElementById('signout'),oldSignout=signout?.onclick;if(signout)signout.onclick=function(e){analysisSerial++;clearTimeout(poll);saved=null;renderProfile();analysis.replaceChildren();return oldSignout?.call(this,e);};
})();
