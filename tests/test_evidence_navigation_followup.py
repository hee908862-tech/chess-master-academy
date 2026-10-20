"""Narrow review follow-up: controlled Chromium state, no production accounts."""
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import site, page, open_page
from test_growth_browser import report_fixture, mock_status

OUT=Path('docs/qa-evidence-flow/review-followup')

def test_rules_first_home_action_reaches_recommended_basics(page,site):
    data=mock_status(page,report_fixture());data.update(latest=None,results=[],cycle=None)
    open_page(page,site)
    page.evaluate('cmaStartingLevel.open()')
    page.get_by_role('button',name='룰부터 배우기',exact=True).click()
    expect(page.locator('#foundationRecommendedTitle')).to_be_focused()
    title=page.locator('#foundationRecommendedTitle').inner_text()
    page.evaluate("tab('home')")
    expect(page.locator('#journeyHomeOpen')).to_have_text('기초 아카데미 이어하기')
    page.locator('#journeyHomeOpen').click()
    expect(page.locator('#learn')).to_have_class('view active')
    expect(page.locator('#foundationRecommendedTitle')).to_be_focused()
    expect(page.locator('#foundationRecommendedTitle')).to_have_text(title)
    expect(page.locator('#academyTactics')).not_to_have_attribute('open','')

@pytest.mark.parametrize('kind,target',[('active','diagnosis'),('training','training'),('retention','diagnosis')])
def test_home_primary_destination(page,site,kind,target):
    data=mock_status(page,report_fixture())
    def independent_foundations(route):
        saved=route.fetch().json();saved['rules_first']=False;route.fulfill(json=saved)
    page.route('**/api/foundations',independent_foundations)
    if kind=='active':data['active']={'phase':'question','question':{'fen':'8/8/8/8/8/8/4K3/7k w - - 0 1','legal':[]},'index':3,'total':24}
    if kind=='training':data['training']={'active':True}
    if kind=='retention':data['rechecks']={'mate':{'eligible':True,'reason':'7일 조건 충족'}}
    open_page(page,site)
    expect(page.locator('#journeyRefresh')).to_be_enabled()
    page.locator('#journeyHomeOpen').click()
    expect(page.locator('#'+target)).to_have_class('view active')
    if kind=='active':expect(page.locator('#journeyProgress')).to_have_text('4 / 24 문항')
    if kind=='retention':expect(page.get_by_role('button',name='선택 분야 7일 기억 확인',exact=True)).to_be_visible()


def test_previous_account_delayed_report_cannot_replace_current_home(page,site):
    old=mock_status(page,report_fixture())
    open_page(page,site);page.evaluate("tab('diagnosis')")
    expect(page.locator('#journeyRefresh')).to_be_enabled()
    page.evaluate("""() => {const original=api;window.oldIdentity=token;api=(path,...args)=>path==='/journey'?(token===window.oldIdentity?new Promise(r=>window.releaseOldAccount=r):Promise.resolve({active:null,latest:null,results:[],cycle:null})):original(path,...args);} """)
    page.locator('#journeyRefresh').click()
    page.evaluate("token='controlled-account-B';tab('home')")
    expect(page.locator('#journeyHomeOpen')).to_have_text('나의 분야별 실력 알아보기')
    page.evaluate('data=>window.releaseOldAccount(data)',old)
    expect(page.locator('#journeyResults')).to_be_empty()
    expect(page.locator('#journeyHomeOpen')).to_have_text('나의 분야별 실력 알아보기')
    expect(page.locator('#home')).to_have_class('view active')

@pytest.mark.parametrize('width,height,scale',[(900,420,1),(1280,480,1.5)])
def test_menu_short_height_text_enlargement_and_width_transition(page,site,width,height,scale):
    open_page(page,site);page.set_viewport_size({'width':width,'height':height})
    if scale!=1:page.add_style_tag(content=f'html{{font-size:{16*scale}px}} #academyNavigationDialog button{{font-size:{16*scale}px}}')
    opener=page.locator('.nav [data-tab="learn"]');opener.click()
    menu=page.locator('#academyNavigationDialog');expect(menu).to_be_visible()
    last=menu.locator('button').last;last.focus()
    expect(last).to_be_focused()
    bounds=menu.bounding_box();assert bounds['y']>=0 and bounds['y']+bounds['height']<=height+1
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    OUT.mkdir(exist_ok=True,parents=True)
    page.screenshot(path=str(OUT/f'menu-{width}-{height}.png'))
    page.keyboard.press('Escape');expect(menu).not_to_be_visible();expect(opener).to_be_focused()
    opener.click();page.set_viewport_size({'width':390,'height':700})
    expect(menu).not_to_be_visible()
    mobile=page.locator('.mobile-nav [data-tab="learn"]');mobile.click()
    expect(menu).to_be_visible();assert menu.evaluate("e=>e.matches(':modal')")
    page.keyboard.press('Escape');expect(mobile).to_be_focused()
    expect(page.locator('#home')).to_have_class('view active')
