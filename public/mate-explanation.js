/* Independent read-only board; no hints, premoves, or training writes. */
(()=>{'use strict';
const panels=new Map();
function clear(id){panels.get(id)?.remove();panels.delete(id);}
function show(id,data,flip){clear(id);if(!data)return;
 const host=document.getElementById(id),panel=document.createElement('details');panel.className='mate-panel';panel.dataset.for=id;
 const title=document.createElement('summary');title.textContent='메이트 해설 열기 / 닫기';panel.append(title);
 const text=document.createElement('p');text.textContent=data.available?data.note:data.reason;panel.append(text);
 if(data.available){
  const source=document.createElement('p');source.textContent=data.source||'정답 착수 이후의 최종 체크메이트 위치';panel.append(source);
  const legend=document.createElement('p');legend.textContent=`왕 ${data.king} · 체크 기물 ${data.checkers.join(', ')} · 합법 대응 ${data.legal_replies}개. [왕] 수비 왕, [체크] 체크 기물, [통제] 선택 칸의 공격자. 도주 칸 또는 아래 버튼을 선택하세요. 표시된 칸은 원래 문제의 입력과 별개입니다.`;panel.append(legend);
  const board=document.createElement('div');board.className='board';board.id=id+'MateBoard';panel.append(board);
  const detail=document.createElement('p');detail.className='notice';detail.setAttribute('aria-live','polite');panel.append(detail);
  const list=document.createElement('div');list.className='mate-choices';panel.append(list);
  function select(cell){
   drawBoard(board.id,fromFen(data.fen),{flip,onClick:s=>{const c=data.cells.find(c=>c.square===s);if(c)select(c);}});
   for(const sq of board.querySelectorAll('.sq')){
    const name=sq.getAttribute('aria-label').split(' ')[0],labels=[];
    if(name===data.king)labels.push('왕');if(data.checkers.includes(name))labels.push('체크');
    if(cell?.attackers.some(a=>a.square===name))labels.push('통제');
    if(name===cell?.square){sq.classList.add('selected');labels.push('선택');}
    if(labels.length){const tag=document.createElement('small');tag.className='mate-label';tag.textContent=labels.join('·');sq.append(tag);sq.setAttribute('aria-label',sq.getAttribute('aria-label')+' '+labels.join(' '));}
   }
   detail.textContent=cell?`${cell.square||'보드 밖'}: ${cell.reasons.join(' / ')}. 통제 기물: ${cell.attackers.map(a=>a.square+' '+a.piece).join(', ')||'없음'}`:'왕 주변 칸을 선택하면 이동할 수 없는 이유와 모든 통제 기물을 확인할 수 있습니다.';
  }
  for(const cell of data.cells){const b=document.createElement('button');b.type='button';b.className='btn';b.textContent=(cell.square||`보드 밖 (${cell.offset.join(',')})`)+' · '+cell.reasons.join(' / ');b.onclick=()=>select(cell);list.append(b);}
  panel.addEventListener('toggle',()=>{if(panel.open){window.cmaBoardTools?.cancel(id);select(null);}});
 }
 host.parentElement.append(panel);panels.set(id,panel);
}
const style=document.createElement('style');style.textContent='.mate-panel{margin:12px 0;padding:12px;border:1px solid #6c95ae;border-radius:12px}.mate-panel summary{cursor:pointer;min-height:44px;font-weight:bold}.mate-panel p{font-size:13px;line-height:1.6}.mate-panel .board{max-width:460px;margin:10px auto}.mate-choices{display:flex;gap:6px;flex-wrap:wrap}.mate-choices button{min-height:44px;font-size:12px}.mate-label{position:absolute;bottom:1px;left:1px;right:1px;font-size:8px;white-space:nowrap;background:#14283a;color:white;line-height:1.2;pointer-events:none}';document.head.append(style);
window.cmaMate={clear,show};
})();
