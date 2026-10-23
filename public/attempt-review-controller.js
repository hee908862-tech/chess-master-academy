/* Explicit revalidation is a separate owned write, never a new submitted answer. */
(()=>{'use strict';
const requests=new Map();
async function revalidate(ref,initial=false){
 const identity=token,key=identity+'|'+ref.report_id+'|'+ref.item_id;
 let request_id=requests.get(key);if(!request_id){request_id=crypto.randomUUID();requests.set(key,request_id);}
 const record=await api('/journey/revalidate','POST',{...ref,request_id});
 if(identity!==token)throw Error('계정이 바뀌어 이전 결과를 표시하지 않습니다.');
 if(record.status==='pending'){
  if(Date.now()-Date.parse(record.requested_at)>30000)requests.delete(key);
  throw Error('앞선 재검증 결과 미확인 · 원본은 보존됩니다. 저장 상태를 확인한 뒤 다시 시도하세요.');
 }
 requests.delete(key);
 if(initial){await window.cmaJourney.load();if(identity!==token)throw Error('계정이 바뀌어 이전 결과를 표시하지 않습니다.');return window.cmaJourney.state()?.initial_profile?.attempt_evidence;}
 const result=await api('/journey/attempt-evidence/'+encodeURIComponent(ref.report_id));if(identity!==token)throw Error('계정이 바뀌어 이전 결과를 표시하지 않습니다.');return result;
}
function render(host,data,initial=false){const identity=token;window.cmaAttemptEvidence?.render(host,data,{onRevalidate:ref=>revalidate(ref,initial),onTrain:!initial||data.baseline_reviewed?ref=>{if(identity===token)window.learningFromDiagnosis(ref.report_id,ref.item_id);}:null});}
async function mount(host,report){
 const identity=token;const box=document.createElement('section');const primary=host.querySelector(':scope > .solving-score');if(primary)primary.after(box);else host.prepend(box);box.textContent='전체 시도 근거를 확인하고 있습니다…';
 try{const data=await api('/journey/attempt-evidence/'+encodeURIComponent(report.id));if(identity!==token||!box.isConnected)return;
  data.original={score:report.internal_skill?.score??report.skill_index?.score??null,max:3000,version:report.score_version||report.scoring_version,label:'당시 선택 관찰 수행점수 · 원본 보존'};
  render(box,data);
 }catch(e){if(identity!==token||!box.isConnected)return;box.textContent='전체 시도 조회 실패 · 기존 결과는 보존됩니다. '+e.message;const b=document.createElement('button');b.className='btn';b.textContent='근거 다시 확인';b.onclick=()=>{box.remove();mount(host,report);};box.append(b);}
}
window.cmaAttemptReview={mount,render};
})();
