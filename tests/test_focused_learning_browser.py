"""Focused navigation with real local state and read-only route transitions."""
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page,square
from test_study_browser import login

@pytest.mark.parametrize('width,height',[(320,800),(390,844),(485,757),(1280,720)])
def test_home_foundation_practice_list_history_no_writes(page,site,width,height):
    login(page,site);page.set_viewport_size(dict(width=width,height=height))
    page.locator('#homeBasicsOpen').click()
    expect(page.locator('#foundationPrimary')).to_be_visible()
    expect(page.locator('#academyHub')).not_to_be_visible()
    page.locator('#foundationPrimary button').click()
    expect(page.locator('#foundationWorkspace')).to_be_visible()
    square(page,'foundationBoard','a1').click();square(page,'foundationBoard','a4').click()
    page.locator('#foundationNext').get_by_role('button',name='다음 단계',exact=True).click()
    expect(page.locator('#foundationStepTitle')).to_contain_text('2/3')
    before=page.evaluate("api('/foundations')")
    writes=[];page.on('request',lambda r:writes.append(r.url) if '/api/' in r.url and r.method!='GET' else None)
    expect(page.locator('#foundationPrimary')).not_to_be_visible()
    expect(page.locator('#academyTactics')).not_to_be_visible()
    page.locator('#learn-list-back').click()
    expect(page.locator('#foundationWorkspace')).not_to_be_visible()
    expect(page.locator('#foundationPrimary')).to_be_visible()
    page.locator('#foundationPrimary button').click()
    expect(page.locator('#foundationStepTitle')).to_contain_text('2/3')
    page.locator('#learn-hub-back').click()
    expect(page.locator('#academyHub')).to_be_visible()
    assert page.locator('#academyHub .feature-options button').count()==6
    assert page.locator('#learn .board:visible').count()==0
    page.go_back();expect(page.locator('#foundationWorkspace')).to_be_visible()
    page.reload();expect(page.locator('#foundationStepTitle')).to_contain_text('2/3')
    expect(page.locator('#foundationWorkspace')).to_be_visible()
    assert page.evaluate("api('/foundations')")==before
    assert writes==[],writes
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    out=Path('/tmp/cma-focused-evidence');out.mkdir(exist_ok=True)
    page.screenshot(path=str(out/f'foundation-{width}.png'),full_page=True)


def test_tactics_selection_list_focus_and_education_menu(page,site):
    page.unroute('**/api/v9/catalog');login(page,site);page.evaluate("cmaAcademyNavigate('tactics')")
    expect(page.locator('#v9CourseCards')).to_be_visible()
    card=page.locator('#tactic-mateIn1');card.focus();page.keyboard.press('Enter')
    expect(page.locator('#v9LearnMode')).to_be_visible()
    expect(page.locator('#v9CourseCards')).not_to_be_visible()
    expect(page.locator('#v9CourseTitle')).to_be_focused()
    page.locator('#v9CourseBack').click()
    expect(card).to_be_focused()
    expect(page.locator('#v9LearnMode')).not_to_be_visible()
    page.locator('#learn-hub-back').click()
    page.locator('#learn-choice-education').click()
    expect(page.locator('#educationBody')).not_to_be_empty()
    expect(page.locator('#foundationAcademy')).not_to_be_visible()
    page.locator('.nav [data-tab=learn]').click()
    expect(page.locator('#learn-menu-education')).to_be_visible()
    page.keyboard.press('Escape')
    expect(page.locator('#educationPaths')).to_be_visible()


def test_education_list_return_and_url_whitelist_no_writes(page,site):
    login(page,site);page.evaluate("cmaNavigation.go('learn/education')")
    page.locator('#educationBody article').first.get_by_role('button',name='설명 보며 학습',exact=True).click()
    expect(page.locator('#educationBoard')).to_be_visible()
    saved=page.evaluate("api('/education')")
    writes=[];page.on('request',lambda r:writes.append(r.url) if '/api/' in r.url and r.method!='GET' else None)
    page.locator('#learn-list-back').click()
    expect(page.locator('#educationBoard')).not_to_be_visible()
    page.get_by_role('button',name='저장된 교육 실습 이어하기',exact=True).click()
    expect(page.locator('#educationBoard')).to_be_visible()
    page.reload();expect(page.locator('#educationBoard')).to_be_visible()
    assert page.evaluate("api('/education')")==saved
    assert writes==[]
    page.evaluate("cmaNavigation.go('learn/basics/private-session-123')")
    assert page.evaluate('location.hash')=='#home'


def test_hub_home_mobile_and_menu_does_not_change_selected_piece(page,site):
    login(page,site);page.locator('#homeBasicsOpen').click();page.locator('#foundationPrimary button').click()
    square(page,'foundationBoard','a1').click()
    before=page.evaluate("api('/foundations')")
    page.locator('.nav [data-tab=learn]').click();page.keyboard.press('Escape')
    expect(square(page,'foundationBoard','a1')).to_have_attribute('aria-pressed','true')
    assert page.evaluate("api('/foundations')")==before
    page.locator('#learn-hub-back').click()
    for w,h in [(320,640),(360,800),(390,844),(1366,768),(844,390)]:
        page.set_viewport_size(dict(width=w,height=h))
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        assert page.locator('#learn .board:visible').count()==0
        out=Path('/tmp/cma-focused-evidence');out.mkdir(exist_ok=True)
        page.screenshot(path=str(out/f'hub-{w}.png'),full_page=True)
    page.evaluate("tab('home')");page.set_viewport_size(dict(width=390,height=844))
    expect(page.locator('#homeBasicsOpen')).to_be_visible()
    assert page.locator('#homeBasics').bounding_box()['y']<page.locator('#journeyActivity').bounding_box()['y']
    page.screenshot(path='/tmp/cma-focused-evidence/home-390.png',full_page=True)


def test_list_focus_counts_and_485_geometry(page,site):
    import json
    login(page,site);page.set_viewport_size(dict(width=485,height=757))
    page.evaluate("window.uiClicks=0;document.addEventListener('click',()=>uiClicks++,true)")
    page.locator('#homeBasicsOpen').click();expect(page.locator('#foundationPrimary')).to_be_visible()
    counts={'home_to_foundation':page.evaluate('uiClicks')}
    page.locator('#foundationPrimary button').click();expect(page.locator('#foundationWorkspace')).to_be_visible()
    counts['home_to_first_practice']=page.evaluate('uiClicks')
    square(page,'foundationBoard','a1').click();square(page,'foundationBoard','a4').click()
    page.locator('#foundationNext').get_by_role('button',name='다음 단계',exact=True).click()
    expect(page.locator('#foundationStepTitle')).to_contain_text('2/3')
    counts['viewport']={'width':485,'height':757}
    counts['practice']=page.locator('#foundationWorkspace').bounding_box()
    counts['board']=page.locator('#foundationBoard').bounding_box()
    counts['document_height']=page.evaluate('document.documentElement.scrollHeight')
    page.screenshot(path='/tmp/cma-focused-evidence/practice-485-viewport.png')
    page.locator('#learn-list-back').click()
    expect(page.locator('#foundation-recommended-action')).to_be_focused()
    expect(page.locator('#foundationAcademy')).to_have_attribute('aria-busy','false')
    expect(page.locator('#foundation-recommended-action')).to_be_focused()
    assert counts['home_to_foundation']==1 and counts['home_to_first_practice']==2
    Path('/tmp/cma-focused-evidence/measurements.json').write_text(json.dumps(counts,ensure_ascii=False,indent=2))


def test_guest_foundation_login_route_and_ephemeral_trial_reload(page,site):
    page.add_init_script("localStorage.removeItem('chess_token')")
    page.goto(site[0]);page.locator('#homeBasicsOpen').click()
    page.get_by_role('button',name='계정 연결 후 시작',exact=True).click()
    page.locator('#codeField').fill('BROWSER-QA');page.locator('#pinField').fill('test-pin-9384');page.locator('#signin').click()
    expect(page.locator('#foundationPrimary')).to_be_visible()
    assert page.evaluate('location.hash')=='#learn/basics'
    page.evaluate('cmaEntry.openTrial()');page.reload()
    expect(page.locator('#home')).to_have_class('view active')
    expect(page.locator('#rookTrial')).not_to_be_visible()


def test_late_foundation_start_does_not_leave_hub(page,site):
    login(page,site);page.locator('#homeBasicsOpen').click()
    page.evaluate("""()=>{const real=api;api=async(...args)=>{if(args[0]==='/foundations/action'){const saved=await real(...args);return new Promise(r=>window.releaseFoundationStart=()=>r(saved));}return real(...args);};}""")
    page.locator('#foundationPrimary button').click();page.wait_for_function('!!window.releaseFoundationStart')
    page.locator('#learn-hub-back').click();page.evaluate('releaseFoundationStart()')
    expect(page.locator('#academyHub')).to_be_visible()
    expect(page.locator('#foundationWorkspace')).not_to_be_visible()
    assert page.evaluate('location.hash')=='#learn'


def test_hub_and_other_topics_do_not_record_training_exposure(page,site):
    login(page,site)
    before=page.evaluate("api('/learning/start','POST',{fresh:true})")
    writes=[];page.on('request',lambda r:writes.append(r.url) if '/api/' in r.url and r.method!='GET' else None)
    page.evaluate("tab('learn')");page.locator('#learn-choice-basics').click()
    page.locator('#learn-hub-back').click();page.locator('#learn-saved').click()
    expect(page.locator('#academyResume')).to_be_visible()
    assert writes==[],writes
    assert page.evaluate("api('/learning/dashboard')")['active']==before


def test_promotion_cancel_on_route_leave_without_saved_answer(page,site):
    login(page,site);page.evaluate("cmaNavigation.go('learn/education')")
    page.locator('#educationBody article').filter(has_text='승격').get_by_role('button',name='설명 보며 학습',exact=True).click()
    expect(page.locator('#educationBoard')).to_be_visible()
    before=page.evaluate("api('/education')")
    square(page,'educationBoard','g7').click();square(page,'educationBoard','g8').click()
    expect(page.locator('#cmaPromotionModal')).to_be_visible()
    page.evaluate("cmaNavigation.go('learn')")
    expect(page.locator('#cmaPromotionModal')).not_to_be_visible()
    assert page.evaluate("api('/education')")==before
    expect(page.locator('#academyHub')).to_be_visible()
