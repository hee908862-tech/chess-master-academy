/* Read-only presentation for guided foundations. Never submits moves or hints. */
(()=>{'use strict';
window.cmaFoundationVisual={draw(id,visual,flip,show=true){
 const board=document.getElementById(id);if(!board||!visual)return;
 if(visual.check_king&&!board.querySelector('.cma-check')){const cell=board.querySelector(`[aria-label^="${visual.check_king} "]`);if(cell){cell.classList.add('foundation-check');const label=document.createElement('small');label.className='foundation-check-label';label.textContent='체크';cell.append(label);cell.setAttribute('aria-label',cell.getAttribute('aria-label')+' · 체크 당한 킹');}}
 if(!show)return;const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 8 8');svg.setAttribute('aria-hidden','true');svg.classList.add('foundation-arrows');
 const point=s=>{const f='abcdefgh'.indexOf(s[0]),r=Number(s[1])-1;return flip?[7-f+.5,r+.5]:[f+.5,7-r+.5];};
 for(const a of visual.arrows||[]){const start=point(a.via||a.from),end=point(a.to),color={guide:'#ffe18a',threat:'#ff92a8',protect:'#81ebcc'}[a.kind]||'#ffe18a';const dx=end[0]-start[0],dy=end[1]-start[1],len=Math.hypot(dx,dy);if(!len)continue;const ux=dx/len,uy=dy/len;
 if(a.via){const origin=point(a.from),leg=document.createElementNS(ns,'line');for(const[k,v]of Object.entries({x1:origin[0],y1:origin[1],x2:start[0],y2:start[1],stroke:color,'stroke-width':'.13'}))leg.setAttribute(k,v);svg.append(leg);}
 const line=document.createElementNS(ns,'line');for(const [k,v]of Object.entries({x1:start[0],y1:start[1],x2:end[0]-.25*ux,y2:end[1]-.25*uy,stroke:color,'stroke-width':'.13'}))line.setAttribute(k,v);if(a.kind==='threat')line.setAttribute('stroke-dasharray','.23 .12');const halo=line.cloneNode();halo.setAttribute('stroke','#18202c');halo.setAttribute('stroke-width','.21');svg.append(halo,line);
 const tip=document.createElementNS(ns,'polygon');tip.setAttribute('points',`${end[0]},${end[1]} ${end[0]-.48*ux+.20*uy},${end[1]-.48*uy-.20*ux} ${end[0]-.48*ux-.20*uy},${end[1]-.48*uy+.20*ux}`);tip.setAttribute('fill',color);tip.setAttribute('stroke','#18202c');tip.setAttribute('stroke-width','.035');svg.append(tip);}
 board.append(svg);
}};
})();
