/* Explicit anonymous identity; account and guest sessions are never merged implicitly. */
(()=>{'use strict';
const $=id=>document.getElementById(id), make=(p,t,text)=>{const e=document.createElement(t);e.textContent=text;p.append(e);return e;};
const box=document.createElement('section');box.className='card';box.id='guestAccess';$('home').prepend(box);
make(box,'h2','기초 배우기 → 실력 확인 → 약점 훈련 → 대국·복기');
make(box,'p','로그인 없이 모든 학습 기능을 시작하세요. 같은 정답 판정과 엔진을 사용합니다.');
const status=make(box,'p','');status.setAttribute('role','status');status.style.minHeight='3em';
const note=make(box,'p','이 브라우저에 접속 키를, 서버에 진행과 기록을 저장합니다. 브라우저 데이터 삭제·시크릿 창 종료·다른 기기에서는 연결 전 기록을 열 수 없습니다. 로그인 계정에 별도로 연결하면 다른 기기에서도 이어갈 수 있습니다.');note.className='subtle';
let busy=false;
async function enter(destination){if(busy)return;busy=true;status.textContent='저장된 브라우저 기록을 확인하고 있습니다…';try{
 if(!token){const identity=token;let saved=localStorage.getItem('cma_guest_token');if(!saved){const r=await api('/guest/start','POST');if(token!==identity)return;saved=r.token;localStorage.setItem('cma_guest_token',saved);}token=saved;localStorage.setItem('cma_identity','guest');resetGameAccount();await refresh();}
 status.textContent='기록을 확인했습니다. 각 착수의 판정·저장 결과를 확인해 주세요.';tab(destination);
 }catch(e){status.textContent=e.message+' 기존 기록은 지우지 않았습니다.';}finally{busy=false;}}
const actions=make(box,'div','');actions.className='btn-row';for(const [title,view]of [['기초 배우기','learn'],['일반 퍼즐·훈련','training'],['오프닝 학습','opening'],['AI 대국','play'],['실력 진단','diagnosis']]){const b=make(actions,'button',title);b.className='btn';b.onclick=()=>enter(view);}
const profile=make($('profile'),'section','');profile.id='guestAccountAccess';profile.className='card';make(profile,'h3','브라우저 기록과 계정 기록');
const msg=make(profile,'p','연결은 별도 보관입니다. 기존 계정의 점수·기보·진행 중 세션을 덮어쓰거나 합산하지 않습니다.');msg.setAttribute('role','status');
const guestStart=make(profile,'button','로그인 없이 전체 기능 시작');guestStart.className='btn';guestStart.onclick=()=>enter(loginDestination||'home');
const connect=make(profile,'button','이 브라우저의 게스트 기록을 계정에 별도 연결');connect.className='btn';connect.onclick=async()=>{if(busy)return;const guest=localStorage.getItem('cma_guest_token'),account=localStorage.getItem('chess_token');if(!guest||!account||token!==account){msg.textContent='계정에 로그인한 뒤 연결하세요. 현재 게스트 기록은 유지됩니다.';return;}busy=true;connect.disabled=true;try{const r=await api('/guest/link','POST',{guest_token:guest});if(localStorage.getItem('cma_guest_token')===guest)localStorage.removeItem('cma_guest_token');for(const path of ['/journey','/foundations','/learning','/game'])localStorage.removeItem('cma_guest_snapshot:'+path);msg.textContent=r.message;await links();}catch(e){msg.textContent=e.message;}finally{busy=false;connect.disabled=false;}};
const saved=make(profile,'div','');let serial=0;
async function links(){const stamp=++serial,owner=token;saved.replaceChildren();if(!owner)return;try{const r=await api('/guest/links');if(stamp!==serial||owner!==token)return;for(const item of r.items){const b=make(saved,'button',item.label+' 이어하기');b.className='btn';b.onclick=async()=>{if(busy)return;busy=true;try{const next=await api('/guest/resume','POST',{id:item.id});if(token!==owner)return;localStorage.setItem('cma_linked_token',next.token);localStorage.setItem('cma_identity','linked');token=next.token;resetGameAccount();await refresh();tab('home');}catch(e){msg.textContent=e.message;}finally{busy=false;}};}}catch(e){if(stamp===serial)msg.textContent=e.message;}}
const back=make(profile,'button','로그인 계정의 원래 기록으로 돌아가기');back.className='btn';back.onclick=async()=>{const account=localStorage.getItem('chess_token');if(!account){msg.textContent='먼저 로그인해 주세요.';return;}token=account;localStorage.setItem('cma_identity','account');resetGameAccount();await refresh();tab('home');};
const oldSignout=$('signout').onclick;$('signout').onclick=async function(e){if(token&&token===localStorage.getItem('cma_linked_token')){token=localStorage.getItem('chess_token')||'';resetGameAccount();}if(token&&token===localStorage.getItem('cma_guest_token')){msg.textContent='게스트 기록은 보존됩니다. 계정 전환 버튼으로 로그인하거나 원래 계정으로 돌아가세요.';tab('profile');return;}await oldSignout?.call(this,e);if(!localStorage.getItem('chess_token')){localStorage.removeItem('cma_linked_token');localStorage.removeItem('cma_identity');saved.replaceChildren();}};
window.addEventListener('storage',e=>{if(['chess_token','cma_guest_token','cma_linked_token'].includes(e.key)&&e.oldValue===token&&e.newValue!==token){token='';user=null;window.cmaBoardTools.cancelAll();resetGameAccount();saved.replaceChildren();msg.textContent='계정 연결 또는 로그아웃으로 접근 권한이 변경되었습니다. 소유 계정으로 로그인하세요.';tab('profile');}});

const oldTab=tab;tab=function(id){oldTab(id);if(id==='profile')links();};
// A small acknowledged-response cache is a browser copy, never an authority for grading.
const oldApi=api;api=async function(path,...args){const identity=token;const r=await oldApi(path,...args);if(identity&&identity===token&&identity===localStorage.getItem('cma_guest_token')&&['/journey','/foundations','/learning','/game'].includes(path)){try{localStorage.setItem('cma_guest_snapshot:'+path,JSON.stringify({at:Date.now(),response:r}));}catch(e){status.textContent='브라우저 사본 저장 공간이 부족합니다. 서버 저장 응답은 별도로 확인하세요.';}}return r;};
const badge=$('userBadge');new MutationObserver(()=>{if(token&&token===localStorage.getItem('cma_guest_token')&&badge.textContent!=='게스트 · 이 브라우저 기록')badge.textContent='게스트 · 이 브라우저 기록';}).observe(badge,{childList:true});
})();
