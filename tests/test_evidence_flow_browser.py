"""Controlled state coverage in Chromium; not measured educational effectiveness."""
import copy
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page,open_page
from test_growth_browser import report_fixture,mock_status
from journey_evidence import learning_observation

@pytest.mark.parametrize('condition,label',[
 ('new','나의 분야별 실력 알아보기'),('active','저장된 진단 이어하기'),
 ('training','진행 중인 훈련 이어하기'),('incomplete','추천 훈련 이어가기'),
 ('unlocked','새 문제로 다시 진단하기'),('retention','7일 기억 유지 확인 보기'),
 ('preparing','준비 상태 확인'),('error','저장 상태 다시 확인')])
def test_home_one_next_step_with_explicit_estimate(page,site,condition,label):
    report=report_fixture();data=mock_status(page,report)
    if condition=='new':data.update(latest=None,results=[],cycle=None)
    if condition=='active':
        from test_journey_browser import question
        data['active']={**question(),'total':24}
    if condition=='training':data['training']={'active':True}
    if condition=='unlocked':data['cycle']['unlocked']=True
    if condition=='retention':data['rechecks']={'mate':{'eligible':True}}
    if condition=='preparing':data['preparing']=True
    if condition=='error':page.route('**/api/journey',lambda r:r.fulfill(status=503,json={'detail':'자료를 준비하지 못했습니다.'}))
    open_page(page,site);page.evaluate("tab('home')")
    page.locator("#flowSavedActivities > summary").click()
    expect(page.locator('#journeyHomeOpen')).to_have_text(label)
    if condition not in ('error','preparing'):expect(page.locator('#journeyHomeEstimate')).to_contain_text('추정')
    expect(page.locator('#homeExplore')).not_to_have_attribute('open','')
    assert page.locator('#journeyHome button:visible').count()==1

@pytest.mark.parametrize('width',[390,1280])
def test_traceable_recommendation_and_selected_independent_check(page,site,width):
    page.set_viewport_size({'width':width,'height':950})
    report=report_fixture();data=mock_status(page,report)
    for item in report['items']:
        item.update(fen='rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',line=['e2e4','e7e5','g1f3'],submitted=['e2e4'])
    data['learning_evidence']={report['id']:{i['id']:learning_observation(i) for i in report['items']}}
    data['rechecks']={'mate':{'eligible':False,'reason':'새 전체 수순 확인이 필요합니다.'},'promotion':{'eligible':True,'reason':'7일 조건 충족'}}
    requests=[]
    page.route('**/api/journey/start',lambda r:(requests.append(r.request.post_data_json),r.fulfill(status=409,json={'detail':'진행 중 기록을 보존했습니다.'})))
    open_page(page,site);page.evaluate("tab('diagnosis')")
    summary=page.locator('#journeyResults .growth-abilities')
    expect(summary).to_be_visible()
    expect(summary.locator('.ability-card')).to_have_count(7)
    for card in summary.locator('.ability-card').all():
        expect(card.locator('.ability-score')).to_be_visible()
        expect(card.locator('details')).not_to_have_attribute('open','')
    assert summary.evaluate("e=>!!(e.compareDocumentPosition(document.querySelector('#journeyResults .growth-plan')) & Node.DOCUMENT_POSITION_FOLLOWING)")
    expect(page.locator('.growth-plan')).to_contain_text('5개 완료는 학습량이며 독립 숙련이 아닙니다.')
    expect(page.locator('.learning-observation').first).to_contain_text('실제 제출: e4')
    expect(page.locator('.learning-observation').first).to_contain_text('Nf3')
    expect(page.locator('.growth-plan')).to_contain_text('정교한 구조 유사성을 보장하지 않습니다.')
    field=page.get_by_role('combobox',name='기억 확인 분야');field.select_option('promotion')
    page.get_by_role('button',name='선택 분야 7일 기억 확인',exact=True).click()
    expect(page.locator('#journeyMessage')).to_contain_text('진행 중 기록을 보존했습니다.')
    assert requests==[{'mode':'recheck','competency':'promotion'}]
    expect(field).to_be_disabled()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    out=Path('docs/qa-evidence-flow');out.mkdir(exist_ok=True)
    page.screenshot(path=str(out/f'evidence-{width}.png'),full_page=True)
    page.evaluate("tab('home')");expect(page.locator('#journeyHomeOpen')).to_have_text('7일 기억 유지 확인 보기')
    page.screenshot(path=str(out/f'home-{width}.png'),full_page=True)


def test_pc_disclosure_tab_leaves_without_navigation(page,site):
    open_page(page,site);page.set_viewport_size({'width':1280,'height':950})
    nav=page.locator('.nav [data-tab="learn"]');nav.click()
    menu=page.locator('#academyNavigationDialog');expect(menu).to_be_visible()
    assert not menu.evaluate("e=>e.matches(':modal')")
    page.locator('#academyNavigationDialog button').last.focus();page.keyboard.press('Tab')
    expect(menu).not_to_be_visible();expect(page.locator('#home')).to_contain_class('view active')
    nav.click();page.locator('#homeNextAction h2').click()
    expect(menu).not_to_be_visible();expect(nav).to_have_attribute('aria-expanded','false')


def test_late_status_refresh_keeps_explicit_history_selection(page,site):
    report=report_fixture(number=2);data=mock_status(page,report)
    open_page(page,site);page.evaluate("tab('diagnosis')")
    expect(page.locator('#journeyRefresh')).to_be_enabled()
    page.evaluate("""() => {const original=api;api=(path,...args)=>path==='/journey'?new Promise(resolve=>window.releaseHistoryStatus=resolve):original(path,...args);} """)
    page.locator('#journeyRefresh').click()
    page.locator('#journeyPast > summary').click()
    select=page.get_by_role('combobox',name='저장된 진단 선택');select.select_option('1')
    expect(page.locator('#journeyPastReport .ability-card')).to_have_count(7)
    page.evaluate('data=>window.releaseHistoryStatus(data)',data)
    expect(page.locator('#journeyRefresh')).to_be_enabled()
    expect(page.locator('#journeyPast')).to_have_attribute('open','')
    expect(select).to_have_value('1')
    expect(page.locator('#journeyPastReport .ability-card')).to_have_count(7)
    page.evaluate("document.getElementById('signout').click()")
    expect(page.locator('#journeyPastReport')).to_be_empty()
    expect(page.locator('#journeyPast')).not_to_have_attribute('open','')
