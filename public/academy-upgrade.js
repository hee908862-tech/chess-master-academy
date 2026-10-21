/* Discovery and explicit account switching. Existing account/session APIs retained. */
(()=>{'use strict';function install(){
 const $=id=>document.getElementById(id),node=(p,t,text)=>{const n=document.createElement(t);if(text)n.textContent=text;p.append(n);return n;};
 const button=(p,text,fn)=>{const b=node(p,'button',text);b.type='button';b.className='btn';b.onclick=fn;return b;};
 const shelf=node($('home'),'section');shelf.id='academyTry';shelf.className='card';$('firstEntry').after(shelf);
 node(shelf,'h2','저장 없이 골라서 체험');node(shelf,'p','말 움직이기부터 퍼즐·오프닝까지. 체험 착수는 이 화면에서만 유지되고 정식 기록에 합산되지 않습니다.');
 const choices=p=>{const row=node(p,'div');row.className='academy-choices';for(const [label,id] of [['비숍 움직이기','rook-bishop-1'],['나이트 움직이기','knight-queen-0'],['한 수 메이트','mate-stalemate-0'],['오프닝 이유 보기','opening']])button(row,label,()=>window.cmaGuestPractice.openExample(id));return row;};
 choices(shelf);const next=node($('rookTrial'),'section');next.id='trialMore';node(next,'h3','다른 기능도 체험해 보세요');choices(next);$('trialContinue').after(next);
 const form=$('codeField').closest('.auth-grid'),card=form.closest('.card');const account=node(card,'section');account.id='connectedAccount';form.before(account);
 const state=node(account,'p');state.setAttribute('role','status');let switching=false,identity=token;
 const change=button(account,'계정 전환',()=>{switching=true;$('pinField').value='';$('codeField').value='';sync();$('codeField').focus();});
 const cancel=button(account,'계정 전환 취소',()=>{switching=false;window.cmaCancelAuth?.();$('pinField').value='';sync();change.focus();});
 function sync(){if(identity!==token){identity=token;switching=false;$('pinField').value='';}const connected=!!token;account.hidden=!connected;form.hidden=connected&&!switching;for(const id of ['signup','signin'])$(id).hidden=connected&&!switching;$('signout').hidden=!connected;change.hidden=switching;cancel.hidden=!switching;state.textContent=switching?'다른 계정으로 로그인하면 그 계정의 저장 기록을 엽니다. 취소하면 현재 계정을 유지합니다.':`현재 계정: ${$('userBadge').textContent==='게스트'?'확인 중…':$('userBadge').textContent} · 진행은 계정별로 보존됩니다.`;$('loginNav').textContent=connected?'내 계정':'계정 연결';}
 const oldAuth=auth;auth=async function(...args){try{return await oldAuth(...args);}finally{sync();}};
 const oldTab=tab;tab=function(...args){const value=oldTab(...args);sync();return value;};
 new MutationObserver(sync).observe($('userBadge'),{childList:true,characterData:true,subtree:true});sync();
 const opening=node($('openingStudy'),'section');opening.id='beginnerOpeningPath';opening.className='notice';$('openingStudy').querySelector('h2').after(opening);
 node(opening,'h3','처음이라면 · 중앙 → 전개 → 킹 안전');node(opening,'p','1. 폰으로 중앙을 지키는 이유 → 2. 나이트·비숍이 활동할 칸 → 3. 상대 위협과 캐슬링 가능 여부를 확인하세요. 예시 수순을 외우기보다 각 수의 목적을 설명해 보세요.');
 button(opening,'추천 경로 · 오프닝 이유 체험',()=>window.cmaGuestPractice.openExample('opening'));
 button(opening,'전체 오프닝 탐색',()=>{const chooser=$('focusOpeningSelection');if(chooser)chooser.open=true;$('studyCourse').focus();$('studyCourse').scrollIntoView({block:'center'});});
 node(opening,'p','전체 강의·백/흑 시점·참고 수순은 아래 선택에서 계속 탐색할 수 있습니다.');
 const credit=node($('profileSettings'),'p');credit.className='footnote';credit.append('기물: Chessnut · Alexis Luengas · Apache-2.0 · 동일 도형의 색상 변형. ');const link=node(credit,'a','사용권과 출처');link.href='/assets/assets/pieces/chessnut-source/SOURCE.txt';
}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();})();
