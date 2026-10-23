/* Optional foreground-thinking telemetry. No score calculation or network timer. */
(()=>{'use strict';
const VERSION='thinking-time-v1',MAX=1800000,KEY='cma_thinking_time_v1',MAX_RECORDS=256;
let current=null,startAt=null,reasons=new Set(),panels=new Set();
const stamp=()=>performance.now(),validInt=n=>Number.isInteger(n)&&n>=0&&n<=MAX;
function loadStore(){try{const raw=localStorage.getItem(KEY);if(!raw)return {};if(raw.length>200000)return {};const value=JSON.parse(raw);return value&&typeof value==='object'&&!Array.isArray(value)?value:{};}catch(_){return {};}}
function persist(){if(!current)return;try{const all=loadStore();if(!all[current.key]&&Object.keys(all).length>=MAX_RECORDS)throw Error('capacity');all[current.key]={stream_id:current.stream_id,seq:current.seq,active_ms:Math.floor(current.active_ms),explicit:reasons.has('explicit'),limited:current.limited,explicit_pause_used:current.explicit_pause_used,open:startAt!==null};localStorage.setItem(KEY,JSON.stringify(all));}catch(_){current.limited=true;}}
function collect(){if(!current||startAt===null)return;const now=stamp(),delta=now-startAt;startAt=now;if(!Number.isFinite(delta)||delta<0){current.limited=true;return;}if(current.active_ms+delta>MAX)current.limited=true;current.active_ms=Math.min(MAX,current.active_ms+delta);}
function running(){return !!current&&!reasons.size&&!document.hidden&&current.active_ms<MAX;}
function update(){for(const panel of panels){if(!panel.isConnected){panels.delete(panel);continue;}const b=panel.querySelector('button'),s=panel.querySelector('[role=status]');b.disabled=!current;b.textContent=reasons.has('explicit')?'생각 시간 측정 다시 시작':'생각 시간 일시정지';s.textContent=!current?'활동 시간 미측정':current.explicit_pause_used?'직접 일시정지를 사용한 시간은 속도 비교에서 제외합니다.':current.limited?'활동 시간 기록에 제한이 있어 속도 비교를 보류합니다.':running()?'활동 시간 측정 중 · 실력 점수와 별도입니다.':'활동 시간 일시정지 · 쉬거나 화면을 떠난 시간은 더하지 않습니다.';}}
function sync(){if(running()){if(startAt===null)startAt=stamp();}else startAt=null;persist();update();}
function pause(reason='explicit'){collect();if(current&&reason==='explicit')current.explicit_pause_used=true;reasons.add(String(reason));sync();}
function resume(reason='explicit'){collect();reasons.delete(String(reason));sync();}
function begin(sessionId,itemId,serverThinkingTime){
 const key=String(sessionId||'')+':'+String(itemId||'');
 if(!sessionId||!itemId||key.length>180){pause('invalid_item');return;}
 if(!current||current.key!==key){collect();startAt=null;persist();const saved=loadStore()[key];
  const usable=saved&&typeof saved.stream_id==='string'&&/^[A-Za-z0-9_-]{8,64}$/.test(saved.stream_id)&&Number.isInteger(saved.seq)&&saved.seq>=0&&saved.seq<=1000000&&validInt(saved.active_ms);
  current={key,stream_id:usable?saved.stream_id:crypto.randomUUID().replaceAll('-',''),seq:usable?saved.seq:0,active_ms:usable?saved.active_ms:0,limited:!!(usable&&(saved.limited||saved.open)),explicit_pause_used:!!(usable&&saved.explicit_pause_used)};
  reasons.delete('explicit');reasons.delete('invalid_item');if(usable&&saved.explicit)reasons.add('explicit');
 }
 const cursor=serverThinkingTime?.version===VERSION?serverThinkingTime.streams?.[current.stream_id]:null;
 if(cursor&&Number.isInteger(cursor.seq)&&cursor.seq>=current.seq&&validInt(cursor.client_ms)){collect();current.seq=cursor.seq;current.active_ms=Math.max(current.active_ms,cursor.client_ms);}
 if(document.hidden)reasons.add('visibility');else reasons.delete('visibility');
 sync();
}
function snapshot(){if(!current)return null;collect();if(current.seq>=1000000){current.limited=true;pause('sequence_limit');return null;}current.seq++;persist();const value={version:VERSION,stream_id:current.stream_id,seq:current.seq,active_ms:Math.floor(current.active_ms),limited:current.limited,explicit_pause_used:current.explicit_pause_used};update();return value;}
function clear(){collect();startAt=null;persist();current=null;reasons=new Set();update();}
function offer(host){if(!host)return null;let panel=host.querySelector('[data-thinking-controls]');if(panel){panels.add(panel);update();return panel;}panel=document.createElement('div');panel.dataset.thinkingControls='';panel.className='thinking-controls';const b=document.createElement('button');b.type='button';b.className='btn';b.onclick=()=>reasons.has('explicit')?resume('explicit'):pause('explicit');const s=document.createElement('p');s.className='subtle';s.setAttribute('role','status');panel.append(b,s);host.append(panel);panels.add(panel);update();return panel;}
document.addEventListener('visibilitychange',()=>document.hidden?pause('visibility'):resume('visibility'));
addEventListener('pagehide',()=>pause('pagehide'));
addEventListener('pageshow',()=>resume('pagehide'));
addEventListener('beforeunload',()=>pause('pagehide'));
window.cmaDiagnosisTiming={begin,start:begin,pause,resume,snapshot,clear,offer,status:()=>{collect();return {version:VERSION,active_ms:current?Math.floor(current.active_ms):null,running:running(),paused:[...reasons],limited:current?.limited||false};}};
})();
