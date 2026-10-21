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
 const trainingLayout=training.querySelector('.learning-layout');trainingLayout.before(library);
 for(const n of [$('learningSetup'),$('learningSaved'),$('learningCards').closest('details'),$('learningSkills').closest('details'),$('learningAttempts').closest('details'),$('trainingCycle')])if(n)library.append(n);
 const trainNav=document.createElement('div');trainNav.className='btn-row focus-selection';training.querySelector('.feature-toolbar').after(trainNav);
 let lastTask=null,trainingChoice=false,requestedChoice=false;
 const selectButton=document.createElement('button');selectButton.className='btn';selectButton.textContent='훈련 선택 · 저장 활동 · 기록';selectButton.onclick=()=>{trainingChoice=true;applyTraining();library.tabIndex=-1;library.focus({preventScroll:true});scrollTo({top:0,behavior:'instant'});};trainNav.append(selectButton);
 const resumeButton=document.createElement('button');resumeButton.className='btn';resumeButton.textContent='현재 훈련으로';resumeButton.onclick=()=>{trainingChoice=false;applyTraining();$('learningTitle').tabIndex=-1;$('learningTitle').focus({preventScroll:true});scrollTo({top:0,behavior:'instant'});};trainNav.append(resumeButton);
 library.addEventListener('click',e=>{if(e.target.closest('button'))requestedChoice=true;});
 function applyTraining(){const active=!!$('learningBoard').querySelector('.sq')||$('learningMode').textContent==='읽기 전용 · 개념';const pathHost=active&&!trainingChoice?training.querySelector('.learning-aside'):library;if($('learningRoute').parentElement!==pathHost)pathHost.prepend($('learningRoute'));library.hidden=active&&!trainingChoice;trainingLayout.hidden=!active||trainingChoice;resumeButton.hidden=!active||!trainingChoice;selectButton.hidden=!active||trainingChoice;}
 // Existing layout hook must not move setup/records out of this explicit selection screen.
 window.cmaBoardLayout.training=()=>applyTraining();
 const openingPick=$('openingStudy').querySelector('.study-pickers');const openingChooser=details($('openingStudy'),'focusOpeningSelection','강의 · 모드 · 방향 선택',[openingPick]);$('openingStudy').querySelector('.study-layout').before(openingChooser);openingChooser.open=true;
 openingPick.addEventListener('change',()=>{scrollTo({top:0,behavior:'instant'});});
 const puzzleSetup=$('v9PuzzleRoot').querySelector('.v9-controls'),puzzleChooser=details($('v9PuzzleRoot'),'focusPuzzleSelection','다른 문제 · 주제와 난도',[ $('v9CatalogStatus'),puzzleSetup]);$('v9PuzzleRoot').querySelector('.v9-layout').before(puzzleChooser);puzzleChooser.open=true;
 const originalPuzzlePaint=new MutationObserver(()=>{if($('v9PuzzleBoard').querySelector('.sq')&&puzzleChooser.open&&!puzzleChooser.contains(document.activeElement))puzzleChooser.open=false;});originalPuzzlePaint.observe($('v9PuzzleBoard'),{childList:true});
 let pending=false;
 function sync(){pending=false;applyTraining();const reviewReady=typeof v5Review!=='undefined'&&!!v5Review;for(const id of ['reviewExplorer','reviewBranchStart'])if($(id))$(id).hidden=!reviewReady;const view=document.querySelector('.view.active'),route=window.cmaNavigation?.current();const boardViews=['training','diagnosis','assessment','puzzle','opening','review','rookTrial','guestPractice'];const active=view?.id==='play'||(view?.id==='learn'&&route?.endsWith('/practice'))||(boardViews.includes(view?.id)&&!![...view.querySelectorAll('.board')].find(b=>b.querySelector('.sq')&&!b.closest('[hidden],[inert]')));document.body.classList.toggle('focus-activity',active);document.body.classList.toggle('focus-foundation',active&&view?.id==='learn');}
 const queue=()=>{if(!pending){pending=true;requestAnimationFrame(sync);}};
 new MutationObserver(queue).observe(document.querySelector('.main'),{childList:true,subtree:true});
 for(const v of document.querySelectorAll('.view'))new MutationObserver(queue).observe(v,{attributes:true,attributeFilter:['class']});
 new MutationObserver(queue).observe($('foundationWorkspace'),{attributes:true,attributeFilter:['hidden']});
 window.addEventListener('popstate',queue);sync();
 window.cmaFocusLayout={details,refresh:sync,task(id){if(id!==lastTask){if(requestedChoice||lastTask===null)trainingChoice=false;lastTask=id;requestedChoice=false;}applyTraining();queue();}};
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
})();
