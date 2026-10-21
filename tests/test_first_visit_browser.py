"""Fresh browser contexts and real disposable local accounts. Never production."""
import json
from pathlib import Path
import secrets
import pytest
from playwright.sync_api import sync_playwright,expect
from test_qa_browser import site,square

@pytest.fixture
def guest(site):
    with sync_playwright() as p:
        b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=b.new_page(viewport={'width':390,'height':844});page.set_default_timeout(10000)
        page.goto(site[0]);page.wait_for_timeout(500)
        yield page
        b.close()

def trial(page):
    page.locator('#firstTry').click();square(page,'trialBoard','a1').click();square(page,'trialBoard','a4').click()
    expect(page.locator('#trialContinue')).to_be_visible()

def test_fresh_trial_keyboard_skip_reload_no_server_writes(guest,site):
    p=guest;writes=[];p.on('request',lambda r:writes.append(r.url) if '/api/' in r.url and r.method!='GET' else None)
    expect(p.locator('#firstTry')).to_be_visible();expect(p.locator('#firstSkip')).to_be_visible()
    p.locator('#firstTry').click();square(p,'trialBoard','a1').focus();p.keyboard.press('Enter')
    expect(square(p,'trialBoard','a1')).to_be_focused()
    square(p,'trialBoard','b2').click();expect(p.locator('#trialContinue')).to_be_hidden()
    square(p,'trialBoard','a1').focus();p.keyboard.press('ArrowUp');p.keyboard.press('ArrowUp');p.keyboard.press('ArrowUp');p.keyboard.press('Enter');expect(p.locator('#trialContinue')).to_be_visible()
    p.locator('#trialSkip').click();expect(p.locator('#entryChoices')).to_be_visible()
    assert p.evaluate("localStorage.getItem('cma_entry_preference_v1')")=='explore'
    p.reload();expect(p.locator('#entryChoices')).to_be_visible();p.locator('#firstTry').click()
    expect(p.locator('#trialContinue')).to_be_hidden();expect(square(p,'trialBoard','a1')).to_have_attribute('aria-label',__import__('re').compile('a1 백 룩'))
    p.locator('#trialExit').click();assert writes==[]
    assert not p.evaluate("localStorage.getItem('chess_token')")


def test_signup_from_trial_starts_real_first_step_without_transferring_success(guest,site):
    p=guest;trial(p);p.locator('#trialContinue').click();expect(p.locator('#entryLoginNotice')).to_be_visible()
    p.locator('#codeField').fill('FIRST-'+secrets.token_hex(4));p.locator('#pinField').fill('trial-test-pin42');p.locator('#signup').click()
    expect(p.locator('#foundationWorkspace')).to_be_visible(timeout=20000)
    expect(p.locator('#foundationStepTitle')).to_contain_text('룩은 직선으로')
    expect(p.locator('#startingLevelDialog')).to_be_hidden()
    d=p.evaluate("api('/foundations')");assert d['completed']==0 and not d['active']['solved'] and d['active']['step']==0
    assert 'R5K1' in d['active']['fen']
    assert p.evaluate("api('/me')")['stats']['games']==0
    expect(p.locator('#academyTactics')).not_to_have_attribute('open','')
    p.wait_for_function("()=>{const b=document.getElementById('foundationBoard').getBoundingClientRect(),n=document.querySelector('.mobile-nav').getBoundingClientRect();return b.top>=0&&b.bottom<=n.top}")
    Path('/tmp/cma-first-visit-captures').mkdir(exist_ok=True);p.screenshot(path='/tmp/cma-first-visit-captures/formal-first-viewport.png')


def test_existing_login_keeps_saved_activity_and_cancel_is_safe(guest,site):
    p=guest;code='RETURN-'+secrets.token_hex(4)
    saved=p.evaluate("async code=>{const r=await api('/register','POST',{code,pin:'trial-test-pin42'});token=r.token;const d=await api('/foundations');await api('/foundations/action','POST',{action:'start',course_id:'knight-queen',revision:d.revision,step:0});const s=await api('/foundations');token='';return s;}",code)
    trial(p);p.locator('#trialContinue').click();p.locator('#entryLoginCancel').click()
    expect(p.locator('#home')).to_have_class('view active')
    trial(p);p.locator('#trialContinue').click();p.locator('#codeField').fill(code);p.locator('#pinField').fill('trial-test-pin42');p.locator('#signin').click()
    expect(p.locator('#entryReturn')).to_be_visible(timeout=20000)
    assert p.evaluate("api('/foundations')")==saved
    expect(p.locator('#homeBasics')).to_contain_text('나이트와 퀸')
    expect(p.locator('#homeBasicsOpen')).to_contain_text('기초 배우기 이어하기')

@pytest.mark.parametrize('width,height',[(1366,768),(360,800),(320,640),(844,390)])
def test_guest_layout_and_all_destinations_require_auth(guest,site,width,height):
    p=guest;p.set_viewport_size(dict(width=width,height=height))
    Path('/tmp/cma-first-visit-captures').mkdir(exist_ok=True);p.screenshot(path=f'/tmp/cma-first-visit-captures/home-{width}.png',full_page=True)
    p.locator('#firstTry').click()
    assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
    for id in ['trialSkip','trialExit']:
        p.locator('#'+id).scroll_into_view_if_needed();expect(p.locator('#'+id)).to_be_visible()
    Path('/tmp/cma-first-visit-captures').mkdir(exist_ok=True);p.screenshot(path=f'/tmp/cma-first-visit-captures/trial-{width}.png',full_page=True)
    p.locator('#trialSkip').click();p.locator('#entry-play').click();p.locator('#newGame').click()
    expect(p.locator('#profile')).to_have_class('view active')
    assert not p.evaluate('token')
    for endpoint in ['/foundations','/journey','/game','/learning/dashboard']:
        r=p.request.get(site[0]+'/api'+endpoint);assert r.status==401,(endpoint,r.status)


def test_cancel_late_login_cannot_replace_new_account_or_start_old_path(guest,site):
    p=guest
    old=p.evaluate("async()=>api('/register','POST',{code:'LATE-'+Math.random().toString(36).slice(2),pin:'trial-test-pin42'})")
    trial(p);p.locator('#trialContinue').click()
    waits=[];p.route('**/api/login',lambda r:waits.append(r))
    p.locator('#codeField').fill('LATE-LOGIN');p.locator('#pinField').fill('trial-test-pin42');p.locator('#signin').click()
    for _ in range(100):
        if waits:break
        p.wait_for_timeout(20)
    assert len(waits)==1
    p.locator('#entryLoginCancel').click();trial(p);p.locator('#trialContinue').click()
    p.locator('#codeField').fill('NEW-'+secrets.token_hex(4));p.locator('#pinField').fill('trial-test-pin42');p.locator('#signup').click()
    expect(p.locator('#foundationWorkspace')).to_be_visible(timeout=20000)
    current=p.evaluate('token');snapshot=p.evaluate("api('/foundations')")
    waits[0].fulfill(json=old);p.wait_for_timeout(300)
    assert p.evaluate('token')==current and p.evaluate("api('/foundations')")==snapshot
    expect(p.locator('#learn')).to_have_class('view active')


def test_login_error_cancel_and_zoom(guest,site):
    p=guest;trial(p);p.locator('#trialContinue').click()
    p.locator('#codeField').fill('MISSING-'+secrets.token_hex(4));p.locator('#pinField').fill('wrong-pin')
    with p.expect_response('**/api/login') as response:p.locator('#signin').click()
    assert response.value.status==401
    expect(p.locator('#accountStatus')).not_to_contain_text('로그인되었습니다')
    expect(p.locator('#entryLoginNotice')).to_be_visible()
    p.locator('#entryLoginCancel').click();p.set_viewport_size(dict(width=1280,height=720))
    p.evaluate("document.documentElement.style.zoom='2'")
    assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
    p.locator('#firstTry').click();p.locator('#trialSkip').scroll_into_view_if_needed()
    expect(p.locator('#trialSkip')).to_be_visible();assert p.evaluate('document.documentElement.scrollWidth<=innerWidth')
    p.screenshot(path='/tmp/cma-first-visit-captures/zoom-200.png',full_page=True)

@pytest.mark.parametrize('return_to_learn',[False,True])
def test_delayed_foundations_after_signup_does_not_start_after_leaving(guest,site,return_to_learn):
    p=guest;trial(p);p.locator('#trialContinue').click()
    waits=[];posts=[]
    p.route('**/api/foundations',lambda r:waits.append(r))
    p.on('request',lambda r:posts.append(r.url) if '/foundations/action' in r.url else None)
    p.locator('#codeField').fill('DELAY-'+secrets.token_hex(4));p.locator('#pinField').fill('trial-test-pin42');p.locator('#signup').click()
    for _ in range(200):
        if waits:break
        p.wait_for_timeout(20)
    assert waits
    p.evaluate("tab('play')")
    if return_to_learn:p.evaluate("tab('learn')")
    saved=p.request.get(site[0]+'/api/foundations',headers={'Authorization':'Bearer '+p.evaluate('token')}).json()
    for r in list(waits):r.fulfill(json=saved)
    p.unroute('**/api/foundations')
    p.wait_for_timeout(500)
    assert not posts
    assert p.evaluate("document.querySelector('.view.active').id")==('learn' if return_to_learn else 'play')
    assert p.evaluate("api('/foundations')")['active'] is None


def test_returning_action_precedes_optional_guides_and_group_location(guest,site):
    p=guest;trial(p);p.locator('#trialContinue').click()
    p.locator('#codeField').fill('HOME-'+secrets.token_hex(4));p.locator('#pinField').fill('trial-test-pin42');p.locator('#signup').click()
    expect(p.locator('#foundationWorkspace')).to_be_visible(timeout=20000)
    p.evaluate("tab('home')")
    expect(p.locator('#homeBasicsOpen')).to_contain_text('기초 배우기 이어하기')
    expect(p.locator('#onboardingInvitation')).to_be_hidden();expect(p.locator('#startingLevelInvitation')).to_be_hidden()
    r=p.locator('#homeBasicsOpen').bounding_box();assert r['y']>=0 and r['y']+r['height']<p.locator('.mobile-nav').bounding_box()['y']
    p.locator('#homeExplore > summary').click();expect(p.locator('#startingLevelInvitation')).to_be_visible()
    for view,group in [('training','learn'),('puzzle','learn'),('opening','learn'),('review','profile'),('diagnosis','diagnosis')]:
        p.evaluate('id=>tab(id)',view)
        expect(p.locator(f'.mobile-nav [data-tab={group}]')).to_have_attribute('aria-current','page')
    p.evaluate("tab('home')");p.screenshot(path='/tmp/cma-first-visit-captures/returning-home-final.png',full_page=True)


def test_skip_prioritizes_activities_and_preserves_revisit_preference(guest,site):
    p=guest
    expect(p.locator('#firstTry')).to_have_class('btn primary')
    p.locator('#firstSkip').click()
    expect(p.locator('#firstSkip')).to_be_hidden()
    expect(p.locator('#entryChoices h2')).to_be_focused()
    expect(p.locator('#entry-diagnosis')).to_have_class('btn primary')
    expect(p.locator('#firstTry')).to_have_class('btn')
    assert p.evaluate("document.getElementById('firstEntry').firstElementChild.id")=='entryChoices'
    for id in ['entry-diagnosis','entry-training','entry-play','entry-learn']:
        assert p.locator('#'+id).bounding_box()['y']<p.locator('#firstTry').bounding_box()['y']
    p.keyboard.press('Tab');expect(p.locator('#entry-diagnosis')).to_be_focused()
    p.wait_for_timeout(250)  # Allow the existing button style transition to settle for capture.
    p.screenshot(path='/tmp/cma-first-visit-captures/skip-choices.png',full_page=True)
    p.reload();expect(p.locator('#firstSkip')).to_be_hidden()
    expect(p.locator('#entryChoices')).to_be_visible()
    p.locator('#firstTry').click();expect(p.locator('#trialSkip')).to_be_visible()
    p.locator('#trialSkip').click();expect(p.locator('#entryChoices h2')).to_be_focused()
    expect(p.locator('#firstSkip')).to_be_hidden()
    assert not p.evaluate('token')


def test_late_logout_cannot_clear_new_login_and_failure_preserves_account(guest,site):
    p=guest
    def login_new(prefix):
        p.evaluate("tab('profile')")
        p.locator('#codeField').fill(prefix+secrets.token_hex(4))
        p.locator('#pinField').fill('trial-test-pin42')
        p.locator('#signup').click()
        expect(p.locator('#home')).to_have_class('view active')
        return p.evaluate('token')
    first=login_new('OUT-A-')
    waits=[];p.route('**/api/logout',lambda r:waits.append(r))
    p.evaluate("tab('profile')");p.locator('#signout').click()
    p.wait_for_function("()=>document.getElementById('signup').disabled===false")
    for _ in range(100):
        if waits:break
        p.wait_for_timeout(20)
    assert len(waits)==1
    p.evaluate("cmaEntry.cancel();tab('home')")
    second=login_new('OUT-B-');assert second!=first
    before=p.evaluate("api('/foundations')")
    waits[0].fulfill(json={'ok':True});p.wait_for_timeout(200)
    assert p.evaluate('token')==second
    assert p.evaluate("localStorage.getItem('chess_token')")==second
    assert p.evaluate("api('/foundations')")==before
    expect(p.locator('#home')).to_have_class('view active')
    p.unroute('**/api/logout')
    p.route('**/api/logout',lambda r:r.fulfill(status=503,json={'detail':'temporary test failure'}))
    p.evaluate("tab('profile')");p.locator('#signout').click()
    expect(p.locator('#accountStatus')).to_contain_text('로그아웃하지 못했습니다')
    assert p.evaluate('token')==second
    p.unroute('**/api/logout');p.locator('#signout').click()
    expect(p.locator('#userBadge')).to_have_text('게스트')
    assert not p.evaluate('token') and not p.evaluate("localStorage.getItem('chess_token')")


def test_entry_primary_contrast_initial_skip_and_returning(guest,site):
    import re
    p=guest
    def check(selector):
        el=p.locator(selector)
        el.focus()
        colors=el.evaluate("e=>{const s=getComputedStyle(e);return {fg:s.color,bg:s.backgroundImage,outline:s.outlineStyle}}")
        def luminance(rgb):
            v=[int(x)/255 for x in rgb]
            v=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in v]
            return sum(a*b for a,b in zip(v,[.2126,.7152,.0722]))
        fg=luminance(re.findall(r'\d+',colors['fg'])[:3])
        stops=re.findall(r'rgb\((\d+), (\d+), (\d+)\)',colors['bg'])
        assert len(stops)==2,colors
        ratios=[(max(fg,luminance(c))+.05)/(min(fg,luminance(c))+.05) for c in stops]
        assert min(ratios)>=4.5,(selector,ratios)
        expect(el).to_be_focused()
        print(selector,'gradient contrast',ratios,'focus',colors['outline'])
    check('#firstTry')
    p.locator('#firstSkip').click();check('#entry-diagnosis')
    p.wait_for_timeout(250)  # Allow the existing button style transition to settle for capture.
    p.screenshot(path='/tmp/cma-first-visit-captures/skip-choices.png',full_page=True)
    p.reload();check('#entry-diagnosis')
    p.evaluate("t=>localStorage.setItem('chess_token',t)",site[1]);p.reload()
    expect(p.locator('#journeyHomeOpen')).to_be_visible()
    check('#journeyHomeOpen')


@pytest.mark.parametrize('signed_in',[False,True])
def test_trial_continue_label_matches_authentication(guest,site,signed_in):
    p=guest
    if signed_in:
        p.evaluate("t=>localStorage.setItem('chess_token',t)",site[1]);p.reload()
    writes=[];p.on('request',lambda r:writes.append(r.url) if '/api/' in r.url and r.method!='GET' else None)
    p.evaluate('cmaEntry.openTrial()')
    square(p,'trialBoard','a1').click();square(p,'trialBoard','a4').click()
    expect(p.locator('#trialContinue')).to_have_text('계속 배우기 · 저장된 활동 보기' if signed_in else '계속 배우기 · 로그인하고 기초 시작')
    assert writes==[]
