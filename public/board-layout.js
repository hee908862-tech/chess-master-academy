/* Reorder existing DOM only. No navigation, session, or request hooks. */
(()=>{'use strict';
function install(){const $=id=>document.getElementById(id);
 $('training').querySelector('.learning-layout').after($('learningSaved'));
 const learning=$('learningBoard');learning.after($('learningControls'),$('learningMessage'),$('learningGoal'),$('learningLink'));
 const journey=$('journeyBoard');journey.after($('journeyGoal'));const actions=$('journeyNext').parentElement;journey.after(actions);
 // Put optional repertoire introduction after the currently selected opening board.
 const repertoire=$('repertoire');if(repertoire&&$('openingStudy'))$('openingStudy').after(repertoire);
 const tools=$('studyTools');$('studyOpeningBoard').after(tools);tools.after($('studySaveStatus'));
 const scope=$('openingStudy').querySelector(':scope > p');if(scope&&scope.id===''){const d=document.createElement('details');d.className='board-scope';const sum=document.createElement('summary');sum.textContent='강의 범위·자료 안내';d.append(sum,scope);$('openingStudy').append(d);}
 // Feedback from a different identity is never retained in a replacement account.
 const previousAuth=auth;auth=async function(...args){window.cmaFeedback.clearAll();return previousAuth(...args);};$('signout').addEventListener('click',()=>window.cmaFeedback.clearAll());
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
})();
