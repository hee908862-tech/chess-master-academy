/* Presentation only. Original stored text, verdicts, lines and controller nodes survive. */
(()=>{'use strict';
const $=id=>document.getElementById(id);
window.cmaPlainText=value=>String(value??'').replace(/같은 파일/g,'같은 세로줄(파일)').replace(/([a-h])파일/g,'$1 세로줄(파일)').replace(/백랭크/g,'맨 뒤 가로줄(백랭크)').replace(/디스커버드 어택/g,'기물을 옮겨 뒤의 공격을 여는 수(디스커버드 어택)');
window.cmaExplanation=(host,original)=>{const p=document.createElement('p'),plain=window.cmaPlainText(original);p.textContent=plain;host.append(p);if(plain!==original){const d=document.createElement('details'),s=document.createElement('summary'),raw=document.createElement('p');s.textContent='용어를 풀어 쓴 표시 · 저장된 원문 보기';raw.textContent=original;d.append(s,raw);host.append(d);}return p;};
function install(){
 const fold=(host,id,label,nodes)=>window.cmaFocusLayout.details(host,id,label,nodes);
 const diagnosticRow=$('journeyRefresh').parentElement,diagnosticBar=$('diagnosis').querySelector('.feature-toolbar');
 const diagnosticTitle=diagnosticRow.querySelector('h2');diagnosticBar.prepend(diagnosticTitle);diagnosticBar.append($('journeyRefresh'));diagnosticRow.remove();
 // Selection is kept apart from execution, without replacing handlers or controller nodes.
 const review=$('review'),layout=review.querySelector('.two'),panel=$('reviewGameSelect').parentElement;
 const picker=fold(review,'reviewSelection','다른 대국 선택 · 분석',[panel.querySelector(':scope > .row'),$('reviewGameSelect'),$('reviewLoad')]);
 layout.before(picker);picker.open=true;
 const status=$('reviewStatus'),brief=document.createElement('p');brief.id='reviewReasonBrief';brief.className='notice';brief.setAttribute('role','status');panel.prepend(brief);
 const original=fold(panel,'reviewOriginal','착수 해설 원문 · 당시 분석',[status]);panel.prepend(original);panel.prepend(brief);
 const controls=$('reviewPrev').parentElement,boardPanel=$('reviewBoard').parentElement;let hadReview=false;
 function reviewState(){const ready=typeof v5Review!=='undefined'&&!!v5Review;controls.hidden=!ready;boardPanel.hidden=!ready;if(ready!==hadReview){picker.open=!ready;hadReview=ready;}const text=status.textContent,plain=window.cmaPlainText(text);brief.textContent=plain+(plain!==text?' · 용어를 풀어 쓴 표시 (아래 원문 확인)':'');original.hidden=!ready||plain===text;}
 new MutationObserver(reviewState).observe(status,{childList:true,subtree:true,characterData:true});reviewState();
 // Keep the active training goal above the board and the original explanation available.
 const raw=$('learningExplanation'),plain=document.createElement('div');plain.id='learningPlainExplanation';raw.before(plain);
 const rawDetails=fold($('learningDetails'),'learningOriginalExplanation','저장된 해설 원문',[raw]);plain.after(rawDetails);
 function trainingText(){const text=raw.textContent,display=window.cmaPlainText(text),changed=display!==text;plain.textContent=display;rawDetails.hidden=!changed;raw.hidden=false;plain.dataset.reworded=String(changed);if(changed){const note=document.createElement('p');note.className='subtle';note.textContent='용어만 풀어 쓴 표시입니다. 원래 해설과 당시 판정은 보존됩니다.';plain.append(note);}}
 new MutationObserver(trainingText).observe(raw,{childList:true,subtree:true,characterData:true});trainingText();
 // The current goal is already in the board brief; detailed original wording is still reachable.
 const goalDetails=fold($('learningDetails'),'learningOriginalGoal','과제 안내 원문',[$('learningGoal')]);
 // Give review controls a real accessible name; labels survive responsive layouts.
 $('reviewGameSelect').setAttribute('aria-label','분석할 저장 대국');
 // Existing freely selectable course cards become scan-friendly without new content.
 for(const b of document.querySelectorAll('#academyHub button')){const parts=b.textContent.split(' · ');if(parts.length<2)continue;const title=document.createElement('strong'),description=document.createElement('span');title.textContent=parts.shift();description.textContent=parts.join(' · ');b.replaceChildren(title,description);}
 // Reuse the information hierarchy already separating account, settings and destructive controls.
 const profile=$('profileInformation');for(const node of [...profile.children]){if(node.id==='profileNextAction'||node.tagName==='DETAILS')continue;const title=node.querySelector('h3,h2');if(title&&/이전 버전 진단|AI 대국 규칙별 성적/.test(title.textContent)){const d=fold(profile,'','기록 상세 · '+title.textContent,[node]);d.classList.add('clarity-records');}}
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
})();
