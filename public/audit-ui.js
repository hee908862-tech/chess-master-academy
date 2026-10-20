/* Main destinations fit without horizontal scrolling; the native dialog owns focus. */
(()=>{'use strict';
const make=(tag,text)=>{const n=document.createElement(tag);n.textContent=text;return n;};
for(const b of document.querySelectorAll('.nav [data-tab="profile"]'))b.textContent='기록';
const side=document.querySelector('.nav');for(const id of ['home','learn','diagnosis','training','profile','play','puzzle','opening','review','help']){const item=side?.querySelector(`[data-tab="${id}"]`);if(item)side.append(item);}
const nav=document.querySelector('.mobile-nav');nav.setAttribute('aria-label','주요 메뉴');nav.replaceChildren();
for(const [id,label] of [['home','홈'],['learn','아카데미'],['diagnosis','진단'],['training','훈련실']]){const b=make('button',label);b.dataset.tab=id;b.onclick=()=>tab(id);nav.append(b);}
const more=make('button','더보기');more.id='moreNavigation';more.setAttribute('aria-haspopup','dialog');nav.append(more);
const dialog=document.createElement('dialog');dialog.id='moreNavigationDialog';dialog.setAttribute('aria-labelledby','moreNavigationTitle');const title=make('h2','더보기');title.id='moreNavigationTitle';dialog.append(title);
const close=make('button','닫기');close.className='btn';close.onclick=()=>dialog.close();dialog.append(close);
for(const [id,label] of [['profile','기록'],['play','AI 대국'],['puzzle','퍼즐'],['opening','오프닝 연구실'],['review','대국 복기'],['help','도움말']]){const b=make('button',label);b.className='btn';b.onclick=()=>{dialog.close();tab(id);document.querySelector('#'+id+' h2')?.scrollIntoView({block:'start'});};dialog.append(b);}
dialog.addEventListener('keydown',event=>{if(event.key!=='Tab')return;const buttons=[...dialog.querySelectorAll('button:not(:disabled)')];if(!event.shiftKey&&document.activeElement===buttons.at(-1)){event.preventDefault();buttons[0].focus();}else if(event.shiftKey&&document.activeElement===buttons[0]){event.preventDefault();buttons.at(-1).focus();}});
document.body.append(dialog);more.onclick=()=>dialog.showModal();dialog.addEventListener('close',()=>more.focus());
const resume=make('button','현재 학습 이어하기');resume.className='btn';resume.id='homeResumeLearning';resume.onclick=()=>tab('training');document.getElementById('journeyHome').append(resume);
const performance=document.getElementById('gamePerformance');if(performance){const details=document.createElement('details');details.className='card';details.append(make('summary','대국 지표 · 내 수 품질과 앱 내부 레이팅'));performance.before(details);details.append(performance);}
const reason=make('p','새 대국을 시작하면 기권과 힌트를 사용할 수 있습니다.');reason.id='gameActionReason';reason.className='subtle';document.getElementById('gameStatus').after(reason);
window.cmaGameActions=()=>{const active=!!game&&!game.is_over;for(const id of ['resign','v7Hint','v7Undo']){const b=document.getElementById(id);if(!b)continue;const why=!active?'진행 중인 대국이 없습니다.':gameBusy?'대국 응답을 기다리고 있습니다.':id==='v7Undo'&&!game.ply?'아직 무를 착수가 없습니다.':'';b.disabled=!!why;b.title=why;b.setAttribute('aria-describedby','gameActionReason');}reason.textContent=!active?'새 대국을 시작하면 기권과 힌트를 사용할 수 있습니다.':gameBusy?'응답 처리 중에는 대국 액션을 기다려 주세요.':!game.ply?'착수 후 한 수 무르기를 사용할 수 있습니다.':'힌트와 무르기는 도움 사용 기록에 남습니다.';};window.cmaGameActions();
})();
