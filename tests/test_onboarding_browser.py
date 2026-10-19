"""Real Chromium tutorial controls with a controlled account API; not production QA."""
import os
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH', '/usr/bin/chromium'), args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 390, 'height': 620})
        page.set_default_timeout(5000)
        yield page
        browser.close()


def boot(page, *, authenticated=True, deferred=False, status='not_started'):
    page.set_content('''<main class="main"><section id="profile"></section><section id="help"></section>
      <input id="pinField"><button id="signout">logout</button><button id="launch">login</button></main>''')
    page.add_style_tag(path=str(ROOT/'public/onboarding.css'))
    page.evaluate('''({authenticated,deferred,status}) => {
      window.token=authenticated?'account-1':'';
      window.saved={version:1,status,step:0,defer_auto:deferred}; window.tabs=[];window.requests=[];
      window.api=async(path,method,body)=>{requests.push({path,method,body});
        if(method==='POST'&&!['completed','skipped'].includes(saved.status))Object.assign(saved,body);
        return {...saved};};
      window.auth=async()=>{token='account-1';document.getElementById('pinField').value='';};
      window.tab=id=>tabs.push(id);window.ready=()=>false;
      document.getElementById('launch').onclick=()=>auth('signin');
    }''', {'authenticated': authenticated, 'deferred': deferred, 'status': status})
    page.add_script_tag(path=str(ROOT/'public/onboarding.js'))


def test_first_login_skip_reopen_keyboard_and_no_automatic_start(page):
    boot(page, authenticated=False)
    expect(page.locator('#onboardingDialog')).not_to_be_visible()
    page.locator('#pinField').fill('example-pin')
    page.locator('#launch').click()
    expect(page.locator('#onboardingDialog')).to_be_visible()
    expect(page.locator('#onboardingTitle')).to_be_focused()
    page.keyboard.press('Escape')
    expect(page.locator('#onboardingDialog')).not_to_be_visible()
    expect(page.locator('#launch')).to_be_focused()
    assert page.evaluate('saved.status') == 'skipped'
    page.evaluate('cmaOnboarding.check(true)')
    expect(page.locator('#onboardingDialog')).not_to_be_visible()
    page.locator('#profile .onboarding-replay').click()
    expect(page.locator('#onboardingDialog')).to_be_visible()
    for _ in range(3): page.locator('#onboardingNext').click()
    expect(page.locator('#onboardingNext')).to_have_text('안내 완료 · 진단 화면 보기')
    page.locator('#onboardingNext').click()
    assert page.evaluate('tabs') == ['diagnosis']
    assert page.evaluate('saved.status') == 'skipped'  # replay preserves completion preference
    assert page.evaluate("requests.every(r=>r.path==='/onboarding')")


def test_existing_token_invitation_focus_trap_and_mobile_fit(page):
    boot(page)
    expect(page.locator('#onboardingInvitation')).to_be_visible()
    expect(page.locator('#onboardingDialog')).not_to_be_visible()
    page.locator('#onboardingInvitation button').click()
    expect(page.locator('#onboardingDialog')).to_be_visible()
    page.locator('#onboardingNext').focus()
    page.keyboard.press('Tab')
    assert page.evaluate("document.getElementById('onboardingDialog').contains(document.activeElement)")
    box = page.locator('#onboardingDialog').bounding_box()
    assert box['x'] >= 0 and box['x'] + box['width'] <= 390
    assert box['y'] >= 0 and box['y'] + box['height'] <= 620
    for _ in range(4): page.locator('#onboardingNext').click()
    assert page.evaluate('saved.status') == 'completed'
    page.evaluate('cmaOnboarding.check(true)')
    expect(page.locator('#onboardingDialog')).not_to_be_visible()
    expect(page.locator('#onboardingInvitation')).not_to_be_visible()


def test_active_session_defers_and_failed_save_still_closes(page):
    boot(page, authenticated=False, deferred=True)
    page.locator('#pinField').fill('example-pin'); page.locator('#launch').click()
    expect(page.locator('#onboardingInvitation')).to_be_visible()
    expect(page.locator('#onboardingDialog')).not_to_be_visible()
    page.locator('#onboardingInvitation button').click()
    expect(page.locator('.onboarding-clock')).to_contain_text('멈추지 않습니다')
    page.evaluate("() => { api=async()=>{throw Error('offline')}; }")
    page.locator('#onboardingSkip').click()
    expect(page.locator('#onboardingDialog')).not_to_be_visible()
    expect(page.locator('#onboardingInvitation')).to_contain_text('저장하지 못해')


def test_pending_save_does_not_trap_close_or_navigate_later(page):
    boot(page)
    page.locator('#onboardingInvitation button').click()
    for _ in range(3): page.locator('#onboardingNext').click()
    page.evaluate("() => { api=()=>new Promise(resolve=>window.finishSave=resolve); }")
    page.locator('#onboardingNext').click()
    page.keyboard.press('Escape')
    expect(page.locator('#onboardingDialog')).not_to_be_visible()
    page.evaluate("() => finishSave({version:1,status:'completed',step:3,defer_auto:false})")
    assert page.evaluate('tabs') == []
