/* One local premove per board. No move is sent until an authoritative legal list arrives. */
(()=>{'use strict';
const waits=new Map(),controls=new Map();let enabled=false,generation=0;
try{enabled=localStorage.getItem('cma_premove')==='on'}catch(e){}
function message(id,text){const c=controls.get(id);if(c)c.message.textContent=text}
function clearMarks(id){const b=document.getElementById(id);if(!b)return;b.querySelectorAll('.premove-from,.premove-to').forEach(x=>x.classList.remove('premove-from','premove-to'));b.querySelectorAll('.premove-arrow').forEach(x=>x.remove())}
function decorate(id){clearMarks(id);const w=waits.get(id),b=document.getElementById(id);if(!w||!b||!enabled)return;
 const squares=[...b.querySelectorAll('.sq')],find=s=>squares.find(x=>x.getAttribute('aria-label')?.split(' ')[0]===s);
 if(w.from)find(w.from)?.classList.add('premove-from');
 if(!w.to)return;find(w.to)?.classList.add('premove-to');
 const xy=s=>{const i=squares.indexOf(find(s));return [i%8+.5,Math.floor(i/8)+.5]};
 const a=xy(w.from),z=xy(w.to),ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');
 svg.classList.add('premove-arrow');svg.setAttribute('viewBox','0 0 8 8');svg.setAttribute('aria-hidden','true');
 const line=document.createElementNS(ns,'line');for(const [k,v] of Object.entries({x1:a[0],y1:a[1],x2:z[0],y2:z[1],stroke:'#f39cff','stroke-width':'.13','stroke-dasharray':'.24 .12'}))line.setAttribute(k,v);
 const dot=document.createElementNS(ns,'circle');dot.setAttribute('cx',z[0]);dot.setAttribute('cy',z[1]);dot.setAttribute('r','.23');dot.setAttribute('fill','#f39cff');svg.append(line,dot);b.append(svg);
}
function cancel(id){waits.delete(id);clearMarks(id);message(id,'예약 없음 · 상대 응답 대기 중 출발/도착 칸 선택');generation++}
function cancelAll(){window.cmaBoardPresentation?.cancelAll();window.cancelPromotion?.();for(const id of controls.keys())cancel(id)}
function pick(id,square){const w=waits.get(id);if(!enabled||!w)return;const piece=w.position[square],own=piece&&((piece===piece.toUpperCase())===(w.side==='white'));
 if(w.to||w.from===square){w.from=null;w.to=null}
 if(!w.from){if(own)w.from=square}else{w.to=square}
 message(id,w.to?`예약: ${w.from} → ${w.to} · 응답 후 합법성 확인`:w.from?`예약 출발: ${w.from} · 도착 칸 선택`:'예약 취소');decorate(id);
}
function begin(id,key,position,side){cancel(id);waits.set(id,{key,position,side,from:null,to:null});message(id,'상대 응답 대기 · 프리무브 ON이면 출발/도착 칸 선택')}
function take(id,key,legal,ready){const w=waits.get(id);waits.delete(id);clearMarks(id);
 if(!w?.to){if(w)message(id,'예약 없음 · 상대 응답 대기 중에만 예약할 수 있습니다.');return null;}
 const move=w.from+w.to;
 if(!enabled||w.key!==key||!ready||!(legal||[]).some(u=>(typeof u==='string'?u:u.from+u.to+(u.promotion||'')).slice(0,4)===move)){message(id,'예약 취소 · 현재 위치에서 실행할 수 없습니다.');return null}
 message(id,`예약 실행: ${w.from} → ${w.to}`);return {from:w.from,to:w.to};
}
function install(){
 const style=document.createElement('style');style.textContent='.board{position:relative}.premove-arrow{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:4}.sq.premove-from{outline:4px dashed #f39cff;outline-offset:-5px}.sq.premove-to{outline:5px solid #f39cff;outline-offset:-6px}.sq.opponent-move{border:4px solid #54d8ef!important}.sq.move-hint{outline:4px dotted #66e0b0;outline-offset:-6px}.board-tools{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:10px 0;font-size:13px}.board-tools label{display:flex;align-items:center;gap:6px;min-height:44px}.board-tools input{width:20px;height:20px}.board-tools button{min-height:44px}.board-tools small{flex-basis:100%}';document.head.append(style);
 for(const id of ['gameBoard','testBoard','v9PuzzleBoard','v9CourseBoard']){const board=document.getElementById(id);if(!board)continue;const wrap=document.createElement('div');wrap.className='board-tools';const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.checked=enabled;input.setAttribute('aria-label','프리무브 '+id);label.append(input,'프리무브 ON/OFF');const button=document.createElement('button');button.className='btn tiny';button.textContent='예약 취소';button.type='button';const msg=document.createElement('small');msg.setAttribute('role','status');const legend=document.createElement('small');legend.textContent='청록 테두리: 상대 직전 수 · 금색: 마지막 착수/정답 · 초록 점선: 힌트 · 분홍 경로: 예약. 상대 응답 대기 중 1수만 예약하며 승격 기물은 응답 후 선택합니다. 진단 문항 채점 중에는 예약하지 않습니다.';controls.set(id,{input,message:msg});const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent='보드 표시·프리무브 안내';details.append(summary,legend);wrap.append(label,button,msg,details);board.after(wrap);
 input.onchange=()=>{enabled=input.checked;try{localStorage.setItem('cma_premove',enabled?'on':'off')}catch(e){}for(const c of controls.values())c.input.checked=enabled;if(!enabled)cancelAll()};button.onclick=()=>cancel(id);cancel(id);
 }
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!e.defaultPrevented&&!e.target.closest('dialog'))cancelAll()});
}
function unavailable(id){cancel(id);message(id,'이전 세션은 예약 식별 정보가 없어 프리무브를 지원하지 않습니다. 새 대국/문제에서 사용할 수 있습니다.')}
window.cmaBoardTools={unavailable,begin,take,pick,cancel,cancelAll,decorate,version:()=>generation};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
})();
