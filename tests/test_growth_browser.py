"""Controlled result/error fixtures in real Chromium; temporary local accounts only."""
import copy
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page,open_page
from competencies import COMPETENCIES
from growth_model import decorate,cycle_status


def report_fixture(kind='normal',number=1):
    items=[];areas=[]
    for c,spec in COMPETENCIES.items():
        rows=[]
        if spec['measured']:
            for i in range(4):
                completed=kind!='empty' and (c in ('mate','promotion') or i%2==0)
                rows.append({'id':c+str(i),'puzzle_id':c+str(i),'competency':c,'band':[600,1200] if i<2 else [1200,1800],
                             'outcome':'not_answered' if kind=='empty' else 'completed' if completed else 'partial_execution',
                             'app_new':True,'helped':False,'complete':completed,'submitted':[] if kind=='empty' else ['a2a3'],
                             'correct_plies':0 if kind=='empty' else 2 if completed else 1,'total_plies':2,'fen':'8/8/8/8/8/8/4K3/7k w - - 0 1','line':['e2e3']})
        items+=rows
        areas.append({'id':c,'label':spec['label'],'count':len(rows),'full_success':sum(r['complete'] for r in rows),'first_success':sum(bool(r['submitted']) for r in rows),'partial':sum(r['outcome']=='partial_execution' for r in rows),'unverified':0,'items':rows})
    return decorate({'id':str(number),'at':f'2026-10-{10+number}T10:00:00+00:00','version':'journey-v4','competency_version':'competency-v2','measurement_scope':'uncued_execution','mode':'balanced','areas':areas,'items':items})


def mock_status(page,report):
    previous=report_fixture(number=1)
    cycle=cycle_status(report,{})
    data={'latest':report,'active':None,'results':[previous,report],'cycle':cycle,'competencies':[{'id':k,**v} for k,v in COMPETENCIES.items()]}
    page.route('**/api/onboarding',lambda r:r.fulfill(json={'status':'completed','version':1}))
    page.route('**/api/journey',lambda r:r.fulfill(json=data))
    return data


@pytest.mark.parametrize('width',[320,360,390,430,768,900,1024,1280,1440])
def test_results_growth_and_long_korean_layout(page,site,width):
    page.set_viewport_size({'width':width,'height':1000})
    report=report_fixture(number=2);report['areas'][0]['observation']+=' '+'긴 설명에서도 조사와 문장이 자연스럽게 이어지는지 확인합니다. '*4
    mock_status(page,report)
    page.route('**/api/games/analysis',lambda r:r.fulfill(json={'games':[],'average':None,'rating_reason':'검증된 환산 모델이 없어 산출하지 않습니다.'}))
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    open_page(page,site);page.evaluate("tab('diagnosis')")
    expect(page.locator('.ability-card')).to_have_count(7)
    expect(page.get_by_role('button',name='새 문제로 다시 진단하기',exact=True)).to_be_disabled()
    expect(page.locator('.ability-card').last).to_contain_text('측정 전')
    directory=Path(__file__).resolve().parents[1]/'docs/qa-growth';directory.mkdir(exist_ok=True)
    for view in ['home','diagnosis','profile','training','help','review']:
        page.evaluate('tab('+repr(view)+')')
        page.wait_for_timeout(100)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),(width,view,page.evaluate("[...document.querySelectorAll('.view.active *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,8).map(e=>[e.tagName,e.id,e.className,e.getBoundingClientRect().width])"))
        if view in ('home','diagnosis','profile'):page.screenshot(path=str(directory/f'{view}-{width}.png'),full_page=True)
    page.evaluate("tab('profile')")
    expect(page.locator('#growthProfile svg circle')).to_have_count(2)
    expect(page.locator('#gamePerformance')).to_contain_text('산출 보류')
    assert not errors,errors


def test_empty_result_error_loading_and_double_size(page,site):
    page.set_viewport_size({'width':1440,'height':1000})
    data=mock_status(page,report_fixture('empty',2));data['results']=[data['latest']]
    page.route('**/api/games/analysis',lambda r:r.fulfill(status=503,json={'detail':'분석 기록을 잠시 불러오지 못했어요.'}))
    open_page(page,site);page.evaluate("tab('diagnosis')")
    expect(page.locator('.growth-intro')).to_contain_text('아직 직접 둔 수가 없어요')
    expect(page.locator('.ability-card').first).to_contain_text('측정 전')
    page.evaluate("document.documentElement.style.zoom='200%'")
    for view in ('home','diagnosis','profile'):
        page.evaluate('tab('+repr(view)+')');page.wait_for_timeout(150)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),view
    assert page.locator('#profile input').first.bounding_box()['width']>=200
    expect(page.locator('#gamePerformance')).to_contain_text('분석 기록을 잠시')
    expect(page.get_by_role('button',name='다시 확인',exact=True)).to_be_enabled()
    page.screenshot(path=str(Path(__file__).resolve().parents[1]/'docs/qa-growth/empty-error-200percent.png'),full_page=True)


def test_chart_breaks_missing_and_incompatible_points(page,site):
    data=mock_status(page,report_fixture(number=4))
    first=report_fixture(number=1);second=report_fixture(number=2);third=report_fixture(number=3)
    second['snapshot']['mode']='quick';second['snapshot']['areas']['mate']['comparable']=False
    third['snapshot']['areas']['mate']['score']=None
    data['results']=[first,second,third,data['latest']]
    page.route('**/api/games/analysis',lambda r:r.fulfill(json={'games':[{'game_key':'x','at':'2026-10-20','status':'running','color':'black'}],'average':None,'rating_reason':'산출 보류'}))
    open_page(page,site);page.evaluate("tab('profile')")
    expect(page.locator('#growthProfile circle')).to_have_count(3)
    expect(page.locator('#growthProfile line[stroke="#8fe5c8"]')).to_have_count(0)
    expect(page.locator('#gamePerformance')).to_contain_text('분석 중')
    expect(page.locator('#gamePerformance circle')).to_have_count(0)
    page.screenshot(path=str(Path(__file__).resolve().parents[1]/'docs/qa-growth/partial-analysis-loading.png'),full_page=True)


def test_recommendation_button_routes_task_and_unlock_stays_server_owned(page,site):
    data=mock_status(page,report_fixture(number=2));calls=[]
    def start(route):calls.append(route.request.post_data_json);route.fulfill(status=409,json={'detail':'진행 중인 훈련을 먼저 마쳐 주세요.'})
    page.route('**/api/learning/cycle/start',start)
    open_page(page,site);page.evaluate("tab('diagnosis')")
    page.get_by_role('button',name='설명과 함께 다시 익히기',exact=True).first.click()
    expect(page.locator('#learningMessage')).to_contain_text('진행 중인 훈련')
    assert calls==[{'report_id':'2','item_id':'1'}]
