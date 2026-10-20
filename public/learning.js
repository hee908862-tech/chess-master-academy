/* A single learning state and API for desktop and compact touch layouts. */
(() => {
  const el = (tag, text, cls) => { const n=document.createElement(tag); if(text)n.textContent=text;if(cls)n.className=cls;return n; };
  const button = (text, fn) => {const b=el('button',text,'btn');b.onclick=fn;return b;};
  let dashboard=null, task=null, selected=null, busy=false, generation=0, playbackIndex=-1, pendingLoad=false, cardsRequest=null;
  const statusNames={unaided_first_success:'도움 없이 첫 시도 성공',later_unaided_success:'다른 날짜 도움 없이 성공',revealed_success:'정답 공개 후 성공',hinted_success:'도움 사용 후 성공',retry_success:'오답 후 재시도 성공',not_yet:'아직 미달성',unverified_alternative:'대안 수 미검증 (능력 집계 제외)',unaided_repeat_success:'같은 날짜 도움 없이 재시도 성공'};
  function outcomeLabel(a){
    if(!a)return '';
    const situation=a.mode?.startsWith('situation');
    if(a.success&&a.current_helped===false&&a.prior_help_known){
      return (situation?'이번 시도 도움 없이 기준 충족':'이번 시도 도움 없이 성공')+(a.prior_helped?' · 이전 같은 국면에서 도움 사용':'');
    }
    return (statusNames[a.status]||a.status||'기록 확인')+(situation&&a.success?' · 평가 유지 기준 충족 (대국 승리와 별도)':'');
  }
  const modeNames={practice:'연습',verify:'검증',situation_practice:'상황 연습',situation_verify:'상황 검증'};
  const home=el('details',null,'card learning-home');
  home.innerHTML='<summary>이전 4단계 학습 경로 · 선택 연습</summary><span class="tag">TODAY · 나의 학습 경로</span><h2>배운 수를 새로운 상황에 적용해 보세요.</h2><p class="lead" id="learningReason">로그인하면 나의 복습과 오늘의 적용 문제를 안내합니다.</p><div class="learning-path" id="learningPath"></div><div class="btn-row" id="learningHomeActions"></div>';
  $('home').prepend(home);
  const view=el('section',null,'view');view.id='training';
  view.innerHTML=`<div class="card"><div class="row"><div><span class="tag">LEARNING STUDIO</span><h2 class="heading">나의 훈련실</h2></div><button class="btn" id="learningRefresh">기록 새로고침</button></div><details><summary>기록 범위와 측정 기준</summary><p id="learningNotice" class="lead">기존 기록은 그대로 유지됩니다.</p></details><div class="btn-row"><button class="btn primary" id="learningFresh">새 첫 수 연습</button><button class="btn" id="learningVerify">미출제 첫 수 검증</button><button class="btn" id="learningReview">내 대국 복기</button></div></div>
  <div class="card" id="learningSaved"></div><details class="card" id="learningRoute"><summary>이전 4단계 경로 · 선택 연습</summary><h3>저장된 경로</h3><p id="learningRouteStatus" class="lead"></p><div class="btn-row" id="learningRouteActions"></div></details><div class="learning-layout"><div class="card learning-position"><div class="row"><strong id="learningTitle">시작할 문제를 선택하세요</strong><span class="tag" id="learningMode">준비</span></div><p id="learningGoal" class="lead">아래 오답노트에서 다시 풀거나 새 문제로 시작하세요.</p><div id="learningBoard" class="board"></div><p id="learningMessage" class="notice" role="status" aria-live="polite"></p><div class="btn-row" id="learningControls"></div><p class="subtle">이 훈련은 한 수씩 판단합니다. 프리무브는 사용하지 않습니다.</p></div>
  <aside class="learning-aside"><details class="card" id="learningDetails" open><summary>개념 · 근거 · 수순</summary><p id="learningConcept" class="lead"></p><details><summary>자료 출처와 기술 근거</summary><p id="learningEvidence" class="lead"></p></details><p id="learningExplanation" class="lead"></p><div id="learningPlayback" class="btn-row"></div></details><details class="card" open><summary>오답노트 · 다시 풀기</summary><div id="learningCards" class="learning-list"></div></details></aside></div>
  <details class="card"><summary>전체 수순 훈련의 능력 지도 · 진단 점수와 별도</summary><h3>근거로 보는 능력 지도</h3><p class="lead">같은 버전·같은 측정 범위의 도움 없이 근거만 비교합니다. 최근·이전 각 5개 독립 국면이 없으면 추세를 판단하지 않습니다. 같은 위치 반복은 국면 수를 늘리지 않습니다. 실제 레이팅이 아닙니다.</p><div id="learningSkills" class="learning-skills"></div></details>
  <details class="card"><summary>최근 학습 기록 · 복습 간격</summary><p class="lead">초기 간격 1·3·7일은 조정 가능한 시작값이며 최적 학습 간격을 뜻하지 않습니다. 변경은 다음 완료 기록부터 적용됩니다.</p><label for="learningIntervals">복습 간격 (일, 쉼표 구분)</label><input id="learningIntervals" class="field" value="1,3,7" inputmode="numeric"><button class="btn" id="learningSaveIntervals">간격 저장</button><div id="learningAttempts" class="learning-list"></div></details>`;
  document.querySelector('main').append(view);
  view.querySelector('.learning-aside').prepend($('learningRoute'));
  const compactNav=el('nav',null,'learning-mobile-nav');compactNav.setAttribute('aria-label','훈련실 이동');
  for(const [id,label] of [['home','홈'],['play','대국'],['review','복기'],['profile','기록']])compactNav.append(button(label,()=>tab(id)));
  view.prepend(compactNav);
  for(const nav of document.querySelectorAll('.nav,.mobile-nav')){
    const b=button('훈련실',()=>tab('training'));b.dataset.tab='training';nav.append(b);
  }
  $('learningHomeActions').append(button('훈련실 열기',()=>tab('training')),button('자유롭게 대국하기',()=>tab('play')));
  $('reviewLoad').after(button('이 대국을 개인 훈련으로',async()=>{
    if(!ready()||busy)return;
    await run(async()=>{const r=await api('/learning/import/'+$('reviewGameSelect').value,'POST');tab('training');await load();$('learningMessage').textContent=r.message;});
  }));
  function clear(){generation++;task=null;dashboard=null;selected=null;busy=false;render();$('learningCards').replaceChildren();$('learningAttempts').replaceChildren();$('learningSkills').replaceChildren();$('learningReason').textContent='로그인하면 나의 학습 경로를 안내합니다.';}
  async function run(fn,waiting='저장 중입니다. 상황 대국은 엔진 응수를 기다려 주세요.'){
    if(busy)return;
    busy=true;renderControls();lockControls();
    $('learningMessage').textContent=waiting;
    const identity=token,rev=generation;let succeeded=false;
    try{await fn();succeeded=true;}
    catch(e){if(identity===token&&rev===generation)$('learningMessage').textContent=e.message;}
    finally{if(identity===token){busy=false;renderDashboard();renderControls();lockControls();
      if(succeeded&&(!$('learningMessage').textContent||$('learningMessage').textContent===waiting))$('learningMessage').textContent=task?.message||'준비되었습니다. 보드에서 기물을 선택하세요.';
      if(pendingLoad){pendingLoad=false;load();}
    }}
  }
  async function load(force=false){
    if(busy&&!force){pendingLoad=true;return;}
    if(!token){clear();$('learningRouteStatus').textContent='로그인 후 경로를 시작할 수 있습니다. 아직 수행한 학습은 없습니다.';$('learningRouteActions').replaceChildren(button('로그인 후 경로 준비',()=>ready('training')));$('learningCards').textContent='로그인하면 저장된 위치가 표시됩니다.';$('learningSkills').textContent='학습 기록을 확인하려면 로그인하세요.';$('learningNotice').textContent='로그인하면 나에게 맞는 학습 경로와 기록을 볼 수 있습니다. 시작 버튼에서 로그인한 뒤 이 화면으로 돌아옵니다.';return;}const identity=token, rev=++generation;
    try{const d=await api('/learning/dashboard');if(identity!==token||rev!==generation)return;dashboard=d;task=d.active;selected=null;playbackIndex=-1;renderDashboard();render();}
    catch(e){if(identity===token&&rev===generation)$('learningMessage').textContent=e.message;}
  }
  async function continuePath(action='continue'){
    if(!ready()||busy)return;
    let pause={};if(task&&!task.done&&task.path_id!==dashboard?.path?.id){if(!confirm('현재 훈련을 저장하고 선택 경로로 전환할까요? 저장된 훈련에서 다시 이어갈 수 있습니다.'))return;pause={pause_session_id:task.session_id,pause_revision:task.revision};}
    // Navigation starts an asynchronous dashboard read. Invalidate it before applying the path result.
    if(!$('training').classList.contains('active'))tab('training');
    generation++;
    await run(async()=>{
      const identity=token,rev=generation,path=dashboard?.path;
      const r=await api('/learning/path','POST',{action,path_id:path?.id,revision:path?.revision,...pause});
      if(identity!==token||rev!==generation)return;
      task=r.active;selected=null;playbackIndex=-1;await updateStats();render();
      if(r.path.current===1)$('learningDetails').open=true;
    });
  }
  async function start(options){if(!ready()||busy)return;const same=task&&options.card_id===task.card_id&&(options.mode||'practice')===task.mode&&!options.fresh&&!options.similar_to;if(task&&!task.done&&!same){if(!confirm('현재 착수와 도움 사용을 저장해 두고 다른 문제로 전환할까요? 저장된 훈련에서 이어갈 수 있습니다.'))return;options={...options,pause_session_id:task.session_id,pause_revision:task.revision};}await run(async()=>{
    const identity=token, rev=generation;const r=await api('/learning/start','POST',options);
    if(identity!==token||rev!==generation)return;task=r;selected=null;playbackIndex=-1;render();await updateStats();
  });}
  async function updateStats(){const identity=token,rev=generation;const d=await api('/learning/dashboard');if(identity!==token||rev!==generation)return;dashboard=d;renderDashboard();}
  async function loadMoreCards(){
    if(cardsRequest||!dashboard||dashboard.cards_next==null)return;
    const request={identity:token,rev:generation,list:dashboard,cursor:dashboard.cards_next};
    cardsRequest=request;renderDashboard();
    const current=()=>request.identity===token&&request.rev===generation&&request.list===dashboard&&request.cursor===dashboard.cards_next;
    try{
      const d=await api('/learning/dashboard?offset='+request.cursor);
      if(!current())return;
      const seen=new Set(dashboard.cards.map(c=>c.id));
      const older=d.cards.filter(c=>{if(seen.has(c.id))return false;seen.add(c.id);return true;});
      dashboard={...dashboard,cards:[...older,...dashboard.cards],cards_next:d.cards_next};
    }catch(e){if(current())$('learningMessage').textContent=e.message;}
    finally{if(cardsRequest===request){cardsRequest=null;renderDashboard();}}
  }
  async function act(action,move){if(!task||task.done)return;const s=task;await run(async()=>{
    const identity=token, rev=generation;
    const r=await api('/learning/action','POST',{session_id:s.session_id,revision:s.revision,action,move});
    if(identity!==token||rev!==generation)return;task=r;selected=null;playbackIndex=-1;render();if(r.done)await updateStats();
  });}
  function renderDashboard(){
    if(!dashboard)return;
    $('learningNotice').textContent=dashboard.notice;
    $('learningSaved').replaceChildren(el('h3','저장된 훈련 이어하기'));
    if(task&&!task.done){$('learningSaved').append(el('p','현재 훈련은 착수·도움 사용과 함께 저장됩니다. 새 문제로 전환하려면 보존 확인이 필요합니다.'),button('현재 훈련 이어하기',()=>{$('learningBoard').scrollIntoView({block:'center'});}));}
    for(const saved of dashboard.paused||[]){$('learningSaved').append(button(`${saved.category||'검증'} · ${saved.card_id.slice(-8)} · ${saved.turns}수 진행 이어하기`,()=>run(async()=>{const identity=token,rev=generation;const r=await api('/learning/resume','POST',{session_id:saved.session_id,active_id:task?.session_id,active_revision:task?.revision});if(identity!==token||rev!==generation)return;task=r;selected=null;playbackIndex=-1;await updateStats();render();})));}
    if(!task&&!dashboard.paused?.length)$('learningSaved').append(el('p','아직 진행 중인 훈련이 없습니다.'));
    $('learningReason').textContent=`${dashboard.reason} · 복습할 위치 ${dashboard.due_count??dashboard.due.length}개`;
    $('learningIntervals').value=dashboard.intervals.join(',');
    $('learningPath').replaceChildren();
    const route=dashboard.path;
    home.classList.toggle('has-saved-path',!!route||!!dashboard.active||(dashboard.due_count??dashboard.due.length)>0);
    const labels=[route?.fresh?'01 · 입문 새 문제':'01 · 복습','02 · 개념','03 · 같은 원리의 새 문제','04 · 상황 대국'];
    const states={pending:'대기',active:'진행 중',completed:'완료',skipped:'건너뜀'};
    labels.forEach((label,i)=>{const step=route?.steps[i];const b=button('',()=>continuePath());b.classList.add('learning-step');b.append(el('strong',label),el('span',step?`${states[step.status]} · ${step.reason}`:'경로 시작 시 항목 선택'));b.disabled=busy||!!route&&(route.done||route.current!==i);b.title=b.disabled?(busy?'기록 저장 중입니다.':route.done?'경로의 모든 시도를 마쳤습니다. 새 경로를 선택하세요.':'현재 단계를 마친 뒤 이어갈 수 있습니다.'):'현재 단계 열기';$('learningPath').append(b);});
    $('learningRouteStatus').textContent=route?`${route.date} · ${route.done?'경로 처리 완료 (성공 여부는 별도)' :`${route.current+1}/4 단계`} · ${route.selection_reason}`:'복습할 카드를 선택해 경로를 저장하고 시작합니다.';
    if(route?.diagnosis)$('learningRouteStatus').textContent+='\n왜 이 훈련인가: 진단에서 '+(route.diagnosis.complete?'전체 수순을 완주한 위치를 복습합니다.':route.diagnosis.first_correct?'첫 수는 맞혔지만 전체 수순 확인이 필요합니다.':'아직 전체 수순을 확인하지 못했습니다.')+' '+(route.diagnosis.reason||'')+' 같은 위치 반복은 새 독립 진단에 합산하지 않습니다.';
    if(route)$('learningRouteStatus').textContent+='\n선택 항목: '+(route.source_title||'없음')+'\n'+route.steps.map((step,i)=>`${labels[i]} · ${states[step.status]}${step.status==='skipped'?' · '+step.reason:''}`).join('\n');
    $('learningRouteActions').replaceChildren();
    if(route?.current===1&&!route.done&&route.steps[1].status==='active'){
      $('learningRouteStatus').textContent+='\n'+route.concept+'\n확인된 태그: '+(route.tags.join(', ')||'태그 없음');
      $('learningRouteActions').append(button('개념 읽기 확인',()=>continuePath('acknowledge')));
    }else $('learningRouteActions').append(button(route?.done?'새 경로 선택':'경로 시작 · 이어가기',()=>continuePath(route?.done?'new':'continue')));
    $('learningCards').replaceChildren();
    if(!dashboard.cards.length)$('learningCards').append(el('p','아직 저장한 위치가 없습니다. 새 문제 또는 내 대국 복기로 시작하세요.','lead'));
    for(const c of [...dashboard.cards].reverse()){
      const item=el('div',null,'learning-item');item.append(el('strong',`${c.category_label||c.category} · ${c.puzzle_id||c.id.slice(-8)} · ${c.title}`),el('p',`${c.full_line?'전체 수순':'첫 수 판단'} · ${c.source} · ${c.created_at?.slice(0,10)||'시작일 미기록'}${c.rating?' · 자료 난도 '+c.rating:''}`),el('p',c.last_outcome?`최근 ${c.last_outcome.at.slice(0,10)} · ${statusNames[c.last_outcome.status]||c.last_outcome.status}`:'최근 결과 미기록'),el('small',`다음 복습 ${c.due.slice(0,10)} · 도움 없이 성공 ${c.successes}회`));
      item.append(button('다시 연습',()=>start({card_id:c.id})));const extra=el('details');extra.append(el('summary','다른 연습 방식'));const actions=el('div',null,'btn-row');actions.append(button('검증',()=>start({card_id:c.id,mode:'verify'})),button('같은 원리의 새 문제',()=>start({similar_to:c.id,mode:'verify'})));
      for(const [mode,label] of [['situation_practice','상황 연습'],['situation_verify','상황 검증']]){const b=button(label,()=>start({card_id:c.id,mode}));b.disabled=!dashboard.engine;b.title=dashboard.engine?'':'엔진을 사용할 수 없어 상황 대국을 시작할 수 없습니다.';actions.append(b);}extra.append(actions);item.append(extra);$('learningCards').append(item);
    }
    if(dashboard.cards_next!=null){const more=button(cardsRequest?'이전 카드 불러오는 중…':'이전 훈련 카드 더 보기',loadMoreCards);more.disabled=!!cardsRequest;$('learningCards').append(more);}
    $('learningSkills').replaceChildren();dashboard.skills.forEach(s=>{const box=el('div',null,'learning-item');box.append(el('strong',s.name),el('p',s.measured===false?'미측정 · 검증된 과제 준비 전':s.insufficient?'현재 버전 전체 수순 · 근거 부족':`현재 버전 전체 수순 · 최근 ${s.recent}% (${s.recent_n}/5 국면) · ${s.trend_available?`이전 ${s.previous}% (${s.previous_n}/5 국면)`:'이전 비교 근거 부족 · 추세 미판정'}`),el('small',`전체 수순 ${s.full_line_count||0}회 · 첫 수 판단 ${s.first_move_count||0}회(별도 참고) · 전체 참고 기록 ${s.count}회 · 연습 ${s.practice_count}회 / 검증 ${s.verification_count}회 · 같은 원리 적용 성공 ${s.transfer}회`));const technical=el('details');technical.append(el('summary','자세한 측정 근거'));box.append(technical);for(const g of s.groups||[]){const scope={first_move:'첫 수 판단',full_line:'전체 수순',engine_situation:'상황 대국',unrecorded:'측정 범위 미기록'}[g.assessment_scope]||g.assessment_scope;technical.append(el('p',`${g.reference_only?'별도 참고':'추천 기준'} · ${g.version==='unrecorded'?'버전 미기록':g.version} · ${scope} · ${g.count}회 / 독립 ${g.distinct}국면 · ${g.insufficient?'근거 부족':`최근 ${g.recent}% (${g.recent_n}/5)`} · ${g.trend_available?`동일 범위 이전 ${g.previous}% (${g.previous_n}/5)`:'추세 미판정'}`));}$('learningSkills').append(box);});
    lockControls();
    $('learningAttempts').replaceChildren();dashboard.attempts.forEach(a=>$('learningAttempts').append(el('p',`${a.at.slice(0,10)} · ${modeNames[a.mode]} · ${outcomeLabel(a)}`,'learning-item')));
  }
  function lockControls(){
    for(const b of document.querySelectorAll('#training button, #learningPath button')){
      if(busy){if(!b.hasAttribute('data-before-busy'))b.dataset.beforeBusy=String(b.disabled);b.disabled=true;}
      else if(b.hasAttribute('data-before-busy')){b.disabled=b.dataset.beforeBusy==='true';delete b.dataset.beforeBusy;}
    }
    $('learningBoard').setAttribute('aria-busy',String(busy));
  }
  function render(){
    const route=dashboard?.path;
    const concept=!task?.growth_task && route?.current===1 && route.steps[1].status==='active' && !route.done ? route : null;
    const t=concept?null:task;
    $('learningTitle').textContent=t?(t.category||'주제 비공개 · 독립 판단'):concept?'개념 확인 · 진단과 같은 원리':'시작할 문제를 선택하세요';
    $('learningMode').textContent=t?`${modeNames[t.mode]}${t.done?' 완료':''}`:concept?'읽기 전용 · 개념':'준비';
    $('learningGoal').textContent=t?`${t.goal} ${t.assessment_scope==='first_move'?'이 활동은 첫 수 판단으로 저장되며 아래 전체 수순 능력 지도에 합산하지 않습니다.':'전체 수순 수행으로 저장하며 독립 근거 조건을 충족할 때만 능력 지도에 반영합니다.'}`:(concept?'아래 설명과 원본 위치를 확인하고 개념 읽기 확인을 누르세요.':'오답노트에서 다시 풀거나 새 문제로 시작하세요.');
    if(t?.mode?.startsWith('situation'))$('learningGoal').textContent+=' 100cp는 엔진 평가에서 폰 한 개 정도의 값입니다. 실제 기물 획득이나 대국 승리를 뜻하지 않습니다.';
    $('learningMessage').textContent=t?.message||'';
    $('learningConcept').textContent=concept?.concept||t?.concept||(t&&!t.done&&t.mode.includes('verify')?'검증 중에는 개념을 표시하지 않습니다.':'문제를 선택하면 확인된 개념을 표시합니다.');
    $('learningEvidence').textContent=(t?.source||'문제와 분석의 출처가 여기에 표시됩니다.')+(t?.selection?.overlap?.length?'\n공통 태그: '+t.selection.overlap.join(', ')+' · '+t.selection.evidence:'');
    $('learningExplanation').textContent=[t?.context,t?.explanation].filter(Boolean).join('\n');
    const frame=playbackIndex>=0?t?.playback[playbackIndex]:null;
    const target=selected?(t?.legal||[]).filter(u=>u.slice(0,2)===selected).map(u=>({to:u.slice(2,4)})):[];
    if(t?.fen||concept?.concept_position?.fen)drawBoard('learningBoard',fromFen(frame?.fen||t?.fen||concept?.concept_position?.fen||chessStart),{flip:(t?.side||concept?.concept_position?.side)==='black',selected,targets:target,opponent:!frame&&t?.opponent_last_move?[t.opponent_last_move.slice(0,2),t.opponent_last_move.slice(2,4)]:[],last:frame?[frame.move.slice(0,2),frame.move.slice(2,4)]:[],onClick:t&&!t.done&&!frame?click:undefined});else $('learningBoard').replaceChildren();
    $('learningPlayback').replaceChildren();
    if(t?.playback?.length){$('learningPlayback').append(button('현재 문제로',()=>{playbackIndex=-1;render();}));t.playback.forEach((f,i)=>$('learningPlayback').append(button(`${i+1}. ${f.san}`,()=>{playbackIndex=i;selected=null;render();})));}
    renderControls();lockControls();
  }
  function renderControls(){
    const area=$('learningControls');area.replaceChildren();if(!task?.growth_task&&dashboard?.path?.current===1&&dashboard.path.steps[1].status==='active'){area.append(el('span','설명을 읽은 뒤 옆 또는 아래 경로의 개념 읽기 확인을 눌러 주세요.','subtle'));return;}if(!task)return;
    if(task.done&&task.growth_task){area.append(el('p',outcomeLabel(task.outcome),'tag'),button('추천 훈련과 진행률 보기',()=>tab('diagnosis')));return;}
    if(task.done){area.append(el('p',outcomeLabel(task.outcome)||'완료','tag'));if(task.path_id){area.append(button('경로 다음 단계',()=>continuePath()));return;}area.append(button('같은 위치 다시',()=>start({card_id:task.card_id,mode:task.mode})),button('다음 첫 수 검증',()=>start({fresh:true,mode:'verify',category:task.outcome.category})));return;}
    if(task.growth_task&&task.selection?.source_card&&task.rating){area.append(button('너무 어려워요 · 더 낮은 난도 찾기',()=>{if(!confirm('현재 착수는 보존하고 같은 과제 슬롯을 더 낮은 난도의 미노출 문제로 바꿀까요? 완료 횟수는 늘지 않습니다.'))return;run(async()=>{const identity=token,rev=generation;const r=await api('/learning/cycle/easier','POST',{report_id:task.growth_task.report_id,item_id:task.growth_task.task_id,card_id:task.card_id,session_id:task.session_id,revision:task.revision});if(identity!==token||rev!==generation)return;task=r;selected=null;playbackIndex=-1;await updateStats();render();});}));}
    if(!task.mode.includes('verify')){
      for(const [a,label] of [['hint',`힌트 ${Math.min(task.hint_level+1,3)}단계`],['reveal','답안 수순'],['refutation','상대 응수'],['undo','한 수 무르기']]){if(a==='undo'&&!task.mode.startsWith('situation'))continue;const b=button(label,()=>act(a));b.disabled=busy;area.append(b);}
    }else area.append(el('span','검증 중에는 힌트와 무르기를 사용할 수 없습니다.','subtle'));
  }
  async function click(square){
    if(busy||!task||task.done||playbackIndex>=0)return;
    const options=task.legal.filter(u=>u.slice(0,2)===selected&&u.slice(2,4)===square);
    if(!options.length){selected=task.legal.some(u=>u.slice(0,2)===square)?square:null;render();return;}
    let move=options[0];
    if(options.length>1){const identity=task;busy=true;lockControls();try{const promotion=await choosePromotion(selected,square,fromFen(task.fen)[selected],task.legal);if(!promotion||identity!==task||!$('training').classList.contains('active'))return;move=options.find(u=>u[4]===promotion); }finally{busy=false;lockControls();}}
    if(move)await act('move',move);
  }
  $('learningFresh').onclick=()=>start({fresh:true,category:dashboard?.recommended});
  $('learningVerify').onclick=()=>start({fresh:true,mode:'verify',category:dashboard?.recommended});
  $('learningReview').onclick=()=>tab('review');
  $('learningRefresh').onclick=load;
  $('learningSaveIntervals').onclick=()=>run(async()=>{const intervals=$('learningIntervals').value.split(',').map(Number);await api('/learning/settings','POST',{intervals});$('learningMessage').textContent='다음 완료부터 사용할 복습 간격을 저장했습니다.';});
  window.learningRetention=async(report_id,item_id)=>{if(!ready('training')||busy)return;tab('training');generation++;await run(async()=>{const identity=token,rev=generation;const r=await api('/learning/retention/start','POST',{report_id,item_id});if(identity!==token||rev!==generation)return;task=r;selected=null;playbackIndex=-1;await updateStats();render();},'7일 기억 확인을 위한 미노출 전체 수순 검증을 준비합니다…');};
  window.learningCycle=async(report_id,item_id)=>{if(!ready('training')||busy)return;tab('training');generation++;await run(async()=>{const identity=token,rev=generation;const result=await api('/learning/cycle/start','POST',{report_id,item_id});if(identity!==token||rev!==generation)return;task=result;selected=null;playbackIndex=-1;await updateStats();render();},'추천 훈련을 준비하고 있어요…');};
  window.learningFromDiagnosis=async(report_id,item_id)=>{
    if(!ready('training')||busy)return;
    tab('training');generation++;
    task=null;dashboard=null;selected=null;playbackIndex=-1;render();
    $('learningMessage').textContent='선택한 진단의 원본 훈련을 여는 중입니다…';
    await run(async()=>{
      const identity=token,rev=generation;
      try{
        const result=await api('/learning/from-diagnosis','POST',{report_id,item_id});
        if(identity!==token||rev!==generation)return;
        task=result.active;selected=null;playbackIndex=-1;
        await updateStats();render();
        $('learningMessage').textContent=task?.message||(task?'선택한 진단 문제입니다. 보드에서 바로 연습하세요.':'보존된 경로의 현재 단계를 이어서 진행하세요.');
      }catch(e){
        if(identity!==token||rev!==generation)return;
        // A timeout can follow a successful save: read state before allowing another start.
        await load(true);
        $('learningMessage').textContent=e.message;
        if(e.detail?.code==='active_learning_path')$('learningRouteActions').replaceChildren(button('보존된 경로 이어하기',()=>continuePath()));
      }
    },'선택한 진단의 원본 훈련을 여는 중입니다…');
  };
  const oldTab=tab;
  tab=function(id){document.body.classList.toggle('learning-active',id==='training');generation++;selected=null;oldTab(id);if(id==='training'||id==='home')load();};
  const oldSignout=$('signout')?.onclick;
  if($('signout'))$('signout').onclick=function(e){clear();return oldSignout?.call(this,e);};
  const mq=matchMedia('(max-width: 760px)');const details=()=>{$('learningDetails').open=!mq.matches;};details();mq.addEventListener('change',details);
  render();load();
})();
