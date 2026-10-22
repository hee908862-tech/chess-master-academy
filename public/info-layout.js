/* Existing profile nodes, separate UI destinations. No data migration or account API calls. */
(()=>{'use strict';
function install(){const $=id=>document.getElementById(id),profile=$('profile'),toolbar=profile.querySelector('.feature-toolbar');toolbar.querySelector('span').textContent='내 정보';
 const account=$('codeField').closest('.entry-auth-layout'),settings=$('boardThemeSelect').closest('.card'),danger=$('resetProfileV5').closest('.card');
 const info=document.createElement('section');info.id='profileInformation';info.setAttribute('aria-label','성장과 활동 기록');
 const guestAccount=$('guestAccountAccess');if(guestAccount)account.append(guestAccount);
 for(const sibling of [...account.children])if(sibling!==guestAccount&&!sibling.contains($('codeField')))info.append(sibling);
 const nav=document.createElement('nav');nav.id='profileSections';nav.className='btn-row';nav.setAttribute('aria-label','내 정보와 설정');toolbar.after(nav);
 for(const node of [...profile.children])if(![toolbar,nav,account,settings,danger].includes(node))info.append(node);
 profile.append(info,settings,account,danger);settings.id='profileSettings';danger.id='profileDataManagement';
 // The old combined heading belongs to account connection, not the growth report.
 const oldIntro=[...info.children].find(n=>n.querySelector?.('h2')?.textContent==='나의 기록 · 계정 연결');if(oldIntro){oldIntro.querySelector('h2').textContent='계정 연결';account.prepend(oldIntro);}
 const buttons=[];
 for(const [path,label]of [['profile','성장 · 활동 기록'],['profile/settings','표시 · 학습 설정'],['profile/account','계정 연결'],['profile/data','계정 기록 관리']]){const b=document.createElement('button');b.className='btn';b.textContent=label;b.onclick=()=>{window.cmaNavigation.go(path);const target=path==='profile'?info:path.endsWith('settings')?settings:path.endsWith('data')?danger:account;target.tabIndex=-1;target.focus({preventScroll:true});scrollTo({top:0,behavior:'instant'});};b.dataset.infoRoute=path;nav.append(b);buttons.push(b);}
 const interval=document.createElement('section');interval.setAttribute('aria-label','복습 간격 설정');const heading=document.createElement('h3');heading.textContent='학습 복습 간격';interval.append(heading);const original=$('learningIntervals').closest('details');for(const n of [...original.children])if(n.id!=='learningAttempts'&&n.tagName!=='SUMMARY')interval.append(n);settings.append(interval);
 function show(route=window.cmaNavigation.current()){if(!route.startsWith('profile'))return;if(route==='profile/settings')window.cmaLearningSettings.load();const path=route==='profile'&&!token?'profile/account':route;for(const [node,key]of [[info,'profile'],[settings,'profile/settings'],[account,'profile/account'],[danger,'profile/data']]){node.hidden=path!==key;node.inert=path!==key;}for(const b of buttons)b.setAttribute('aria-current',b.dataset.infoRoute===path?'page':'false');}
 window.cmaInfoLayout={show};$('loginNav').onclick=()=>window.cmaNavigation.go('profile/account');show();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
})();
