/* Presentation only: geometric attacks include pinned pieces; motion needs an explicit move. */
(()=>{'use strict';
const files='abcdefgh',positions=new Map(),running=new Map();
const xy=s=>[files.indexOf(s[0]),Number(s[1])-1],square=(f,r)=>files[f]+(r+1);
function attacked(board,target,white){const [tx,ty]=xy(target);for(const [s,p]of Object.entries(board)){if((p===p.toUpperCase())!==white)continue;const[x,y]=xy(s),dx=tx-x,dy=ty-y,t=p.toLowerCase();if(!dx&&!dy)continue;
 if(t==='p'&&Math.abs(dx)===1&&dy===(white?1:-1))return true;
 if(t==='n'&&Math.abs(dx)*Math.abs(dy)===2)return true;
 if(t==='k'&&Math.max(Math.abs(dx),Math.abs(dy))===1)return true;
 if(!((t==='r'||t==='q')&&(!dx||!dy)||(t==='b'||t==='q')&&Math.abs(dx)===Math.abs(dy)))continue;
 const sx=Math.sign(dx),sy=Math.sign(dy);let clear=true;for(let f=x+sx,r=y+sy;f!==tx||r!==ty;f+=sx,r+=sy)if(board[square(f,r)]){clear=false;break;}if(clear)return true;
 }return false;}
function checked(board){return Object.entries(board).filter(([s,p])=>p.toLowerCase()==='k'&&attacked(board,s,p!==p.toUpperCase())).map(([s])=>s);}
const equal=(a,b)=>Object.keys(a).length===Object.keys(b).length&&Object.keys(a).every(s=>a[s]===b[s]);
function advance(before,uci,hint={}){if(!/^[a-h][1-8][a-h][1-8][qrbn]?$/.test(uci||''))return null;const from=uci.slice(0,2),to=uci.slice(2,4),p=before[from];if(!p||before[to]&&(before[to]===before[to].toUpperCase())===(p===p.toUpperCase()))return null;
 const next={...before},moves=[{from,to,piece:p}];delete next[from];next[to]=p;
 if(p.toLowerCase()==='p'){if(from[0]!==to[0]&&!before[to]){const captured=to[0]+from[1];if(before[captured]!== (p==='P'?'p':'P'))return null;delete next[captured];}if(to[1]==='1'||to[1]==='8'){const promoted=uci[4]||(hint[to]||'').toLowerCase();if(!'qrbn'.includes(promoted)||promoted.length!==1)return null;next[to]=p==='P'?promoted.toUpperCase():promoted;}}
 if(p.toLowerCase()==='k'&&from[1]===to[1]&&Math.abs(xy(from)[0]-xy(to)[0])===2){const rf=(to[0]==='g'?'h':'a')+from[1],rt=(to[0]==='g'?'f':'d')+from[1],rook=p==='K'?'R':'r';if(before[rf]!==rook)return null;delete next[rf];next[rt]=rook;moves.push({from:rf,to:rt,piece:rook});}return {next,moves};}
function plan(before,after,uci,reverse=false){const sequence=Array.isArray(uci)?uci:[uci];if(!sequence.length||sequence.length>2)return null;
 if(reverse){const p=plan(after,before,sequence);return p?.map(m=>({from:m.to,to:m.from,piece:m.afterPiece,step:sequence.length-1-m.step}));}
 let board=before,moves=[];for(let i=0;i<sequence.length;i++){const r=advance(board,sequence[i],after);if(!r)return null;moves.push(...r.moves.map(m=>({...m,afterPiece:r.next[m.to],step:i})));board=r.next;}return equal(board,after)?moves:null;}

function cancel(id){const r=running.get(id);if(!r)return;running.delete(id);for(const a of r.animations)a.cancel();for(const g of r.ghosts)g.remove();for(const n of r.hidden)if(n.isConnected)n.style.opacity='';cancelAnimationFrame(r.frame);}
function cancelAll(){for(const id of [...running.keys()])cancel(id);}
function beforeDraw(id,board,flip=false){const r=running.get(id);if(r&&(!equal(positions.get(id)||{},board)||r.flip!==flip))cancel(id);}
function remember(id,board){positions.set(id,{...board});const host=document.getElementById(id);if(!host)return;const active=running.get(id);if(active)for(const to of active.targets){const n=host.querySelector(`[aria-label^="${to} "] .piece-wrap`);if(n){n.style.opacity='0';active.hidden.push(n);}}for(const s of checked(board)){const cell=host.querySelector(`[aria-label^="${s} "]`);if(!cell)continue;cell.classList.add('cma-check');cell.setAttribute('aria-label',cell.getAttribute('aria-label')+' · 체크 당한 킹');const label=document.createElement('small');label.className='cma-check-label';label.textContent='체크';label.setAttribute('aria-hidden','true');cell.append(label);}}
function transition(id,uci,paint,reverse=false){cancel(id);let host=document.getElementById(id);const before=positions.get(id),old=new Map();if(host&&before)for(const s of [...host.querySelectorAll('.sq')].map(n=>n.getAttribute('aria-label').split(' ')[0])){const n=host.querySelector(`[aria-label^="${s} "] .piece-wrap`);if(n)old.set(s,{node:n.cloneNode(true),box:n.getBoundingClientRect()});}paint();host=document.getElementById(id);const after=positions.get(id),moves=before&&after&&plan(before,after,uci,reverse);if(!moves||!host?.isConnected||!host.getClientRects().length||matchMedia('(prefers-reduced-motion: reduce)').matches)return;
 const identity=typeof token==='undefined'?null:token,r={animations:[],ghosts:[],hidden:[],targets:[],flip:host.querySelector('.sq')?.getAttribute('aria-label')?.startsWith('h1 '),frame:0};running.set(id,r);
 for(const m of moves){const prior=old.get(m.from),dest=host.querySelector(`[aria-label^="${m.to} "] .piece-wrap`);if(!prior||!dest||!prior.box.width)continue;const box=dest.getBoundingClientRect(),g=before[m.from]===m.piece?prior.node:renderPiece(m.piece);g.classList.add('cma-motion-ghost');g.setAttribute('aria-hidden','true');g.style.cssText=`position:fixed;z-index:1000;pointer-events:none;left:${prior.box.x}px;top:${prior.box.y}px;width:${prior.box.width}px;height:${prior.box.height}px;opacity:${m.step?0:1}`;document.body.append(g);dest.style.opacity='0';r.ghosts.push(g);r.hidden.push(dest);r.targets.push(m.to);r.animations.push(g.animate([{opacity:1,transform:'translate(0,0)'},{opacity:1,transform:`translate(${box.x-prior.box.x}px,${box.y-prior.box.y}px)`}],{duration:210,delay:(m.step||0)*210,easing:'ease-out',fill:'forwards'}));}
 if(!r.animations.length){cancel(id);return;}const watch=()=>{if(running.get(id)!==r)return;if(!host.isConnected||!host.getClientRects().length||(typeof token==='undefined'?null:token)!==identity){cancel(id);return;}r.frame=requestAnimationFrame(watch);};watch();Promise.allSettled(r.animations.map(a=>a.finished)).then(()=>{if(running.get(id)===r)cancel(id);});}
window.cmaBoardPresentation={attacked,checked,advance,plan,cancel,cancelAll,beforeDraw,remember,transition};
window.addEventListener('resize',cancelAll);window.addEventListener('scroll',cancelAll,true);document.addEventListener('visibilitychange',()=>{if(document.hidden)cancelAll();});matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change',cancelAll);
})();
