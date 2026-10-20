"""Journey UI protocol tests in Chromium; controlled grading responses, no production data."""
import copy
import json
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright, expect
from test_qa_browser import site

FEN='8/8/8/8/8/4r3/5k2/1R5K b - - 0 1'

def question():
    return {'session_id':'journey-test','revision':0,'phase':'question','index':0,'total':2,'version':'journey-v2','question':{'id':'item1','fen':FEN,'legal':['e3h3','e3e2'],'side':'black','competency':'mate','label':'메이트 수순','goal':'상대 응수 뒤에도 끝까지 메이트를 완성하세요.','ply':0,'total_plies':2}}

def report():
    return {'id':'report-test','version':'journey-v2','at':'2026-10-19','areas':[{'id':'mate','label':'메이트 수순','count':2,'independent':1,'first_success':1,'full_success':0,'partial':1,'confidence':'근거 부족','reason':'첫수 이후 수순을 더 확인합니다.','items':[{'id':'item1','puzzle_id':'test-position','fen':FEN,'first_correct':True,'complete':False,'correct_plies':1,'total_plies':2,'submitted':['e3h3'],'expected':['e3h3'],'reason':'후속 수순 미완료'}]}],'recommendations':[{'competency':'mate','label':'메이트 수순','item_id':'item1','reason':'후속 수순을 놓친 문항의 원리를 훈련합니다.'}],'limitations':['교육 효과 자체를 검증한 결과가 아닙니다.'],'comparison':'동일 버전의 적격 독립 근거만 비교합니다.'}

@pytest.mark.parametrize('width,height',[(1366,768),(390,844)])
def test_journey_partial_resume_result_training(site,width,height):
    active=None
    latest=None
    actions=[]
    training=[]
    def route(r):
        nonlocal active,latest
        path=r.request.url.split('/api')[-1]
        if path=='/journey':
            data={'schema':'journey-v2','active':active,'latest':latest,'results':[latest] if latest else [],'competencies':[{'id':'strategy','label':'장기 계획','scope':'검증 자료 부족','measured':False}]}
        elif path=='/journey/start':
            active=question();data=active
        else:
            body=r.request.post_data_json;actions.append(body)
            assert body['session_id']=='journey-test'
            assert body['revision']==active['revision']
            if body['action']=='move':
                active=copy.deepcopy(active);active['revision']+=1
                active['phase']='feedback';active['feedback']={'first_correct':True,'complete':False,'correct_plies':1,'total_plies':2,'reason':'첫수는 맞았지만 후속 수순은 완성하지 못했습니다.','submitted':['e3h3'],'expected':['e3h3'],'fen':FEN}
                data=active
            else:
                latest=report();active=None;data={'phase':'complete','report':latest}
        r.fulfill(json=data)
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':width,'height':height})
        page.add_init_script(f"localStorage.setItem('chess_token',{json.dumps(site[1])});")
        page.route('**/api/journey',route);page.route('**/api/journey/*',route)
        page.route('**/api/learning/from-diagnosis',lambda r:(training.append(r.request.post_data_json),r.fulfill(json={'message':'진단 근거의 훈련을 준비했습니다.'})))
        page.goto(site[0]);page.locator('#journeyHomeOpen').click()
        expect(page.locator('#journeyResults')).to_contain_text('미측정: 장기 계획')
        page.locator('#journeyStart').click()
        expect(page.locator('#journeySide')).to_have_text('흑 차례')
        assert page.locator('#journeyBoard .sq').first.get_attribute('aria-label').startswith('h1')
        page.locator('#journeyBoard [aria-label^="e3 "]').click();page.locator('#journeyBoard [aria-label^="h3 "]').click()
        expect(page.locator('#journeyFeedback')).to_contain_text('첫수 성공 · 전체 수순 미완료')
        assert actions[-1]['move']=='e3h3'
        assert page.locator('#journeyBoard .sq:enabled').count()==0
        page.reload();page.evaluate("tab('diagnosis')")
        expect(page.locator('#journeyFeedback')).to_contain_text('첫수 성공 · 전체 수순 미완료')
        page.locator('#journeyNext').click()
        expect(page.locator('#journeyResults')).to_contain_text('독립 국면 1')
        expect(page.locator('#journeyResults')).to_contain_text('전체 성공 0')
        page.locator('#journeyResults summary').first.click()
        expect(page.locator('#journeyResults')).to_contain_text('내 응답: e3h3')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        page.locator('#journeyResults button',has_text='이 근거로 훈련하기').click()
        expect(page.locator('#training')).to_have_class('view active')
        assert training==[{'report_id':'report-test','item_id':'item1'}]
        page.evaluate("tab('diagnosis')")
        expect(page.locator('#journeyHistory option')).to_have_count(1)
        page.evaluate("token=null;tab('diagnosis')")
        expect(page.locator('#journeyHistory option')).to_have_count(0)
        expect(page.locator('#journeyIntro')).to_be_visible()
        expect(page.locator('#journeyResults')).to_be_empty()
        browser.close()


def test_journey_failed_write_requires_state_recovery(site):
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page()
        page.add_init_script(f"localStorage.setItem('chess_token',{json.dumps(site[1])});")
        page.route('**/api/journey',lambda r:r.fulfill(json={'active':question(),'latest':None}))
        page.route('**/api/journey/action',lambda r:r.fulfill(status=409,json={'detail':'저장 버전이 바뀌었습니다.'}))
        page.goto(site[0]);page.evaluate("tab('diagnosis')")
        page.locator('#journeySkip').click()
        expect(page.locator('#journeyMessage')).to_contain_text('저장 상태 확인')
        expect(page.locator('#journeyRefresh')).to_be_enabled()
        page.locator('#journeyRefresh').click()
        expect(page.locator('#journeyProgress')).to_have_text('1 / 2 문항')
        browser.close()


def test_journey_promotion_choice_and_no_early_solution(site):
    task=question()
    task['question'].update(fen='7k/3P4/8/8/8/8/8/K7 w - - 0 1',side='white',legal=['d7d8q','d7d8r','d7d8b','d7d8n'])
    moves=[]
    def act(r):
        moves.append(r.request.post_data_json['move'])
        done=copy.deepcopy(task);done.update(phase='feedback',revision=1,feedback={'first_correct':True,'complete':True,'correct_plies':1,'total_plies':1,'reason':'검증된 승격 응답','fen':'3N3k/8/8/8/8/8/8/K7 b - - 0 1','submitted':['d7d8n'],'expected':['d7d8n']})
        r.fulfill(json=done)
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page()
        page.add_init_script(f"localStorage.setItem('chess_token',{json.dumps(site[1])});")
        page.route('**/api/journey',lambda r:r.fulfill(json={'active':task,'latest':None}))
        page.route('**/api/journey/action',act)
        page.goto(site[0]);page.evaluate("tab('diagnosis')")
        expect(page.locator('#journeyFeedback')).to_be_empty()
        page.locator('#journeyBoard [aria-label^="d7 "]').click();page.locator('#journeyBoard [aria-label^="d8 "]').click()
        page.locator('#cmaPromotionModal button',has_text='나이트').click()
        expect(page.locator('#journeyFeedback')).to_contain_text('전체 수순 성공')
        assert moves==['d7d8n']
        browser.close()


@pytest.mark.parametrize('width,height,label',[(1366,768,'pc'),(390,844,'mobile')])
def test_real_journey_complete_skipped_then_training(site,width,height,label):
    """Real local APIs and temporary accounts. Skips are never presented as success."""
    import secrets
    import urllib.request
    req=urllib.request.Request(site[0]+'/api/register',json.dumps({'code':'JOURNEY-'+secrets.token_hex(4),'pin':'qa-journey-pin'}).encode(),{'Content-Type':'application/json'})
    account=json.load(urllib.request.urlopen(req))
    captures=Path(__file__).resolve().parents[1]/'docs'/'qa-reliability'
    captures.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':width,'height':height})
        page.add_init_script(f"localStorage.setItem('chess_token',{json.dumps(account['token'])});")
        page.goto(site[0]);page.evaluate("api('/starting-level','POST',{choice:'experienced',revision:0})");page.locator('#journeyHomeOpen').click();page.locator('#journeyStart').click()
        expect(page.locator('#journeyBoard .sq')).to_have_count(64,timeout=30000)
        board=page.locator('#journeyBoard').bounding_box()
        nav=page.locator('.mobile-nav')
        bottom=nav.bounding_box()['y'] if nav.is_visible() else height
        assert board['y']+board['height']<=bottom+1
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        page.screenshot(path=str(captures/f'diagnosis-{label}.png'),full_page=True)
        data=page.evaluate("api('/journey')")
        total=data['active']['total']
        assert total>0
        page.reload();page.evaluate("tab('diagnosis')")
        expect(page.locator('#journeyProgress')).to_have_text(f'1 / {total} 문항')
        for index in range(total):
            page.locator('#journeySkip').click()
            expect(page.locator('#journeyFeedback')).to_contain_text('미응답 · 수행 미관찰')
            page.locator('#journeyNext').click()
            if index<total-1:expect(page.locator('#journeyProgress')).to_have_text(f'{index+2} / {total} 문항')
        expect(page.locator('#journeyResults')).to_contain_text('전체 성공 0')
        expect(page.locator('#journeyResults')).to_contain_text('실력 부족을 뜻하지 않습니다')
        page.screenshot(path=str(captures/f'results-{label}.png'),full_page=True)
        data=page.evaluate("api('/journey')")
        assert data['active'] is None
        assert not any(a['full_success'] for a in data['latest']['areas'])
        page.locator('#journeyResults button',has_text='설명과 함께 다시 익히기').first.click()
        expect(page.locator('#training')).to_have_class('view active')
        linked=page.evaluate("api('/learning/dashboard')")
        assert linked['active']['growth_task']=={'report_id':data['latest']['id'],'task_id':'1'}
        expect(page.locator('#learningBoard .sq')).to_have_count(64)
        source_id=data['latest']['training_plan'][0]['item_id']
        assert linked['active']['fen']==next(i['fen'] for i in data['latest']['items'] if i['id']==source_id)
        page.screenshot(path=str(captures/f'training-{label}.png'),full_page=True)
        browser.close()


def test_one_click_clears_old_board_and_suppresses_duplicate_start(site):
    pending=[]
    task={'session_id':'selected-source','revision':0,'card_id':'source','fen':FEN,'legal':['e3h3'],
          'side':'black','mode':'practice','done':False,'goal':'원본 연습','category':'메이트',
          'hint_level':0,'playback':[]}
    dashboard={'active':{**task,'done':True},'notice':'기록 유지','reason':'원본 연습','due':[],
               'intervals':[1,3,7],'path':None,'cards':[],'skills':[],'attempts':[],'engine':False}
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page()
        page.add_init_script(f"localStorage.setItem('chess_token',{json.dumps(site[1])});")
        page.route('**/api/learning/dashboard',lambda r:r.fulfill(json=dashboard))
        page.route('**/api/learning/from-diagnosis',lambda r:pending.append(r))
        page.goto(site[0]);page.evaluate("tab('training')")
        expect(page.locator('#learningBoard .sq')).to_have_count(64)
        page.evaluate("void window.learningFromDiagnosis('report','item')")
        expect(page.locator('#learningBoard')).to_be_empty()
        expect(page.locator('#learningMessage')).to_contain_text('여는 중')
        expect(page.locator('#learningFresh')).to_be_disabled()
        page.evaluate("void window.learningFromDiagnosis('report','item')")
        page.wait_for_timeout(100)
        assert len(pending)==1
        assert pending[0].request.post_data_json=={'report_id':'report','item_id':'item'}
        dashboard['active']=task
        pending[0].fulfill(json={'active':task})
        expect(page.locator('#learningBoard .sq:enabled')).to_have_count(64)
        expect(page.locator('#learningMessage')).to_contain_text('바로 연습')
        browser.close()
