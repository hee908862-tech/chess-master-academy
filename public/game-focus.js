/* Move existing controls; preserve their handlers, server state and clock semantics. */
(()=>{'use strict';
function install(){
 const $=id=>document.getElementById(id),play=$('play');
 const make=(p,tag,text,cls)=>{const e=document.createElement(tag);if(text)e.textContent=text;if(cls)e.className=cls;p.append(e);return e;};
 const originalHeader=play.querySelector(':scope > .row'),toolbar=play.querySelector('.feature-toolbar');
 const title=originalHeader.querySelector('h2');title.id='gameFocusTitle';title.tabIndex=-1;toolbar.querySelector('span').replaceWith(title);
 const settings=make(play,'details',null,'game-settings');settings.id='gameSettings';settings.open=!game||game.is_over;
 const settingSummary=make(settings,'summary','대국 설정');settingSummary.id='gameSettingsSummary';
 const fields=make(settings,'div',null,'game-setting-fields');
 for(const [id,label] of [['playerColor','내 기물 색'],['aiLevel','AI 난도'],['timeMode','대국 시간']]){const l=make(fields,'label',label);l.append($(id));}
 fields.append($('newGame'));make(settings,'p','AI 단계는 엔진 설정입니다. 외부 Elo로 검증된 범위가 없어 숫자 레이팅을 표시하지 않습니다. 1–2는 입문 연습, 3–5는 기본 대국, 6–10은 더 강한 탐색 설정입니다. 실제 난도는 기기·시간 설정에 따라 달라집니다.','subtle');const calibration=make(settings,'details');make(calibration,'summary','난이도 수치 보정 기준');make(calibration,'p','동일 엔진·탐색 시간·시간제한에서 표본 대국과 상대 집단을 고정해 승률 및 불확실성을 측정한 뒤 별도 버전으로 범위를 제공해야 합니다. 현재 단계 숫자를 Elo로 환산하지 않습니다.');const engine=make(settings,'p',null,'subtle');engine.append($('engineBadge'));
 const stage=make(play,'div',null,'game-focus-stage');const boardPanel=make(stage,'section',null,'game-focus-board');boardPanel.setAttribute('aria-label','대국 보드와 차례');
 const state=make(boardPanel,'div',null,'game-turn-clock');state.append($('turnIndicator'),$('gameClock'));
 boardPanel.append($('gameBoard'));
 const controls=make(stage,'section',null,'game-focus-controls');controls.setAttribute('aria-label','대국 핵심 조작');
 const actions=make(controls,'div',null,'game-primary-actions');actions.append($('v7Hint'),$('v7Undo'));
 controls.append($('gameActionReason'),$('gameStatus'));if($('gameRestoreRetry'))controls.append($('gameRestoreRetry'));$('gameStatus').setAttribute('role','status');
 const boardTools=play.querySelector('.board-tools');
 // The existing live region remains visible even when tool options are folded.
 const premoveStatus=boardTools.querySelector(':scope > small');premoveStatus.id='gamePremoveStatus';controls.append(premoveStatus);
 const tools=make(controls,'details',null,'game-secondary-tools');tools.id='gameTools';make(tools,'summary','프리무브 · 대국 도구');tools.append(boardTools);
 const danger=make(tools,'div',null,'game-danger-actions');danger.append($('resign'));danger.append(originalHeader.querySelector('[data-go="review"]'));
 const information=make(controls,'details',null,'game-information');make(information,'summary','대국 정보 · 규칙 안내');information.append($('gameMatchup'));
 const oldPanels=play.querySelector(':scope > .two');const oldInfo=oldPanels.querySelector(':scope > .card:not(.board-panel)');
 for(const child of [...oldInfo.children])information.append(child);
 oldPanels.remove();originalHeader.remove();toolbar.after(settings);settings.after(stage);
 let previouslyActive=!!game&&!game.is_over,previousSession=game?.session_id;
 function update(){const active=!!game&&!game.is_over;play.classList.toggle('game-in-progress',active);
  if(active&&(!previouslyActive||(game.session_id&&game.session_id!==previousSession))){const inside=settings.contains(document.activeElement);settings.open=false;if(inside)title.focus({preventScroll:true});}
  previouslyActive=active;previousSession=game?.session_id;
  const values=['playerColor','aiLevel','timeMode'].map(id=>$(id).selectedOptions[0]?.textContent||'');
  settingSummary.textContent=(active?'새 대국 설정':'대국 설정')+' · '+values.join(' · ');
 }
 const previousActions=window.cmaGameActions;window.cmaGameActions=()=>{previousActions?.();update();};
 for(const id of ['playerColor','aiLevel','timeMode'])$(id).addEventListener('change',update);
 update();
 const previousTab=tab;tab=function(id){const previous=document.querySelector('.view.active')?.id;if(id==='play'&&previous==='play')return;previousTab(id);document.body.classList.toggle('game-focus-active',id==='play');if(previous!==id){
  const current=document.getElementById(id);const heading=current?.querySelector('h1,h2');if(current){current.tabIndex=-1;if(heading&&!current.hasAttribute('aria-label'))current.setAttribute('aria-label',heading.textContent);current.focus({preventScroll:true});}
  // Cancel an in-flight smooth scroll from the old screen, after the layout changes.
  scrollTo({top:0,left:0,behavior:'instant'});
 }};
 document.body.classList.toggle('game-focus-active',play.classList.contains('active'));
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
})();
