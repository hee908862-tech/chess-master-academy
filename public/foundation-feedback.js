/* Read-only relationships. Coordinates follow rendered cells, including flipped boards. */
(()=>{'use strict';
window.cmaFoundationVisual={draw(id,visual,flip,show=true){
 const board=document.getElementById(id);if(!board||!visual)return;
 board.querySelectorAll('.foundation-arrows').forEach(n=>n.remove());
 if(visual.check_king)board.querySelector(`[aria-label^="${visual.check_king} "]`)?.classList.add('foundation-check');
 if(!show)return;const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 8 8');svg.setAttribute('aria-hidden','true');svg.classList.add('foundation-arrows');svg.style.pointerEvents='none';
 const cells=[...board.querySelectorAll('.sq')],point=s=>{const i=cells.findIndex(c=>c.getAttribute('aria-label').startsWith(s+' '));return i<0?null:[i%8+.5,Math.floor(i/8)+.5];};
 const shape=(tag,attrs)=>{const e=document.createElementNS(ns,tag);for(const[k,v]of Object.entries(attrs))e.setAttribute(k,v);svg.append(e);return e;};
 for(const a of (visual.arrows||[]).slice(0,6)){const start=point(a.via||a.from),end=point(a.to);if(!start||!end)continue;const kind=a.kind==='attack'?'threat':a.kind,color={guide:'#ffe18a',threat:'#ff92a8',protect:'#81ebcc',last:'#b7cbff'}[kind]||'#ffe18a';const dx=end[0]-start[0],dy=end[1]-start[1],len=Math.hypot(dx,dy);if(!len)continue;const ux=dx/len,uy=dy/len;
 const path=a.via?`M ${point(a.from).join(' ')} L ${start.join(' ')} L ${end[0]-.3*ux} ${end[1]-.3*uy}`:`M ${start[0]+.22*ux} ${start[1]+.22*uy} L ${end[0]-.3*ux} ${end[1]-.3*uy}`;
 const attrs={d:path,fill:'none',stroke:color,'stroke-width':'.085','stroke-linecap':'round','stroke-linejoin':'round',opacity:'.88'};
 if(kind==='threat')attrs['stroke-dasharray']='.17 .12';if(kind==='protect')attrs['stroke-dasharray']='.025 .14';
 shape('path',{...attrs,stroke:'#162434','stroke-width':'.13'});shape('path',attrs);
 if(kind==='protect')shape('circle',{cx:end[0]-.25*ux,cy:end[1]-.25*uy,r:'.12',fill:'none',stroke:color,'stroke-width':'.06'});
 else shape('path',{d:`M ${end[0]-.48*ux+.13*uy} ${end[1]-.48*uy-.13*ux} L ${end[0]-.23*ux} ${end[1]-.23*uy} L ${end[0]-.48*ux-.13*uy} ${end[1]-.48*uy+.13*ux}`,fill:'none',stroke:color,'stroke-width':'.085','stroke-linecap':'round','stroke-linejoin':'round'});
 }
 for(const cell of visual.king_moves||[]){const p=point(cell.square);if(!p)continue;const x=p[0]+.27,y=p[1]+.27;shape('circle',{cx:x,cy:y,r:'.17',fill:'#162434',opacity:'.9'});shape('path',{d:cell.legal?`M ${x-.08} ${y} l .06 .06 l .11 -.13`:`M ${x-.07} ${y-.07} l .14 .14 M ${x+.07} ${y-.07} l -.14 .14`,stroke:cell.legal?'#81ebcc':'#ffb1b1','stroke-width':'.045','stroke-linecap':'round',fill:'none'});}
 board.append(svg);
}};
})();
