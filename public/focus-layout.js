/* Presentation only: reuse controller-owned nodes; opening a panel never navigates or writes. */
(()=>{'use strict';
const $=id=>document.getElementById(id);
function details(parent,id,label,nodes){const d=document.createElement('details');d.id=id;d.className='focus-details';const s=document.createElement('summary');s.textContent=label;d.append(s);for(const n of nodes)if(n)d.append(n);parent.append(d);d.addEventListener('keydown',e=>{if(e.key==='Escape'&&d.open){e.stopPropagation();d.open=false;s.focus({preventScroll:true});}});return d;}
function install(){
 const actions=document.querySelector('.foundation-actions');
 actions.prepend($('foundationLive'),$('foundationAnswers'),$('foundationNext'));
 const brief=document.createElement('p');brief.id='foundationReasonBrief';brief.className='focus-reason';$('foundationNext').after(brief);
 const explanation=details(actions,'foundationExplanation','이유 · 자세한 해설',[$('foundationFeedback'),$('foundationFullInstruction')]);
 const visual=$('foundationVisualTools');actions.append(visual);const tools=details(actions,'foundationFocusTools','안내 표시의 의미',[$('foundationVisualLegend')]);
 tools.after($('foundationAlternative'));
 const policy=actions.querySelector(':scope > .subtle');if(policy)explanation.append(policy);
 function update(){const text=$('foundationFeedback').textContent;const short=text.length>140?text.slice(0,140)+'…':text;if(brief.textContent!==short)brief.textContent=short;}
 new MutationObserver(update).observe($('foundationFeedback'),{childList:true,subtree:true,characterData:true});update();
 const training=$('training'),library=document.createElement('section');library.id='trainingLibrary';library.setAttribute('aria-label','훈련 선택과 기록');
 const trainingLayout=training.querySelector('.learning-layout');trainingLayout.before(library);const trainingJumps=training.querySelector('.feature-jumps');if(trainingJumps)trainingLayout.after(trainingJumps);
 for(const n of [$('learningSetup'),$('learningSaved'),$('learningCards').closest('details'),$('learningSkills').closest('details'),$('learningAttempts').closest('details'),$('trainingCycle')])if(n)library.append(n);
 // Reuse the controller's exact nodes: core actions beside the board on PC, immediately after it on mobile.
 const trainingAside=training.querySelector('.learning-aside'),trainingCore=document.createElement('section');trainingCore.id='trainingCore';trainingCore.setAttribute('aria-label','현재 훈련 판정과 핵심 조작');trainingAside.prepend(trainingCore);
 for(const n of [$('learningControls'),$('learningMessage'),$('learningGoal'),$('learningLink'),training.querySelector('.learning-position > .subtle')])if(n)trainingCore.append(n);
 function arrangeTrainingCore(){if(trainingAside.firstElementChild!==trainingCore)trainingAside.prepend(trainingCore);const feedback=$('learningBoardFeedback');if(feedback&&feedback.parentElement!==trainingCore)trainingCore.prepend(feedback);const facts=$('learningBoardFacts');if(facts&&facts.parentElement!==trainingCore)$('learningControls').after(facts);}
 const selectionStatus=document.createElement('p');selectionStatus.setAttribute('role','status');selectionStatus.id='trainingSelectionStatus';library.prepend(selectionStatus);new MutationObserver(()=>{selectionStatus.textContent=$('learningMessage').textContent;}).observe($('learningMessage'),{childList:true,subtree:true,characterData:true});
 const trainNav=document.createElement('div');trainNav.className='btn-row focus-selection';training.querySelector('.feature-toolbar').after(trainNav);
 let lastTask=null,trainingChoice=false;
 const selectButton=document.createElement('button');selectButton.className='btn';selectButton.textContent='훈련 선택 · 저장 활동 · 기록';selectButton.onclick=()=>{trainingChoice=true;applyTraining();library.tabIndex=-1;library.focus({preventScroll:true});scrollTo({top:0,behavior:'instant'});};trainNav.append(selectButton);
 const resumeButton=document.createElement('button');resumeButton.className='btn';resumeButton.textContent='현재 훈련으로';function resumeTraining(){trainingChoice=false;applyTraining();$('learningTitle').tabIndex=-1;$('learningTitle').focus({preventScroll:true});scrollTo({top:0,behavior:'instant'});}resumeButton.onclick=resumeTraining;trainNav.append(resumeButton);
 function applyTraining(){const active=!!$('learningBoard').querySelector('.sq')||$('learningMode').textContent==='읽기 전용 · 개념';const pathHost=$('trainingRecords')||(active&&!trainingChoice?training.querySelector('.learning-aside'):library);if($('learningRoute').parentElement!==pathHost)pathHost.prepend($('learningRoute'));arrangeTrainingCore();library.hidden=active&&!trainingChoice;trainingLayout.hidden=!active||trainingChoice;resumeButton.hidden=!active||!trainingChoice;selectButton.hidden=!active||trainingChoice;}
 // Existing layout hook must not move setup/records out of this explicit selection screen.
 window.cmaBoardLayout.training=()=>applyTraining();
 const openingPick=$('openingStudy').querySelector('.study-pickers');const openingChooser=details($('openingStudy'),'focusOpeningSelection','강의 · 모드 · 방향 선택',[openingPick]);$('openingStudy').querySelector('.study-layout').before(openingChooser);openingChooser.open=false;
 openingPick.addEventListener('change',()=>{scrollTo({top:0,behavior:'instant'});});
 const puzzleSetup=$('v9PuzzleRoot').querySelector('.v9-controls'),puzzleChooser=details($('v9PuzzleRoot'),'focusPuzzleSelection','다른 문제 · 주제와 난도',[ $('v9CatalogStatus'),puzzleSetup]);$('v9PuzzleRoot').querySelector('.v9-layout').before(puzzleChooser);puzzleChooser.open=true;
 let puzzleSession=null,puzzleOwner=null;
 function puzzleReady(id){if(!id)return;if(puzzleOwner!==token||id!==puzzleSession){puzzleOwner=token;puzzleSession=id;puzzleChooser.open=false;if(puzzleChooser.contains(document.activeElement)){$('v9PuzzleMeta').tabIndex=-1;$('v9PuzzleMeta').focus({preventScroll:true});}if($('puzzle').classList.contains('active'))scrollTo({top:0,behavior:'instant'});}}
 // Controller-owned nodes remain inside their body so busy/identity guards still cover every control.
 const educational=[];
 for(const [hostId,bodyId,layoutClass,boardId] of [['educationPaths','educationBody','education-layout','educationBoard'],['repertoire','repertoireBody','repertoire-layout','repertoireBoard']]){
  const host=$(hostId),body=$(bodyId),headerNodes=[...host.children].filter(n=>n!==body);
  const header=details(host,hostId+'FocusScope','사용법 · 범위 · 저장 상태',headerNodes);host.prepend(header);header.open=true;
  educational.push({host,body,bodyId,header,layoutClass,boardId,active:false});
 }
 function arrangeEducational(){for(const item of educational){const {host,body,bodyId,header,layoutClass,boardId}=item,layout=body.querySelector('.'+layoutClass),active=!!layout;if(active!==item.active){item.active=active;header.open=!active;}host.classList.toggle('focus-lesson-active',active);if(!layout)continue;const panel=$(boardId+'Feedback'),aside=layout.lastElementChild;if(panel&&panel.parentElement!==aside)aside.prepend(panel);if(layout.dataset.focusReady)continue;layout.dataset.focusReady='true';
  const info=layout.lastElementChild;info.classList.add('focus-lesson-panel');const before=[...body.children].slice(0,[...body.children].indexOf(layout));
  const title=before.find(n=>n.tagName==='H3'),progress=before[before.indexOf(title)+1];const record=details(info,bodyId+'Context','누적 기록 · 추가 안내',before.filter(n=>n!==title&&n!==progress));
  // Explanation content exists only when the authoritative mode permits it.
  const paragraphs=[...info.children].filter(n=>n.tagName==='P'||n.tagName==='H4');
  if(boardId==='educationBoard'){
   const prompt=paragraphs.find(n=>n.tagName==='P'&&!n.textContent.startsWith('상대 직전 수:'));if(prompt){prompt.classList.add('focus-lesson-goal');layout.before(prompt);}
  }
  const explanationNodes=paragraphs.filter(n=>n.parentElement===info);if(explanationNodes.length){const short=document.createElement('p');short.className='focus-reason';const text=explanationNodes.at(-1).textContent;short.textContent=text.length>140?text.slice(0,140)+'…':text;info.prepend(short);details(info,bodyId+'Explanation','배치 · 이유 자세히',explanationNodes);}
  // Keep next/hint/move actions before optional logs and long explanations.
  const actions=[...body.children].filter(n=>n.tagName==='BUTTON');const primary=document.createElement('div');primary.className='btn-row';primary.append(...actions);info.insertBefore(primary,record);
  for(const n of [...body.children])if(n!==layout&&n!==title&&n!==progress&&!n.classList.contains('focus-lesson-goal'))record.append(n);
 }}

 let pending=false;
 function sync(){pending=false;applyTraining();arrangeEducational();const reviewReady=typeof v5Review!=='undefined'&&!!v5Review;for(const id of ['reviewExplorer','reviewBranchStart','reviewBoard'])if($(id))$(id).hidden=!reviewReady;const view=document.querySelector('.view.active'),route=window.cmaNavigation?.current();const boardViews=['training','diagnosis','assessment','puzzle','opening','review','rookTrial','guestPractice'];const active=view?.id==='play'||(view?.id==='learn'&&route?.endsWith('/practice'))||(boardViews.includes(view?.id)&&!![...view.querySelectorAll('.board')].find(b=>b.querySelector('.sq')&&!b.closest('[hidden],[inert]')));document.body.classList.toggle('focus-activity',active);document.body.classList.toggle('focus-foundation',active&&view?.id==='learn');}
 const queue=()=>{if(!pending){pending=true;requestAnimationFrame(sync);}};
 new MutationObserver(queue).observe(document.querySelector('.main'),{childList:true,subtree:true});
 for(const v of document.querySelectorAll('.view'))new MutationObserver(queue).observe(v,{attributes:true,attributeFilter:['class']});
 new MutationObserver(queue).observe($('foundationWorkspace'),{attributes:true,attributeFilter:['hidden']});
 window.addEventListener('popstate',queue);sync();
 window.cmaFocusLayout={details,resumeTraining,puzzleReady,prepareLessons:arrangeEducational,refresh:sync,task(id){if(id!==lastTask){trainingChoice=false;lastTask=id;}applyTraining();queue();}};
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
})();
