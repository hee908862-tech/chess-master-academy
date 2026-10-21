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
 let pending=false;
 function sync(){pending=false;const view=document.querySelector('.view.active'),route=window.cmaNavigation?.current();const active=view?.id==='play'||(view?.id==='learn'&&route==='learn/basics/practice');document.body.classList.toggle('focus-activity',active);document.body.classList.toggle('focus-foundation',active&&view?.id==='learn');}
 const queue=()=>{if(!pending){pending=true;requestAnimationFrame(sync);}};
 for(const v of document.querySelectorAll('.view'))new MutationObserver(queue).observe(v,{attributes:true,attributeFilter:['class']});
 new MutationObserver(queue).observe($('foundationWorkspace'),{attributes:true,attributeFilter:['hidden']});
 window.addEventListener('popstate',queue);sync();
 window.cmaFocusLayout={details,refresh:queue};
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
})();
