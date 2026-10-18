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
let user=null,game=null,selectedGame=null,playerColor='white',gameBusy=false,puzzleItems=[],puzzleIdx=0,selectedPuzzle=null,audioCtx=null;
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
async function api(path,method='GET',body){const opts={method,headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})}};if(body!==undefined)opts.body=JSON.stringify(body);let resp;try{resp=await fetch('/api'+path,opts)}catch(e){throw Error('서버와 연결할 수 없습니다. 서버를 실행하거나 Render 주소로 접속하세요.')}const data=await resp.json();if(!resp.ok)throw Error(typeof data.detail==='string'?data.detail:(Array.isArray(data.detail)?data.detail.map(x=>x.msg).join(' / '):'요청이 실패했습니다.'));return data;}
function tab(id){document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===id));document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id===id));scrollTo({top:0,behavior:'smooth'});}
document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>tab(b.dataset.tab)));
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>tab(b.dataset.go)));
$('loginNav').onclick=()=>tab('profile');
function fromFen(fen){const out={};fen.split(' ')[0].split('/').forEach((row,r)=>{let c=0;for(const ch of row){if(/\d/.test(ch))c+=Number(ch);else out[FILES[c++]+(8-r)]=ch}});return out;}
function pieceAsset(piece){if(prefs.pieceTheme==='unicode')return null;const color=piece===piece.toUpperCase()?'w':'b';const type=piece.toUpperCase();return `/assets/assets/pieces/${prefs.pieceTheme}/${color}${type}.svg`;}
function renderPiece(piece){const wrap=document.createElement('div');wrap.className='piece-wrap';if(!piece)return wrap;const src=pieceAsset(piece);if(src){const img=document.createElement('img');img.className='piece-img';img.src=src;img.alt='';img.draggable=false;wrap.appendChild(img);}else{const span=document.createElement('span');span.className='piece-char';span.textContent=PIECES[piece]||'';wrap.appendChild(span);}return wrap;}
function drawBoard(id,positions,opts={}){const el=$(id);if(!el)return;el.innerHTML='';for(let ri=0;ri<8;ri++)for(let fi=0;fi<8;fi++){const r=opts.flip?ri:7-ri,f=opts.flip?7-fi:fi;const square=FILES[f]+(r+1),piece=positions[square];const btn=document.createElement('button');btn.type='button';btn.className='sq '+((r+f)%2===0?'dark ':'')+(piece?(piece===piece.toUpperCase()?'white-piece ':'black-piece '):'');btn.setAttribute('aria-label',square+' '+(piece||''));if(opts.selected===square)btn.classList.add('selected');if(opts.targets?.some(t=>t.to===square))btn.classList.add(piece?'capture':'target');if(opts.last?.includes(square))btn.classList.add('last');btn.appendChild(renderPiece(piece));if(opts.onClick)btn.onclick=()=>opts.onClick(square);else btn.disabled=true;el.appendChild(btn)}}
function ensureAudio(){if(!prefs.soundOn)return null;const Ctx=window.AudioContext||window.webkitAudioContext;if(!Ctx)return null;if(!audioCtx)audioCtx=new Ctx();if(audioCtx.state==='suspended')audioCtx.resume();return audioCtx;}
function tone({freq=440,type='triangle',dur=.08,vol=.05,start=0,slideTo=null}={}){const ctx=ensureAudio();if(!ctx)return;const osc=ctx.createOscillator();const gain=ctx.createGain();osc.type=type;osc.frequency.setValueAtTime(freq,ctx.currentTime+start);if(slideTo)osc.frequency.linearRampToValueAtTime(slideTo,ctx.currentTime+start+dur);gain.gain.setValueAtTime(0,ctx.currentTime+start);gain.gain.linearRampToValueAtTime(vol,ctx.currentTime+start+.01);gain.gain.exponentialRampToValueAtTime(0.0001,ctx.currentTime+start+dur);osc.connect(gain).connect(ctx.destination);osc.start(ctx.currentTime+start);osc.stop(ctx.currentTime+start+dur+.02);}
function playMoveSound(kind='move'){const style=prefs.soundTheme;if(!prefs.soundOn)return; if(style==='classic'){tone({freq:kind==='capture'?540:420,type:'triangle',dur:.09,vol:.06,slideTo:kind==='capture'?390:330});tone({freq:kind==='capture'?320:260,type:'sine',dur:.12,vol:.03,start:.02,slideTo:kind==='capture'?210:200});}
else if(style==='soft'){tone({freq:kind==='capture'?780:620,type:'sine',dur:.05,vol:.035});tone({freq:kind==='capture'?520:430,type:'triangle',dur:.07,vol:.02,start:.015});}
else{tone({freq:kind==='capture'?900:760,type:'square',dur:.04,vol:.022});tone({freq:kind==='capture'?640:520,type:'square',dur:.05,vol:.018,start:.03});}}
function ready(){if(!token){tab('profile');notice('accountStatus','처음 이용한다면 개인 코드와 PIN으로 가입하세요.','');return false}return true}
async function refresh(){if(!token){$('userBadge').textContent='게스트';return}try{user=await api('/me');$('userBadge').textContent=user.code;$('homeGames').textContent=user.stats.games+'판';$('homePuzzles').textContent=user.stats.solved+'개';$('homeGrade').textContent='학습 중';$('profileGames').textContent=user.stats.games;$('profilePuzzles').textContent=user.stats.solved;$('profileLessons').textContent=user.state.completed_lessons.length;$('profileAdvice').textContent=user.stats.puzzles?`퍼즐 정답률 ${Math.round(user.stats.solved/user.stats.puzzles*100)}%. ${user.stats.solved<3?'기초 전술을 더 연습해 보세요.':'좋습니다. 이제 계산 문제와 실전 대국을 병행하세요.'}`:'처음에는 퍼즐 3개와 AI 대국 1판으로 현재 학습 패턴을 확인하세요.';$('recommendText').textContent=user.stats.solved<3?'추천: 기초 규칙 확인 → 기초 퍼즐 3개 → AI 대국 1판':'추천: 전술 복습 → 수읽기 2~3수 → 엔드게임 → AI 대국 복기';$('skillBars').innerHTML=[['퍼즐 정확도',user.stats.puzzles?Math.round(user.stats.solved/user.stats.puzzles*100):0],['퍼즐 도전',Math.min(100,user.stats.puzzles*10)],['대국 경험',Math.min(100,user.stats.games*10)],['학습 진도',Math.round(user.state.completed_lessons.length/lessons.length*100)]].map(([label,v])=>`<div class="skill"><span>${label}</span><div class="bar"><div class="fill" style="width:${v}%"></div></div><b>${v}%</b></div>`).join('');$('engineBadge').textContent=user.engine==='stockfish'?'Stockfish':'기본 체스 AI';$('engineExplanation').textContent=user.engine==='stockfish'?'서버 Stockfish 엔진으로 응수합니다.':'현재는 기본 미니맥스 AI로 플레이합니다. 서버에 Stockfish 바이너리를 연결하면 자동으로 교체됩니다.';renderLessons();await resumeGame();if(!window.practiceModeInitialized)await loadPuzzles();}catch(err){token='';localStorage.removeItem('chess_token');sessionStorage.removeItem('chess_token');notice('accountStatus',err.message,'err')}}
async function auth(mode){const code=$('codeField').value.trim(),pin=$('pinField').value;try{const result=await api(mode==='signup'?'/register':'/login','POST',{code,pin});token=result.token;localStorage.setItem('chess_token',token);$('pinField').value='';notice('accountStatus','로그인되었습니다. 모든 기록은 서버에 저장됩니다.','ok');await refresh();tab('home')}catch(e){notice('accountStatus',e.message,'err')}}
$('signup').onclick=()=>auth('signup');$('signin').onclick=()=>auth('signin');$('signout').onclick=async()=>{try{if(token)await api('/logout','POST')}catch(e){}token='';user=null;localStorage.removeItem('chess_token');sessionStorage.removeItem('chess_token');$('userBadge').textContent='게스트';notice('accountStatus','로그아웃했습니다.','');tab('profile')};
function showGame(board,msg){game=board;selectedGame=null;drawGame();notice('gameStatus',msg|| (board.is_over?'대국이 종료됐습니다.':board.turn===playerColor?'당신의 차례입니다.':'AI가 생각하고 있습니다.'),board.is_over?'ok':'');$('turnIndicator').textContent=board.is_over?('대국 종료 · '+board.result):(board.turn===playerColor?'당신의 차례 ('+(playerColor==='white'?'백':'흑')+')':'AI 차례')}
function drawGame(){if(!game){drawBoard('gameBoard',fromFen(chessStart),{flip:playerColor==='black'});return}drawBoard('gameBoard',game.squares,{flip:playerColor==='black',selected:selectedGame,targets:selectedGame?game.legal.filter(m=>m.from===selectedGame):[],last:game.last_move?[game.last_move.slice(0,2),game.last_move.slice(2,4)]:[],onClick:onGameSquare})}
const chessStart='rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';
async function resumeGame(){try{const r=await api('/game');if(r.active){playerColor=r.player_color||'white';$('playerColor').value=playerColor;showGame(r.board,'진행 중인 대국을 불러왔습니다.');}else {game=null;drawGame();$('turnIndicator').textContent='새 대국을 시작하세요.'}}catch(e){notice('gameStatus',e.message,'err')}}
// Smooth piece translation: the static board updates immediately while a moving overlay bridges old and new cells.
function animateBoardTransition(boardId,from,to,paint){
 const boardEl=$(boardId);
 const src=boardEl?.querySelector(`[aria-label^="${from} "]`);
 const dst=boardEl?.querySelector(`[aria-label^="${to} "]`);
 const piece=src?.querySelector('.piece-wrap');
 if(!src||!dst||!piece||!piece.firstElementChild){paint();return;}
 const srcBox=piece.getBoundingClientRect(),dstBox=dst.getBoundingClientRect();
 const ghost=piece.cloneNode(true);
 ghost.style.cssText=`position:fixed;z-index:1000;pointer-events:none;margin:0;left:${srcBox.left}px;top:${srcBox.top}px;width:${srcBox.width}px;height:${srcBox.height}px`;
 document.body.appendChild(ghost);paint();
 const rendered=boardEl.querySelector(`[aria-label^="${to} "] .piece-wrap`);
 if(rendered)rendered.style.opacity='0';
 const animation=ghost.animate([{transform:'translate(0,0)'},{transform:`translate(${dstBox.left-srcBox.left}px,${dstBox.top-srcBox.top}px)`}],{duration:210,easing:'cubic-bezier(.22,.68,.17,1)',fill:'forwards'});
 animation.finished.catch(()=>{}).then(()=>{ghost.remove();if(rendered)rendered.style.opacity='';});
}
async function onGameSquare(s){
 if(!ready()||!game||game.turn!==playerColor||game.is_over||gameBusy)return;
 ensureAudio();
 if(selectedGame===s){selectedGame=null;drawGame();return;}
 const chosen=selectedGame;
 if(chosen&&game.legal.some(m=>m.from===chosen&&m.to===s)){
  const from=chosen,prior=game;
  gameBusy=true;selectedGame=null;
  const capture=Boolean(prior.squares[s]);
  // Optimistic board state: the learner sees their piece moving before the server calculates its reply.
  const optimistic={...prior,squares:{...prior.squares},legal:[],last_move:from+s,turn:playerColor==='white'?'black':'white'};
  optimistic.squares[s]=optimistic.squares[from];delete optimistic.squares[from];
  // For castling also move rook on the temporary local board.
  if((optimistic.squares[s]||'').toLowerCase()==='k'&&Math.abs(FILES.indexOf(from[0])-FILES.indexOf(s[0]))===2){
   const rank=from[1];
   if(s[0]==='g'){optimistic.squares['f'+rank]=optimistic.squares['h'+rank];delete optimistic.squares['h'+rank];}
   else{optimistic.squares['d'+rank]=optimistic.squares['a'+rank];delete optimistic.squares['a'+rank];}
  }
  animateBoardTransition('gameBoard',from,s,()=>{game=optimistic;drawGame()});playMoveSound(capture?'capture':'move');
  const target=document.querySelector(`#gameBoard [aria-label^="${s} "]`);if(target)target.classList.add('moving-to');
  notice('gameStatus','착수했습니다. AI 응수를 기다리는 중입니다...');
  try{
   const r=await api('/game/move','POST',{from_sq:from,to_sq:s,promotion:'q'});
   const updateFinal=()=>showGame(r.board,r.finished?'대국 종료: '+r.board.result:'AI 응수가 완료됐습니다.');
   if(r.ai_move){const aFrom=r.ai_move.slice(0,2),aTo=r.ai_move.slice(2,4);animateBoardTransition('gameBoard',aFrom,aTo,updateFinal);playMoveSound('move');}else updateFinal();
   await refreshSummaryOnly();
  }catch(err){game=prior;drawGame();notice('gameStatus',err.message,'err')}
  finally{gameBusy=false}
  return;
 }
 selectedGame=game.legal.some(m=>m.from===s)?s:null;drawGame();
}
async function refreshSummaryOnly(){if(!token)return;try{user=await api('/me');$('homeGames').textContent=user.stats.games+'판';$('profileGames').textContent=user.stats.games;}catch(e){}}
$('newGame').onclick=async()=>{if(!ready())return;ensureAudio();try{playerColor=$('playerColor').value;const r=await api('/game/new','POST',{color:playerColor});showGame(r.board,r.message)}catch(e){notice('gameStatus',e.message,'err')}};
$('resign').onclick=async()=>{if(!ready()||!game||game.is_over)return;if(!confirm('현재 대국을 기권하시겠습니까?'))return;try{await api('/game/resign','POST');game=null;drawGame();notice('gameStatus','기권으로 대국이 종료됐습니다.');await refresh()}catch(e){notice('gameStatus',e.message,'err')}};
function currentPuzzle(){return puzzleItems[puzzleIdx]}
async function loadPuzzles(){try{puzzleItems=await api('/puzzles');$('puzzleSelect').innerHTML='';puzzleItems.forEach((p,i)=>{const o=document.createElement('option');o.value=i;o.textContent=`${i+1}. ${p.theme} · ${p.difficulty}`;$('puzzleSelect').appendChild(o)});showPuzzle()}catch(e){notice('puzzleStatus',e.message,'err')}}
function showPuzzle(){const p=currentPuzzle();if(!p)return;selectedPuzzle=null;$('puzzleSelect').value=puzzleIdx;$('puzzleLevel').textContent=p.difficulty;$('puzzleSolved').textContent=p.solved?'✓ 해결 완료':'미해결';$('puzzleTitle').textContent=p.theme;$('puzzleDesc').textContent=p.description;notice('puzzleStatus','백의 최선의 수를 찾아보세요. 말과 목적지를 차례로 누릅니다.');drawPuzzle()}
function drawPuzzle(){const p=currentPuzzle();if(!p)return;drawBoard('puzzleBoard',fromFen(p.fen),{selected:selectedPuzzle,onClick:onPuzzleSquare})}
async function onPuzzleSquare(s){const p=currentPuzzle();if(!p||!ready())return;ensureAudio();const board=fromFen(p.fen);if(selectedPuzzle===s){selectedPuzzle=null;drawPuzzle();return}if(!selectedPuzzle){if(!board[s]||board[s]!==board[s].toUpperCase()){notice('puzzleStatus','백 기물을 먼저 선택하세요.');return}selectedPuzzle=s;drawPuzzle();return}const from=selectedPuzzle;selectedPuzzle=null;drawPuzzle();playMoveSound(board[s]?'capture':'move');try{const r=await api('/puzzle/solve','POST',{puzzle_id:p.id,move:from+s});notice('puzzleStatus',r.explanation,r.correct?'ok':'err');if(r.correct){p.solved=true;$('puzzleSolved').textContent='✓ 해결 완료'}await refreshPuzzleStats()}catch(e){notice('puzzleStatus',e.message,'err')}}
async function refreshPuzzleStats(){try{const m=await api('/me');user=m;$('homePuzzles').textContent=m.stats.solved+'개';$('profilePuzzles').textContent=m.stats.solved}catch(e){}}
$('puzzleSelect').onchange=e=>{puzzleIdx=+e.target.value;showPuzzle()};$('nextPuzzle').onclick=()=>{puzzleIdx=(puzzleIdx+1)%Math.max(1,puzzleItems.length);showPuzzle()};$('puzzleReset').onclick=showPuzzle;$('puzzleHint').onclick=()=>notice('puzzleStatus','힌트: 체크, 잡기, 직접적인 위협 순서로 살펴보세요.');
let selectedLesson='rules';function renderLessons(){const done=user?.state?.completed_lessons||[];$('lessonList').innerHTML=lessons.map(([id,title],i)=>`<div class="lesson"><div><b>${i+1}. ${title}</b><small>${done.includes(id)?'✓ 완료':'미완료 · 읽기 학습'}</small></div><button class="btn tiny" data-lesson="${id}">학습하기</button></div>`).join('');document.querySelectorAll('[data-lesson]').forEach(b=>b.onclick=()=>openLesson(b.dataset.lesson));}
function openLesson(id){selectedLesson=id;const lesson=lessons.find(l=>l[0]===id);$('lessonHeading').textContent=lesson[1];$('lessonBody').textContent=lesson[2];notice('lessonStatus','읽고 이해했다면 완료 버튼을 눌러주세요.');}
$('completeLesson').onclick=async()=>{if(!ready())return;try{await api('/lesson/complete','POST',{lesson_id:selectedLesson});notice('lessonStatus','학습 완료 내역이 서버에 저장되었습니다.','ok');await refresh()}catch(e){notice('lessonStatus',e.message,'err')}};
function initSettings(){if($('boardThemeSelect'))$('boardThemeSelect').onchange=e=>{prefs.boardTheme=e.target.value;savePrefs();applyTheme();};if($('pieceThemeSelect'))$('pieceThemeSelect').onchange=e=>{prefs.pieceTheme=e.target.value;savePrefs();applyTheme();};if($('moveSoundSelect'))$('moveSoundSelect').onchange=e=>{prefs.soundTheme=e.target.value;savePrefs();applyTheme();};if($('toggleSound'))$('toggleSound').onclick=()=>{prefs.soundOn=!prefs.soundOn;savePrefs();applyTheme();if(prefs.soundOn)playMoveSound('move');};if($('testSound'))$('testSound').onclick=()=>playMoveSound('move');}
renderLessons();openLesson('rules');initSettings();applyTheme();refresh();
