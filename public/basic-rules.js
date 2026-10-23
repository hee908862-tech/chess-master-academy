/* Original lesson predicates; bundled chess.js supplies legal moves, never engine scores. */
(()=>{'use strict';let promise=null,Chess=null;
async function load(){if(!promise)promise=import('/assets/vendor/chess-1.4.0/chess.js').then(m=>(Chess=m.Chess,m)).catch(e=>{promise=null;throw e;});return promise;}
const uci=m=>m.from+m.to+(m.promotion||''),capture=m=>!!m.captured,values={p:1,n:3,b:3,r:5,q:9,k:0};
const board=fen=>new Chess(fen,{skipValidation:true});
function moved(before,move){const after=board(before.fen());after.move(uci(move));return after;}
const capturable=(b,to)=>b.moves({verbose:true}).some(m=>m.to===to&&capture(m));
function protectedPiece(b,to){const target=b.get(to);if(!target||target.color===b.turn())return false;const captures=b.moves({verbose:true}).filter(m=>m.to===to&&capture(m));return captures.length>0&&captures.every(m=>capturable(moved(b,m),to));}
function accepts(unit,b,m){const p=unit.predicate,a=moved(b,m);switch(p.type){
case 'arrive':return m.to===p.target&&m.piece.toUpperCase()===p.piece;case 'promotion':return !!m.promotion&&(!p.capture||capture(m));
case 'legal_move':return true;case 'shield':{const target=b.get(p.target);return !!target&&m.from!==p.target&&!capture(m)&&b.isAttacked(p.target,b.turn()==='w'?'b':'w')&&!a.isAttacked(p.target,a.turn());}
case 'capture':{if(!capture(m)||p.safe&&capturable(a,m.to))return false;if(!p.max_value)return true;const candidates=b.moves({verbose:true}).filter(x=>capture(x)&&(!p.safe||!capturable(moved(b,x),x.to)));return candidates.length>0&&(values[m.captured]||0)===Math.max(...candidates.map(x=>values[x.captured]||0));}
case 'safe_move':return m.from===p.source&&!capturable(a,m.to);
case 'protect':return m.from!==p.target&&protectedPiece(a,p.target);
case 'check':return a.isCheck();case 'mate':return a.isCheckmate();case 'stalemate':return a.isStalemate();
case 'escape':if(!b.isCheck())return false;if(p.method==='any')return true;if(p.method==='king')return m.piece==='k';if(p.method==='capture'){const king=b.board().flat().find(x=>x?.type==='k'&&x.color===b.turn());return capture(m)&&b.attackers(king.square,b.turn()==='w'?'b':'w').includes(m.to);}return m.piece!=='k'&&!capture(m);
case 'castle':return m.flags.includes(p.side==='king'?'k':'q');
case 'king_step':return m.piece==='k'&&!/[kq]/.test(m.flags);
case 'en_passant':return m.flags.includes('e');case 'pawn_forward':return m.piece==='p'&&!capture(m);
default:throw Error('이 규칙의 판정을 준비하지 못했어요.');}}
function chooseReply(unit,b){const legal=b.moves({verbose:true});for(const value of unit.reply?.preferred||[]){const found=legal.find(m=>uci(m)===value);if(found)return found;}return legal.sort((a,b)=>uci(a).localeCompare(uci(b)))[0];}
function replay(unit,actions){let b=board(unit.initial_fen||unit.fen),done=false,failed=false,feedback='',played=[],visited=[],own=0,opponentPlayed=false,ep=(unit.initial_fen||unit.fen).split(' ')[3];const nextEp=m=>m.piece==='p'&&Math.abs(Number(m.from[1])-Number(m.to[1]))===2?m.from[0]+((Number(m.from[1])+Number(m.to[1]))/2):'-';
for(const value of actions){if(done||failed)throw Error('끝난 확인은 새 판에서 다시 시작해요.');const p=unit.predicate;
if(unit.kind==='square'){const s=value.slice(7);if(!/^square:[a-h][1-8]$/.test(value))throw Error('칸을 선택해 주세요.');let yes=p.squares.includes(s);if(p.type==='attacked_squares')yes=yes&&b.isAttacked(s,p.by==='white'?'w':'b');if(p.type==='no_ep_square')yes=yes&&!b.moves({verbose:true}).some(m=>m.flags.includes('e'));done=yes;failed=!yes;visited.push(s);}
else if(unit.kind==='place'){const [,symbol,s]=value.split(':');if(!/^place:[RNBQKP]:[a-h][1-8]$/.test(value))throw Error('말과 칸을 확인해 주세요.');const yes=p.pieces[s]===symbol&&!b.get(s);if(yes){b.put({type:symbol.toLowerCase(),color:'w'},s);visited.push(s);done=Object.entries(p.pieces).every(([sq,pc])=>b.get(sq)?.type===pc.toLowerCase()&&b.get(sq)?.color==='w');if(done){const parts=b.fen().split(' ');parts[2]='KQkq';b=board(parts.join(' '));}}else failed=true;}
else{const m=b.moves({verbose:true}).find(m=>uci(m)===value);if(!m)throw Error('이 이동은 둘 수 없어요. 킹의 안전과 막힌 길을 확인해 주세요.');
if(p.type==='ep_chain'){b.move(value);ep=nextEp(m);played.push(value);if(!m.flags.includes('e'))failed=true;else{own++;done=own===p.required;if(!done){const reply=b.moves({verbose:true}).find(x=>uci(x)===unit.replies[own-1]);if(!reply)throw Error('예시 응수를 확인하지 못했어요.');b.move(uci(reply));ep=nextEp(reply);played.push(uci(reply));opponentPlayed=true;feedback='상대 폰이 새로 두 칸 왔어요. 바로 다음 앙파상을 찾아보세요.';}}}
else if(['check_plan','promotion_followup','castle_plan'].includes(p.type)){const a=moved(b,m);own++;if(own===1){const invalid=p.type==='check_plan'?(m.piece!=='r'||a.isCheck()):p.type==='castle_plan'?m.piece!=='n':!m.promotion;if(invalid){failed=true;b=a;ep=nextEp(m);played.push(value);}else{const reply=chooseReply(unit,a);if(!reply){failed=true;b=a;ep=nextEp(m);played.push(value);}else{a.move(uci(reply));played.push(value,uci(reply));b=a;ep=nextEp(reply);opponentPlayed=true;if(p.type==='check_plan'&&!b.moves({verbose:true}).some(x=>moved(b,x).isCheck()))failed=true;if(p.type==='castle_plan'&&!b.moves({verbose:true}).some(x=>x.flags.includes('k')))failed=true;feedback=p.type==='check_plan'?'상대가 예시 수로 응수했어요. 이제 한 수로 체크해보세요.':p.type==='castle_plan'?'상대가 응수했어요. 이제 오른쪽 캐슬링을 해보세요.':'상대가 응수했어요. 이제 승격으로 바뀐 말을 움직여보세요.';}}}else{done=p.type==='check_plan'?a.isCheck():p.type==='castle_plan'?m.flags.includes('k'):m.from===actions[0].slice(2,4);failed=!done;b=a;ep=nextEp(m);played.push(value);}}
else{done=accepts(unit,b,m);failed=!done;b.move(value);ep=nextEp(m);played.push(value);own++;}}
if(done)feedback=unit.reason||'이번 규칙을 직접 확인했어요.';else if(failed)feedback='이번 목표와는 달라요. '+unit.rule+' 원래 배치에서 다시 확인해 보세요.';
}
let place_symbol=null;if(unit.kind==='place'&&!done&&!failed){const missing=Object.entries(unit.predicate.pieces).filter(([s,p])=>b.get(s)?.type!==p.toLowerCase()||b.get(s)?.color!=='w').map(([,p])=>p);place_symbol=unit.placement_order.find(p=>missing.includes(p));}
const fen=b.fen().split(' ');fen[3]=ep;return {fen:fen.join(' '),source:null,remaining:[],visited,done,failed,legal:unit.kind==='move'&&!done&&!failed?b.moves({verbose:true}).map(uci):[],moves:[...actions],played,feedback,place_symbol,opponent_example:opponentPlayed?(unit.reply?.label||null):null};}
window.cmaBasicRules={load,replay,accepts};
})();
