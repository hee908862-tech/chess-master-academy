const $=id=>document.getElementById(id);
const FILES='abcdefgh'.split('');
const PIECES={P:'♙',N:'♘',B:'♗',R:'♖',Q:'♕',K:'♔',p:'♟',n:'♞',b:'♝',r:'♜',q:'♛',k:'♚'};
const BOARD_THEMES={
  walnut:{label:'Walnut',light:'#f0e6d5',dark:'#ba9268',border:'#2b3547'},
  slate:{label:'Slate',light:'#dde4ef',dark:'#6d7d95',border:'#253248'},
  forest:{label:'Forest',light:'#edf3e7',dark:'#75946e',border:'#2a3d35'},
  midnight:{label:'Midnight',light:'#d9def0',dark:'#586a94',border:'#1d2540'}
};
const PIECE_THEMES={classic:'Classic 3D',royal:'Royal 3D',unicode:'Unicode'};
const SOUND_THEMES={classic:'Classic Wood',soft:'Soft Click',digital:'Digital'};
const DEFAULT_PREFS={boardTheme:'walnut',pieceTheme:'classic',soundTheme:'classic',soundOn:true};
let prefs=loadPrefs();
let token=localStorage.getItem('chess_token')||sessionStorage.getItem('chess_token')||'';
let gameRequest=0;
let gameRestoreGeneration=0,gameOwner='',gameRestoreState=token?'pending':'ready';
// Only discard the previous account's client-side work; never write/reset its server game.
function resetGameAccount(){
 ++gameRequest;++gameRestoreGeneration;gameBusy=false;game=null;gameOwner='';selectedGame=null;
 window.cmaBoardTools?.cancel('gameBoard');cancelPromotion();setGameClock(null);
 gameRestoreFeedback(token?'pending':'ready',token?'계정을 확인하고 저장된 대국을 불러오고 있습니다.':'로그인 후 저장된 대국을 확인하거나 새 대국을 시작하세요.');drawGame();
}
function gameRestoreBlocked(){return !!token&&gameRestoreState!=='ready';}
function gameRestoreFeedback(state,message){
 gameRestoreState=state;
 $('gameBoard').style.visibility=state!=='ready'&&(!game||gameOwner!==token)?'hidden':'';
 $('gameBoard').inert=gameRestoreBlocked();
 $('gameBoard').setAttribute('aria-busy',String(state==='pending'));
 $('newGame').disabled=gameRestoreBlocked();
 let retry=$('gameRestoreRetry');if(!retry){retry=document.createElement('button');retry.id='gameRestoreRetry';retry.className='btn';retry.textContent='대국 상태 다시 확인';retry.onclick=()=>refresh();$('gameStatus').after(retry);}
 retry.hidden=state!=='error';
 if(message){notice('gameStatus',message,state==='error'?'err':'');$('turnIndicator').textContent=state==='ready'?'로그인 후 대국을 시작하세요.':state==='error'?'대국 상태 확인 필요':'저장된 대국 확인 중…';}
 window.cmaGameActions?.();
}
let user=null,game=null,selectedGame=null,playerColor='white',gameBusy=false,gameClock=null,gameClockAt=0,puzzleItems=[],puzzleIdx=0,selectedPuzzle=null,audioCtx=null;
const lessons=[
 ['rules','기초 규칙과 체크메이트 이해','체스는 상대 킹을 체크메이트하는 게임입니다. 각 기물의 이동 방식을 정확히 이해하는 것이 가장 먼저입니다. 킹은 한 칸씩, 퀸은 가로·세로·대각선, 룩은 가로·세로, 비숍은 대각선, 나이트는 L자, 폰은 전진과 대각 포획이라는 점을 기억하세요. 체크는 상대 킹이 공격받는 상태이고, 체크메이트는 어떤 합법 수로도 이를 벗어날 수 없는 상태입니다.'],
 ['capture','기물 가치와 교환 감각','일반적으로 폰=1, 나이트·비숍=3, 룩=5, 퀸=9 정도의 가치를 둡니다. 하지만 실제 대국에서는 체크메이트 위협, 킹 안전, 기물 활동성 때문에 단순 수치보다 상황이 더 중요합니다. 먼저 손해 보는 포획을 줄이고, 잡은 뒤 다시 잡히는 교환이 유리한지 계산하는 습관을 들이세요.'],
 ['tactics','기본 전술 5종','포크, 핀, 스큐어, 발견공격, 더블어택은 가장 자주 등장하는 전술입니다. 체크를 동반하는 전술은 상대 응수 수를 줄이므로 특히 강력합니다. 퍼즐을 풀 때는 상대 킹의 안전, 느슨하게 지켜진 기물, 같은 대각선과 파일에 놓인 기물 관계를 먼저 살피세요.'],
 ['calculation','수읽기 시작하기','후보수를 2~3개 고른 뒤 각각 상대의 가장 강한 응수를 찾습니다. 내가 공격하는 것만 보지 말고 상대의 체크와 기물 포획도 점검하세요. 매 수를 두기 전 체크·잡기·위협 순서로 검토하는 습관을 만드세요.'],
 ['endgame','킹·폰 엔드게임 기초','엔드게임에서는 킹이 적극적인 기물이 됩니다. 폰 승격을 위해 킹으로 전진로를 보호하고, 상대 킹과의 오포지션을 활용해 원하는 칸을 확보합니다. 폰을 밀기 전 상대 킹이 승격 칸에 먼저 도착할지 계산하세요.'],
 ['opening','오프닝 4대 원칙','중앙 칸을 다투고, 나이트·비숍 같은 경량 기물을 빠르게 전개하며, 가능한 한 일찍 캐슬링해 킹을 보호하세요. 초반에 같은 기물을 불필요하게 여러 번 움직이거나 퀸을 일찍 꺼내 공격받는 일을 피하세요.'],
 ['review','대국 복기 습관','대국이 끝나면 결정적인 실수 3개를 찾아보세요. 왜 그 수를 뒀는지 적고, 다른 후보수를 비교하며, 비슷한 상황을 다시 풀어봅니다. 엔진 수치만 외우기보다 상대의 위협을 놓친 이유를 파악하세요.']
];
function loadPrefs(){try{return {...DEFAULT_PREFS,...JSON.parse(localStorage.getItem('cma_prefs')||'{}')}}catch(e){return {...DEFAULT_PREFS}}}
function savePrefs(){localStorage.setItem('cma_prefs',JSON.stringify(prefs))}
function applyTheme(){const t=BOARD_THEMES[prefs.boardTheme]||BOARD_THEMES.walnut;const root=document.documentElement.style;root.setProperty('--board-light',t.light);root.setProperty('--board-dark',t.dark);root.setProperty('--board-border',t.border);$('currentBoardTheme')&&($('currentBoardTheme').textContent=`체스판: ${t.label}`);$('currentPieceTheme')&&($('currentPieceTheme').textContent=`기물: ${PIECE_THEMES[prefs.pieceTheme]}`);$('currentSoundTheme')&&($('currentSoundTheme').textContent=`착수음: ${SOUND_THEMES[prefs.soundTheme]}`);if($('toggleSound'))$('toggleSound').textContent=`착수음 ${prefs.soundOn?'켜짐':'꺼짐'}`;if($('boardThemeSelect'))$('boardThemeSelect').value=prefs.boardTheme;if($('pieceThemeSelect'))$('pieceThemeSelect').value=prefs.pieceTheme;if($('moveSoundSelect'))$('moveSoundSelect').value=prefs.soundTheme;drawBoard('homeBoard',fromFen('r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 1'));if(game)drawGame();else drawBoard('gameBoard',fromFen(chessStart));if(puzzleItems.length)drawPuzzle();else drawBoard('puzzleBoard',fromFen(chessStart));}
function notice(id,text,type=''){const e=$(id);if(!e)return;e.className=(id==='gameStatus'||id==='puzzleStatus'?'notice ':'status ')+type;e.textContent=text;}
async function api(path,method='GET',body){const opts={method,headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})}};if(body!==undefined)opts.body=JSON.stringify(body);let resp;const controller=new AbortController(),legacyTimed=['/v8/assessment/start','/v8/assessment/status'].includes(path),timed=path==='/game'||legacyTimed||/^\/(journey|learning|me|onboarding|profile)(\/|$)/.test(path);if(timed)opts.signal=controller.signal;const timeout=timed?setTimeout(()=>controller.abort(),legacyTimed?60000:30000):null;try{resp=await fetch('/api'+path,opts)}catch(e){throw Error(e.name==='AbortError'?'서버 응답 시간이 초과되었습니다. 저장 상태를 다시 확인하세요.':'서버와 연결할 수 없습니다. 서버를 실행하거나 Render 주소로 접속하세요.')}finally{clearTimeout(timeout)}const data=await resp.json();if(!resp.ok){const error=Error(typeof data.detail==='string'?data.detail:(Array.isArray(data.detail)?data.detail.map(x=>x.msg).join(' / '):data.detail?.message||'요청이 실패했습니다.'));error.detail=data.detail;error.status=resp.status;throw error;}return data;}
function tab(id){const changed=document.querySelector('.view.active')?.id!==id;if(changed){window.cmaBoardTools?.cancelAll();cancelPromotion();}document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===id));document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id===id));if(changed)scrollTo({top:0,behavior:'instant'});if(id==='home'||id==='profile'){refreshSummaryOnly();if(id==='profile')renderWinrates();}}
document.querySelectorAll('[data-tab]').forEach(b=>{b.onclick=()=>tab(b.dataset.tab);});
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>tab(b.dataset.go)));
$('loginNav').onclick=()=>tab('profile');
function fromFen(fen){const out={};fen.split(' ')[0].split('/').forEach((row,r)=>{let c=0;for(const ch of row){if(/\d/.test(ch))c+=Number(ch);else out[FILES[c++]+(8-r)]=ch}});return out;}
function pieceAsset(piece){if(prefs.pieceTheme==='unicode')return null;const color=piece===piece.toUpperCase()?'w':'b';const type=piece.toUpperCase();return `/assets/assets/pieces/${prefs.pieceTheme}/${color}${type}.svg`;}
function renderPiece(piece){const wrap=document.createElement('div');wrap.className='piece-wrap';if(!piece)return wrap;const src=pieceAsset(piece);if(src){const img=document.createElement('img');img.className='piece-img';img.src=src;img.alt='';img.draggable=false;wrap.appendChild(img);}else{const span=document.createElement('span');span.className='piece-char';span.textContent=PIECES[piece]||'';wrap.appendChild(span);}return wrap;}
function drawBoard(id,positions,opts={}){const el=$(id);if(!el)return;window.cmaBoardPresentation?.beforeDraw(id,positions,!!opts.flip);el.innerHTML='';for(let ri=0;ri<8;ri++)for(let fi=0;fi<8;fi++){const r=opts.flip?ri:7-ri,f=opts.flip?7-fi:fi;const square=FILES[f]+(r+1),piece=positions[square];const btn=document.createElement('button');btn.type='button';btn.className='sq '+((r+f)%2===0?'dark ':'')+(piece?(piece===piece.toUpperCase()?'white-piece ':'black-piece '):'');const names={p:'폰',n:'나이트',b:'비숍',r:'룩',q:'퀸',k:'킹'};btn.setAttribute('aria-label',square+' '+(piece?(piece===piece.toUpperCase()?'백 ':'흑 ')+names[piece.toLowerCase()]:'빈 칸')+(opts.selected===square?' · 선택됨':'')+(opts.opponent?.includes(square)?' · 상대 직전 수':'')+(opts.last?.includes(square)?' · 마지막 착수':'')+(opts.targets?.some(t=>t.to===square)?' · 이동 가능':''));btn.setAttribute('aria-pressed',String(opts.selected===square));if(opts.selected===square)btn.classList.add('selected');if(opts.targets?.some(t=>t.to===square))btn.classList.add(piece?'capture':'target');if(opts.last?.includes(square))btn.classList.add('last');if(opts.opponent?.includes(square))btn.classList.add('opponent-move');if(opts.hint?.includes(square))btn.classList.add('move-hint');btn.appendChild(renderPiece(piece));if(fi===0||ri===7){const coord=document.createElement('span');coord.className='square-coordinate';coord.setAttribute('aria-hidden','true');coord.textContent=ri===7?FILES[f]+(fi===0?r+1:''):r+1;btn.appendChild(coord);}if(opts.onClick)btn.onclick=()=>opts.onClick(square);else btn.disabled=true;el.appendChild(btn)}window.cmaBoardTools?.decorate(id);window.cmaBoardPresentation?.remember(id,positions);window.cmaFeedback?.decorate(id)}
function ensureAudio(){if(!prefs.soundOn)return null;const Ctx=window.AudioContext||window.webkitAudioContext;if(!Ctx)return null;if(!audioCtx)audioCtx=new Ctx();if(audioCtx.state==='suspended')audioCtx.resume();return audioCtx;}
function tone({freq=440,type='triangle',dur=.08,vol=.05,start=0,slideTo=null}={}){const ctx=ensureAudio();if(!ctx)return;const osc=ctx.createOscillator();const gain=ctx.createGain();osc.type=type;osc.frequency.setValueAtTime(freq,ctx.currentTime+start);if(slideTo)osc.frequency.linearRampToValueAtTime(slideTo,ctx.currentTime+start+dur);gain.gain.setValueAtTime(0,ctx.currentTime+start);gain.gain.linearRampToValueAtTime(vol,ctx.currentTime+start+.01);gain.gain.exponentialRampToValueAtTime(0.0001,ctx.currentTime+start+dur);osc.connect(gain).connect(ctx.destination);osc.start(ctx.currentTime+start);osc.stop(ctx.currentTime+start+dur+.02);}
function playMoveSound(kind='move'){const style=prefs.soundTheme;if(!prefs.soundOn)return; if(style==='classic'){tone({freq:kind==='capture'?540:420,type:'triangle',dur:.09,vol:.06,slideTo:kind==='capture'?390:330});tone({freq:kind==='capture'?320:260,type:'sine',dur:.12,vol:.03,start:.02,slideTo:kind==='capture'?210:200});}
else if(style==='soft'){tone({freq:kind==='capture'?780:620,type:'sine',dur:.05,vol:.035});tone({freq:kind==='capture'?520:430,type:'triangle',dur:.07,vol:.02,start:.015});}
else{tone({freq:kind==='capture'?900:760,type:'square',dur:.04,vol:.022});tone({freq:kind==='capture'?640:520,type:'square',dur:.05,vol:.018,start:.03});}}
let loginDestination=null;
function ready(destination){if(!token){loginDestination=destination||document.querySelector('.view.active')?.id||'home';tab('profile');notice('accountStatus','이 기능은 기록 저장을 위해 로그인이 필요합니다. 로그인 후 선택한 화면으로 돌아갑니다. 개인 코드와 PIN으로 로그인하거나 가입하세요.','');return false}return true}
let refreshGeneration=0;
async function refresh(){const accountToken=token,request=++refreshGeneration;++gameRestoreGeneration;if(!token){$('userBadge').textContent='게스트';gameRestoreFeedback('ready');return}$('userBadge').textContent='계정 확인 중…';if(!game||gameOwner!==token)gameRestoreFeedback('pending','계정을 확인하고 저장된 대국을 불러오고 있습니다.');try{const result=await api('/me');if(token!==accountToken||request!==refreshGeneration)return;user=result;renderSummary();await resumeGame();if(token!==accountToken||request!==refreshGeneration)return;renderWinrates();if(!window.practiceModeInitialized)await loadPuzzles();}catch(err){if(token!==accountToken||request!==refreshGeneration)return;if(err.status===401){token='';localStorage.removeItem('chess_token');sessionStorage.removeItem('chess_token');}if(!game||gameOwner!==token)gameRestoreFeedback('error',err.status===401?'로그인이 만료됐습니다. 다시 로그인해 저장된 대국을 확인하세요.':'계정 확인 실패 · 저장된 대국 여부를 아직 확인하지 못했습니다. '+err.message);notice('accountStatus',err.message,'err')}}
let authGeneration=0;window.cmaCancelAuth=()=>{++authGeneration;loginDestination=null;};
async function auth(mode){const request=++authGeneration,account=token;const code=$('codeField').value.trim(),pin=$('pinField').value;try{const result=await api(mode==='signup'?'/register':'/login','POST',{code,pin});if(request!==authGeneration||token!==account)return;token=result.token;resetGameAccount();localStorage.setItem('chess_token',token);$('pinField').value='';notice('accountStatus','로그인되었습니다. 모든 기록은 서버에 저장됩니다.','ok');await refresh();if(request!==authGeneration)return;const destination=loginDestination||'home';loginDestination=null;window.cmaAuthNavigating=true;try{tab(destination)}finally{window.cmaAuthNavigating=false}}catch(e){if(request===authGeneration)notice('accountStatus',e.message,'err')}}
let logoutGeneration=0;
$('signup').onclick=()=>auth('signup');$('signin').onclick=()=>auth('signin');$('signout').onclick=async()=>{const account=token,request=++logoutGeneration;window.cmaBoardTools.cancelAll();try{if(account)await api('/logout','POST')}catch(e){if(token===account&&request===logoutGeneration)notice('accountStatus','로그아웃하지 못했습니다. 다시 시도해 주세요. '+e.message,'err');return;}if(token!==account||request!==logoutGeneration)return;token='';user=null;localStorage.removeItem('chess_token');sessionStorage.removeItem('chess_token');resetGameAccount();$('userBadge').textContent='게스트';notice('accountStatus','로그아웃했습니다.','');tab('profile')};
function setGameClock(clock){gameClock=clock||null;gameClockAt=Date.now();drawClock()}
function drawClock(){const e=$('gameClock');if(!e)return;
 if(!gameClock||gameClock.mode==='unlimited'||gameClock.white_ms==null){e.textContent='시간 무제한';return;}
 const ms={white:gameClock.white_ms,black:gameClock.black_ms};
 if(game&&game.turn&&gameClockAt&&!(game.is_over)){
  const side=game.turn;ms[side]=Math.max(0,ms[side]-(Date.now()-gameClockAt));
 }
 const fmt=x=>`${Math.floor(Math.max(0,x)/60000)}:${String(Math.floor(Math.max(0,x)%60000/1000)).padStart(2,'0')}`;
 e.textContent=`백 ${fmt(ms.white)} · 흑 ${fmt(ms.black)}`;
 if(game&&!game.is_over&&!gameBusy&&ms[game.turn]<=0&&!window.cmaTimeoutPending){window.cmaTimeoutPending=true;resumeGame().finally(()=>{window.cmaTimeoutPending=false})}
}
setInterval(drawClock,1000);
function renderWinrates(){if(!token||!$('gameModeStats'))return;
 api('/game/stats-by-mode').then(data=>{const labels={unlimited:'무제한',rapid:'래피드 10+5',blitz:'블리츠 3+2',bullet:'불릿 1+0'};
  $('gameModeStats').replaceChildren();for(const [mode,val] of Object.entries(data.rules||{})){
   const row=document.createElement('div');row.className='v8-result-item';
   row.textContent=`${labels[mode]||mode} · ${val.games}판 · ${val.wins}승 ${val.draws}무 ${val.losses}패 · 승률 ${val.win_rate==null?'집계 전':val.win_rate+'%'}`;
   $('gameModeStats').append(row);
  }
 }).catch(e=>{$('gameModeStats').textContent=e.message});
}
function showGame(board,msg){gameOwner=token;game=board;selectedGame=null;drawGame();notice('gameStatus',msg|| (board.is_over?'대국이 종료됐습니다.':board.turn===playerColor?'당신의 차례입니다.':'AI가 생각하고 있습니다.'),board.is_over?'ok':'');$('turnIndicator').textContent=board.is_over?('대국 종료 · '+board.result):(board.turn===playerColor?'당신의 차례 ('+(playerColor==='white'?'백':'흑')+')':'AI 차례')}
function drawGame(){window.cmaGameActions?.();$('gameMatchup').textContent=game?(playerColor==='black'?'흑 ♚ vs AI ♔':'백 ♔ vs AI ♚'):'플레이 색상 선택 후 새 대국을 시작하세요.';if(!game){drawBoard('gameBoard',fromFen(chessStart),{flip:playerColor==='black'});return}drawBoard('gameBoard',game.squares,{flip:playerColor==='black',selected:selectedGame,targets:selectedGame?game.legal.filter(m=>m.from===selectedGame):[],last:game.last_move?[game.last_move.slice(0,2),game.last_move.slice(2,4)]:[],onClick:onGameSquare})}
const chessStart='rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';
async function resumeGame(){const identity=token;if(gameBusy)return;const request=++gameRestoreGeneration,revision=gameRequest;const current=()=>token===identity&&request===gameRestoreGeneration&&revision===gameRequest;gameRestoreFeedback('pending','저장된 대국을 확인하고 있습니다. 아직 새 대국을 시작하지 마세요.');window.cmaBoardTools?.cancel('gameBoard');try{const r=await api('/game');if(!current())return;gameRestoreFeedback('ready');if(r.player_color){playerColor=r.player_color;$('playerColor').value=playerColor;}if(r.active){playerColor=r.player_color||'white';$('playerColor').value=playerColor;showGame({...r.board,session_id:r.session_id},'진행 중인 대국을 불러왔습니다.');setGameClock(r.clock);}else if(r.timeout){game=r.board?{...r.board,is_over:true,result:r.result}:null;setGameClock(r.clock);if(game)showGame({...game,is_over:true,result:r.result},'시간 초과로 대국이 종료됐습니다. · '+(r.result==='win'?'승리':'패배'));else notice('gameStatus','시간 초과로 대국이 종료됐습니다.','ok');$('turnIndicator').textContent='대국 종료 · 시간패';await refreshSummaryOnly();renderWinrates();}else {game=null;drawGame();$('turnIndicator').textContent='새 대국을 시작하세요.';notice('gameStatus','색상과 시간을 선택하고 새 대국을 시작하세요.')}}catch(e){if(current())gameRestoreFeedback('error','대국 조회 실패 · 저장된 대국 여부를 아직 확인하지 못했습니다. '+e.message)}}
// Smooth piece translation: the static board updates immediately while a moving overlay bridges old and new cells.
function animateBoardTransition(boardId,from,to,paint){return window.cmaBoardPresentation.transition(boardId,from+to,paint);}

let promotionCancel=null;
function cancelPromotion(){if(promotionCancel){const cancel=promotionCancel;promotionCancel=null;cancel();}}
// Shared promotion picker. UCI suffix is chosen by the learner (q/r/b/n).
async function choosePromotion(sqFrom,sqTo,piece,moves){
  const available=(moves||[]).filter(m=>{
    const str=typeof m==='string'?m:(m.from+m.to+(m.promotion||''));
    return str.slice(0,2)===sqFrom&&str.slice(2,4)===sqTo;
  }).map(m=>typeof m==='string'?m.slice(4):(m.promotion||''))
    .filter(x=>['q','r','b','n'].includes(x.toLowerCase()));
  const needs=(piece||'').toLowerCase()==='p'&&(sqTo[1]==='1'||sqTo[1]==='8');
  if(!needs)return '';
  if(!available.length)return 'q';
  cancelPromotion();return new Promise(resolve=>{
    let modal=document.getElementById('cmaPromotionModal');
    if(!modal){
      modal=document.createElement('div');modal.id='cmaPromotionModal';modal.className='cma-promotion-modal';
      modal.setAttribute('role','dialog');modal.setAttribute('aria-modal','true');
      document.body.appendChild(modal);
    }
    const origin=document.activeElement;
    const finish=value=>{promotionCancel=null;modal.hidden=true;if(origin?.isConnected&&!origin.disabled)origin.focus();resolve(value);};
    promotionCancel=()=>finish(null);
    modal.onclick=e=>{if(e.target===modal)cancelPromotion();};
    modal.onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();cancelPromotion();}if(e.key==='Tab'){const list=[...modal.querySelectorAll('button')];if(e.shiftKey&&document.activeElement===list[0]){e.preventDefault();list.at(-1).focus();}else if(!e.shiftKey&&document.activeElement===list.at(-1)){e.preventDefault();list[0].focus();}}};
    const turn=piece===piece.toUpperCase()?'w':'b';
    modal.replaceChildren();
    const panel=document.createElement('div');panel.className='cma-promotion-panel';
    const title=document.createElement('h3');title.textContent='어떤 기물로 승격할까요?';title.id='cmaPromotionTitle';modal.setAttribute('aria-labelledby',title.id);panel.appendChild(title);
    const caption=document.createElement('p');caption.textContent='퀸 · 룩 · 비숍 · 나이트 중 선택하세요.';panel.appendChild(caption);
    const buttons=document.createElement('div');buttons.className='cma-promotion-choices';
    for(const [code,name,notation] of [['q','퀸','Q'],['r','룩','R'],['b','비숍','B'],['n','나이트','N']]){
      if(!available.includes(code))continue;
      const btn=document.createElement('button');btn.type='button';btn.className='btn';
      const icon=document.createElement('span');icon.className='cma-promotion-glyph';icon.textContent=(typeof PIECES!=='undefined'?PIECES[turn==='w'?notation:notation.toLowerCase()]:notation)||notation;
      btn.append(icon,document.createTextNode(name));
      btn.onclick=()=>finish(code);buttons.append(btn);
    }
    panel.append(buttons);const close=document.createElement('button');close.className='btn';close.textContent='승격 선택 취소';close.onclick=()=>cancelPromotion();panel.append(close);modal.append(panel);modal.hidden=false;buttons.querySelector('button')?.focus();
  });
}

function playerClockExpired(){return gameClock?.mode!=='unlimited'&&gameClock?.[playerColor+'_ms']!=null&&gameClock[playerColor+'_ms']-(Date.now()-gameClockAt)<=0}
async function onGameSquare(s){
 if(gameRestoreBlocked())return;
 if(gameBusy){window.cmaBoardTools?.pick('gameBoard',s);return;}
 if(!ready()||!game||game.turn!==playerColor||game.is_over||gameBusy)return;
 if(playerClockExpired()){window.cmaBoardTools.cancel('gameBoard');await resumeGame();return;}
 ensureAudio();
 if(selectedGame===s){selectedGame=null;drawGame();return;}
 const chosen=selectedGame;
 if(chosen&&game.legal.some(m=>m.from===chosen&&m.to===s)){
  const from=chosen,prior=game,request=++gameRequest,accountToken=token,viewVersion=window.cmaBoardTools.version();gameBusy=true;window.cmaGameActions?.();
  const promotion=await choosePromotion(from,s,prior.squares[from],prior.legal);
  if(promotion===null||prior!==game||accountToken!==token||viewVersion!==window.cmaBoardTools.version()){if(request===gameRequest&&accountToken===token){gameBusy=false;window.cmaGameActions?.();}return;}
  if(playerClockExpired()){gameBusy=false;window.cmaGameActions?.();window.cmaBoardTools.cancel('gameBoard');await resumeGame();return;}
  selectedGame=null;
  const capture=Boolean(prior.squares[s]) || ((prior.squares[from]||'').toLowerCase()==='p'&&from[0]!==s[0]);
  // Optimistic board state: the learner sees their piece moving before the server calculates its reply.
  const optimistic={...prior,squares:{...prior.squares},legal:[],last_move:from+s,turn:playerColor==='white'?'black':'white'};
  optimistic.squares[s]=optimistic.squares[from];delete optimistic.squares[from];
  // En passant captures a pawn on the adjacent file, not on the destination square.
  if((prior.squares[from]||'').toLowerCase()==='p'&&from[0]!==s[0]&&!prior.squares[s]){
   const taken=s[0]+from[1];delete optimistic.squares[taken];
  }
  // Promotion appears immediately during the optimistic move.
  if((prior.squares[from]||'').toLowerCase()==='p'&&(s[1]==='8'||s[1]==='1'))
   optimistic.squares[s]=playerColor==='white'?promotion.toUpperCase():promotion.toLowerCase();
  // For castling also move rook on the temporary local board.
  if((optimistic.squares[s]||'').toLowerCase()==='k'&&Math.abs(FILES.indexOf(from[0])-FILES.indexOf(s[0]))===2){
   const rank=from[1];
   if(s[0]==='g'){optimistic.squares['f'+rank]=optimistic.squares['h'+rank];delete optimistic.squares['h'+rank];}
   else{optimistic.squares['d'+rank]=optimistic.squares['a'+rank];delete optimistic.squares['a'+rank];}
  }
  if(prior.session_id)window.cmaBoardTools.begin('gameBoard',request,optimistic.squares,playerColor);else window.cmaBoardTools.unavailable('gameBoard');
  animateBoardTransition('gameBoard',from,s,()=>{game=optimistic;drawGame()});playMoveSound(capture?'capture':'move');
  const target=document.querySelector(`#gameBoard [aria-label^="${s} "]`);if(target)target.classList.add('moving-to');
  $('turnIndicator').textContent='AI 응답 대기 중';notice('gameStatus','착수했습니다. AI 응수를 기다리는 중입니다...');
  try{
   const r=await api('/game/move','POST',{from_sq:from,to_sq:s,promotion:promotion||'q',session_id:prior.session_id,expected_fen:prior.fen});if(request!==gameRequest||accountToken!==token)return;setGameClock(r.clock);
   const updateFinal=()=>showGame(r.finished?{...r.board,is_over:true,result:r.timeout?(r.outcome==='win'?'시간패 승리':'시간패 패배'):r.board.result}:{...r.board,session_id:r.session_id},r.timeout?'시간 초과로 대국이 종료됐습니다.':r.finished?'대국 종료: '+r.board.result:'AI 응수가 완료됐습니다.');
   if(r.ai_move){const aFrom=r.ai_move.slice(0,2),aTo=r.ai_move.slice(2,4);animateBoardTransition('gameBoard',aFrom,aTo,updateFinal);playMoveSound('move');}else updateFinal();
   await refreshSummaryOnly();if(r.finished)renderWinrates();
  }catch(err){if(request===gameRequest&&accountToken===token){window.cmaBoardTools.cancel('gameBoard');game=prior;drawGame();notice('gameStatus',err.message,'err')}}
  finally{if(request===gameRequest&&accountToken===token){gameBusy=false;window.cmaGameActions?.();}}
  const queued=window.cmaBoardTools.take('gameBoard',request,game?.legal,accountToken===token&&request===gameRequest&&game?.session_id===prior.session_id&&game?.turn===playerColor&&!game?.is_over&&!playerClockExpired());
  if(queued){selectedGame=queued.from;await onGameSquare(queued.to);}
  return;
 }
 selectedGame=game.legal.some(m=>m.from===s)?s:null;drawGame();
}
function renderSummary(){$('userBadge').textContent=user.code;$('homeGames').textContent=user.stats.games+'판';$('homePuzzles').textContent=user.stats.solved+'개';$('homeGrade').textContent='학습 중';$('profileGames').textContent=user.stats.games;$('profilePuzzles').textContent=user.stats.solved;$('profileLessons').textContent=(user.stats.courses_completed||0)+user.state.completed_lessons.length;$('profileAdvice').textContent=user.stats.first_try_total?`공개 퍼즐 첫 시도 정확도 ${Math.round(user.stats.first_try_correct/user.stats.first_try_total*100)}%. ${user.stats.solved<3?'기초 전술을 더 연습해 보세요.':'좋습니다. 이제 계산 문제와 실전 대국을 병행하세요.'}`:'처음에는 퍼즐 3개와 AI 대국 1판으로 현재 학습 패턴을 확인하세요.';$('recommendText').textContent=user.stats.solved<3?'추천: 기초 규칙 확인 → 기초 퍼즐 3개 → AI 대국 1판':'추천: 전술 복습 → 수읽기 2~3수 → 엔드게임 → AI 대국 복기';$('skillBars').replaceChildren(...[['대국',user.stats.games+'판'],['해결한 퍼즐',user.stats.solved+'개'],['마친 과정',(user.stats.courses_completed||0)+'개']].map(([label,value])=>{const item=document.createElement('p');item.className='activity-total';item.textContent=label+' · '+value;return item;}));$('engineBadge').textContent=user.engine==='stockfish'?'Stockfish':'기본 체스 AI';$('engineExplanation').textContent=user.engine==='stockfish'?'서버 Stockfish 엔진으로 응수합니다.':'현재는 기본 미니맥스 AI로 플레이합니다. 서버에 Stockfish 바이너리를 연결하면 자동으로 교체됩니다.';renderLessons();}
let summaryRequest=0;
async function refreshSummaryOnly(){if(!token)return;const request=++summaryRequest,accountToken=token;try{const data=await api('/me');if(request!==summaryRequest||token!==accountToken)return;user=data;renderSummary();}catch(e){}}
$('newGame').onclick=async()=>{
 if(!ready()||gameBusy||gameRestoreBlocked())return;
 window.cmaBoardTools.cancel('gameBoard');cancelPromotion();const request=++gameRequest,accountToken=token;gameBusy=true;window.cmaGameActions?.();ensureAudio();
 try{const requestedColor=$('playerColor').value;const r=await api('/game/new','POST',{color:requestedColor,difficulty:Number($('aiLevel')?.value||5),time_mode:$('timeMode')?.value||'unlimited'});
 if(request!==gameRequest||accountToken!==token)return;
 playerColor=r.player_color||requestedColor;showGame({...r.board,session_id:r.session_id},r.message);setGameClock(r.clock);
 }catch(e){if(request===gameRequest&&accountToken===token)notice('gameStatus',e.message,'err')}finally{if(request===gameRequest&&accountToken===token)gameBusy=false;window.cmaGameActions?.();}
};
$('resign').onclick=async()=>{
 if(!ready()||!game||game.is_over||gameBusy||gameRestoreBlocked())return;if(!confirm('현재 대국을 기권하시겠습니까?'))return;
 window.cmaBoardTools.cancel('gameBoard');const request=++gameRequest,accountToken=token;gameBusy=true;window.cmaGameActions?.();
 try{await api('/game/resign','POST');if(request!==gameRequest||accountToken!==token)return;game=null;setGameClock(null);drawGame();$('turnIndicator').textContent='대국 종료 · 기권';notice('gameStatus','기권으로 대국이 종료됐습니다.');await refreshSummaryOnly();renderWinrates()}
 catch(e){if(request===gameRequest&&accountToken===token)notice('gameStatus',e.message,'err')}finally{if(request===gameRequest&&accountToken===token){gameBusy=false;window.cmaGameActions?.();}}
};
function currentPuzzle(){return puzzleItems[puzzleIdx]}
async function loadPuzzles(){try{puzzleItems=await api('/puzzles');$('puzzleSelect').innerHTML='';puzzleItems.forEach((p,i)=>{const o=document.createElement('option');o.value=i;o.textContent=`${i+1}. ${p.theme} · ${p.difficulty}`;$('puzzleSelect').appendChild(o)});showPuzzle()}catch(e){notice('puzzleStatus',e.message,'err')}}
function showPuzzle(){const p=currentPuzzle();if(!p)return;selectedPuzzle=null;$('puzzleSelect').value=puzzleIdx;$('puzzleLevel').textContent=p.difficulty;$('puzzleSolved').textContent=p.solved?'✓ 해결 완료':'미해결';$('puzzleTitle').textContent=p.theme;$('puzzleDesc').textContent=p.description;notice('puzzleStatus','백의 최선의 수를 찾아보세요. 말과 목적지를 차례로 누릅니다.');drawPuzzle()}
function drawPuzzle(){const p=currentPuzzle();if(!p)return;drawBoard('puzzleBoard',fromFen(p.fen),{selected:selectedPuzzle,onClick:onPuzzleSquare})}
async function onPuzzleSquare(s){const p=currentPuzzle();if(!p||!ready())return;ensureAudio();const board=fromFen(p.fen);if(selectedPuzzle===s){selectedPuzzle=null;drawPuzzle();return}if(!selectedPuzzle){if(!board[s]||board[s]!==board[s].toUpperCase()){notice('puzzleStatus','백 기물을 먼저 선택하세요.');return}selectedPuzzle=s;drawPuzzle();return}const from=selectedPuzzle;selectedPuzzle=null;drawPuzzle();try{const r=await api('/puzzle/solve','POST',{puzzle_id:p.id,move:from+s});if(r.correct)playMoveSound(board[s]?'capture':'move');notice('puzzleStatus',r.explanation,r.correct?'ok':'err');if(r.correct){p.solved=true;$('puzzleSolved').textContent='✓ 해결 완료'}await refreshPuzzleStats()}catch(e){notice('puzzleStatus',e.message,'err')}}
async function refreshPuzzleStats(){try{const m=await api('/me');user=m;$('homePuzzles').textContent=m.stats.solved+'개';$('profilePuzzles').textContent=m.stats.solved}catch(e){}}
$('puzzleSelect').onchange=e=>{puzzleIdx=+e.target.value;showPuzzle()};$('nextPuzzle').onclick=()=>{puzzleIdx=(puzzleIdx+1)%Math.max(1,puzzleItems.length);showPuzzle()};$('puzzleReset').onclick=showPuzzle;$('puzzleHint').onclick=()=>notice('puzzleStatus','힌트: 체크, 잡기, 직접적인 위협 순서로 살펴보세요.');
let selectedLesson='rules';function renderLessons(){const done=user?.state?.completed_lessons||[];$('lessonList').innerHTML=lessons.map(([id,title],i)=>`<div class="lesson"><div><b>${i+1}. ${title}</b><small>${done.includes(id)?'✓ 완료':'미완료 · 읽기 학습'}</small></div><button class="btn tiny" data-lesson="${id}">학습하기</button></div>`).join('');document.querySelectorAll('[data-lesson]').forEach(b=>b.onclick=()=>openLesson(b.dataset.lesson));}
function openLesson(id){selectedLesson=id;const lesson=lessons.find(l=>l[0]===id);$('lessonHeading').textContent=lesson[1];$('lessonBody').textContent=lesson[2];notice('lessonStatus','읽고 이해했다면 완료 버튼을 눌러주세요.');}
$('completeLesson').onclick=async()=>{if(!ready())return;try{await api('/lesson/complete','POST',{lesson_id:selectedLesson});notice('lessonStatus','학습 완료 내역이 서버에 저장되었습니다.','ok');await refresh()}catch(e){notice('lessonStatus',e.message,'err')}};
function initSettings(){if($('boardThemeSelect'))$('boardThemeSelect').onchange=e=>{prefs.boardTheme=e.target.value;savePrefs();applyTheme();};if($('pieceThemeSelect'))$('pieceThemeSelect').onchange=e=>{prefs.pieceTheme=e.target.value;savePrefs();applyTheme();};if($('moveSoundSelect'))$('moveSoundSelect').onchange=e=>{prefs.soundTheme=e.target.value;savePrefs();applyTheme();};if($('toggleSound'))$('toggleSound').onclick=()=>{prefs.soundOn=!prefs.soundOn;savePrefs();applyTheme();if(prefs.soundOn)playMoveSound('move');};if($('testSound'))$('testSound').onclick=()=>playMoveSound('move');}
renderLessons();openLesson('rules');initSettings();applyTheme();refresh();
