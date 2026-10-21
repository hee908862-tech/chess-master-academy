/* V7 deliberate practice and verified-move safety layer */
(function(){
  const ui=(name,tag='button',label='',cls='btn')=>{const e=document.createElement(tag);e.id=name;if(tag==='button'){e.type='button';e.className=cls;e.textContent=label;}return e};
  const playStatus=document.getElementById('gameStatus');
  const actionGroup=document.createElement('div');actionGroup.className='btn-row';actionGroup.style.margin='12px 0';
  const hint=ui('v7Hint','button','💡 추천 수 힌트');const undo=ui('v7Undo','button','↶ 한 수 무르기');
  actionGroup.append(hint,undo);playStatus.parentElement.insertBefore(actionGroup,playStatus.nextSibling);
  hint.onclick=async()=>{
    if(!ready()||gameBusy||gameRestoreBlocked()||!game||game.is_over)return;
    const current=game,identity=token,revision=gameRequest;
    hint.disabled=true;gameBusy=true;window.cmaGameActions?.();
    try{const data=await api('/v7/game/hint?'+new URLSearchParams({...(current?.session_id?{session_id:current.session_id}:{}),...(current?.fen?{expected_fen:current.fen}:{})}));
      if(token!==identity||gameRequest!==revision||game!==current)return;
      document.querySelectorAll('#gameBoard .move-hint').forEach(e=>e.classList.remove('move-hint'));
      document.querySelector(`#gameBoard [aria-label^="${data.move.slice(0,2)} "]`)?.classList.add('move-hint');
      document.querySelector(`#gameBoard [aria-label^="${data.move.slice(2,4)} "]`)?.classList.add('move-hint');
      notice('gameStatus',`추천: ${data.san} (${data.move.slice(0,2)} → ${data.move.slice(2,4)}). 분석: ${data.source}. ${data.note}`);
    }catch(e){if(token===identity&&gameRequest===revision)notice('gameStatus',e.message,'err')}finally{hint.disabled=false;if(gameRequest===revision)gameBusy=false;window.cmaGameActions?.();}
  };
  undo.onclick=async()=>{
    if(!ready()||gameBusy||gameRestoreBlocked()||!game||game.is_over)return;
    const current=game,identity=token,revision=gameRequest;
    window.cmaBoardTools.cancel('gameBoard');cancelPromotion();gameBusy=true;window.cmaGameActions?.();undo.disabled=true;
    try{const data=await api('/v7/game/undo','POST',{session_id:current?.session_id,expected_fen:current?.fen});if(token!==identity||gameRequest!==revision||game!==current)return;playerColor=data.player_color;window.cmaBoardPresentation.transition('gameBoard',data.undone_moves,()=>showGame({...data.board,session_id:data.session_id},`이전 ${data.removed_plies}반수를 되돌렸습니다.`),true);}
    catch(e){if(token===identity&&gameRequest===revision)notice('gameStatus',e.message,'err')}finally{undo.disabled=false;if(gameRequest===revision)gameBusy=false;window.cmaGameActions?.();}
  };
  const openingView=document.getElementById('opening');
  const openingHeader=openingView?.querySelector('.row');
  const family=document.createElement('div');family.className='card';family.innerHTML='<h3 class="heading">오프닝 계보 탐색</h3><p class="subtle">먼저 원류(오프닝 계열)를 고르고 해당 변화의 백·흑 실습을 선택하세요. 현재 목록은 제공된 기본 수순이며, 실제 대국 빈도 통계 순위는 아직 연동되지 않았습니다.</p>';
  const familyList=document.createElement('div');familyList.className='v7-families';family.append(familyList);
  if(openingHeader)openingHeader.after(family);
  const familyNames={italian:'이탈리안 게임',queens:'퀸즈 갬빗',sicilian:'시실리안 디펜스',london:'런던 시스템',carokann:'카로칸',french:'프렌치 디펜스',scotch:'스카치 게임',kingsindian:'킹즈 인디언',ruylopez:'루이 로페즈',english:'잉글리시 오프닝'};
  async function loadFamilies(){if(!token)return;
    try{const lines=await api('/openings');familyList.replaceChildren();
     Object.entries(familyNames).forEach(([key,label])=>{
      const variants=lines.filter(x=>x.id.startsWith(key+'_'));
      if(!variants.length)return;
      const details=document.createElement('details');details.className='v7-family';
      const head=document.createElement('summary');head.textContent=`${label} · ${variants.length}개 실습`;details.append(head);
      for(const line of variants){const btn=ui('','button',line.name,'btn tiny');btn.style.margin='6px';btn.onclick=()=>{document.getElementById('openingSelect').value=line.id;document.getElementById('openingBegin').click();openingView.scrollIntoView({behavior:'smooth'})};details.append(btn)};
      familyList.append(details);
     });
    }catch(e){familyList.textContent='계보 목록을 불러오지 못했습니다: '+e.message}
  }
  document.querySelectorAll('[data-tab="opening"]').forEach(x=>x.addEventListener('click',loadFamilies));
})();
