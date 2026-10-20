/* Main growth cycle; old paths remain available as optional saved practice. */
(()=>{'use strict';
const make=(parent,tag,text,cls)=>{const e=document.createElement(tag);e.textContent=text||'';if(cls)e.className=cls;parent.append(e);return e;};
const home=make(document.getElementById('home'),'section','','card');home.id='journeyActivity';
const training=make(document.getElementById('training'),'section','','card');training.id='trainingCycle';document.getElementById('training').prepend(training);
window.cmaEvidenceLabel=e=>({engine_unavailable:'엔진을 사용할 수 없어 판단하지 못했어요.',diagnosis_busy:'다른 진단을 분석 중이어서 판단을 보류했어요.',engine_busy:'다른 대국·분석에서 엔진을 사용 중이어서 판단을 보류했어요.',insufficient_depth:'탐색 깊이가 기준에 미치지 못했어요.',mate_requires_proof:'메이트 평가를 기물 점수로 바꿔 오답 판정을 하지 않습니다.',uncertain_difference:'차이가 확정 기준 사이에 있어 추가 분석이 필요해요.',similar_evaluation:'짧은 탐색에서 기준 평가와 비슷했어요. 후속 수순은 별도 확인이 필요해요.',large_loss:'짧은 탐색에서 큰 평가 손실을 확인했어요.',engine_failure:'엔진 분석을 끝내지 못했어요.',invalid_position_or_move:'국면 또는 착수 확인이 필요해요.'}[e.reason]||'분석 근거를 확인하세요.');
window.cmaLearningCycle=d=>{
 home.replaceChildren();training.replaceChildren();
 make(home,'h3','진단과 추천 훈련 활동');make(home,'p',d?.activity?`완료한 진단 ${d.activity.diagnoses}회 · 직접 응답한 문항 ${d.activity.answered}개 · 완료한 추천 훈련 ${d.activity.recommended_completed}개`:'로그인하면 진단과 추천 훈련 기록을 확인할 수 있어요.');make(home,'small','아래 대국·퍼즐·과정 집계와 별도로 기록합니다. 반복 클릭은 완료 수를 늘리지 않습니다.');
 make(training,'h3','나의 다음 추천 훈련');const c=d?.cycle;
 make(training,'p',d?.active?'진행 중인 진단을 먼저 이어서 마쳐 주세요.':c?`${c.completed}/5 완료 · ${c.message}`:'진단을 마치면 나에게 맞는 추천 훈련 5개를 준비해요.');
 const b=make(training,'button',d?.active?'진단 이어하기':c?'추천 훈련 목록 보기':'진단 시작','btn primary');b.onclick=()=>tab('diagnosis');
 if(c&&!d?.active){const t=c.tasks.find(t=>!t.completion);if(t){const next=make(training,'button',`다음 과제 · ${t.label}`,'btn');next.onclick=()=>window.learningCycle(c.report_id,t.id);}}
};window.cmaLearningCycle(null);
const activity=document.getElementById('skillBars')?.parentElement;if(activity){activity.querySelector('h2').textContent='대국·퍼즐·과정 활동';activity.querySelector('p').textContent='자유 대국, 퍼즐, 아카데미 완료만 집계합니다. 진단·추천 훈련은 별도 집계를 확인하세요.';}
})();
