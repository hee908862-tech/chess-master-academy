/* Read-only: this component never calls a write or grading endpoint. */
(()=>{'use strict';let sequence=0;
window.cmaDiagnosticReplay=(host,source)=>{
 const details=document.createElement('details');details.className='diagnostic-replay';host.append(details);
 const title=document.createElement('summary');title.textContent='상대 응수와 후속 수순 다시 보기';details.append(title);
 const info=document.createElement('p');info.textContent='처음 → 정답 첫 수 → 상대 응수 → 후속 수순. 재생은 응답·채점·저장 기록을 바꾸지 않습니다.';details.append(info);
 const board=document.createElement('div');board.className='board';board.id='diagnosticReplay'+(++sequence);details.append(board);
 const label=document.createElement('p');label.setAttribute('role','status');details.append(label);
 const controls=document.createElement('div');controls.className='btn-row';details.append(controls);
 let data=null,position=0,loading=false,timer=null;const owner=token;
 const stop=()=>{clearInterval(timer);timer=null;if(play)play.textContent='재생';};
 const draw=()=>{if(!data?.available)return;const frame=data.frames[position];board.dataset.fen=frame.fen;drawBoard(board.id,fromFen(frame.fen),{flip:data.side==='black',last:frame.move?[frame.move.slice(0,2),frame.move.slice(2,4)]:[]});label.textContent=`${position} / ${data.frames.length-1} · ${frame.san} · ${frame.fen.split(' ')[1]==='w'?'백':'흑'} 차례 · ${data.basis}`;};
 const button=(text,fn)=>{const b=document.createElement('button');b.type='button';b.className='btn';b.textContent=text;b.dataset.readonly='true';b.onclick=()=>{if(owner!==token){stop();details.remove();return;}fn();};controls.append(b);return b;};
 const go=n=>{stop();if(data?.available){position=Math.max(0,Math.min(data.frames.length-1,n));draw();}};
 button('처음',()=>go(0));button('이전 수',()=>go(position-1));
 const play=button('재생',()=>{if(timer){stop();return;}if(!data?.available)return;if(position===data.frames.length-1)position=0;draw();play.textContent='정지';timer=setInterval(()=>{if(!details.isConnected||!details.open||owner!==token||!details.closest('.view.active')){stop();return;}position++;draw();if(position>=data.frames.length-1)stop();},900);});
 button('다음 수',()=>go(position+1));button('끝',()=>go(data?.frames.length-1||0));
 details.addEventListener('toggle',async()=>{if(!details.open){stop();return;}if(data){draw();return;}if(loading)return;loading=true;controls.hidden=true;label.textContent='저장된 수순 확인 중…';try{const value=typeof source==='function'?await source():source;if(owner!==token||!details.isConnected)return;data=value;if(!data?.available){label.textContent=data?.reason||'원래 위치를 확인할 수 없어 재생하지 않습니다.';return;}controls.hidden=false;draw();}catch(e){label.textContent=e.message+' · 닫았다가 다시 열어 재시도하세요.';}finally{loading=false;}});
 return details;
};})();
