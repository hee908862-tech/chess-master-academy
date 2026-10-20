"""Actual local API + UI cycle, with read-only access to this fixture's puzzle answers."""
import json
import secrets
import sqlite3
import urllib.request
from pathlib import Path
from playwright.sync_api import expect
from test_qa_browser import site,page


def test_solved_partial_diagnosis_five_tasks_resume_and_concept_path(page,site,tmp_path_factory):
    code='CYCLE-'+secrets.token_hex(4).upper()
    req=urllib.request.Request(site[0]+'/api/register',json.dumps({'code':code,'pin':'temporary-cycle-pin'}).encode(),{'Content-Type':'application/json'})
    token=json.load(urllib.request.urlopen(req))['token']
    page.add_init_script(f"localStorage.setItem('chess_token',{json.dumps(token)});")
    page.route('**/api/onboarding',lambda r:r.fulfill(json={'status':'completed','version':1}))
    def stored(table):
        for path in tmp_path_factory.getbasetemp().glob('db*/test.sqlite3'):
            with sqlite3.connect(path) as conn:
                try:row=conn.execute(f'SELECT state FROM {table} WHERE code=?',(code,)).fetchone()
                except sqlite3.OperationalError:continue
                if row:return json.loads(row[0])
        raise AssertionError('Temporary test account state not found')
    def move_ui(board,uci):
        with page.expect_response(lambda r:r.url.endswith('/action') and r.request.method=='POST') as response:
            page.locator(f'#{board} [aria-label^="{uci[:2]} "]').click()
            page.locator(f'#{board} [aria-label^="{uci[2:4]} "]').click()
            if len(uci)==5:page.locator('#cmaPromotionModal').get_by_role('button',name={'q':'퀸','r':'룩','b':'비숍','n':'나이트'}[uci[4]]).click()
        assert response.value.status==200
        return response.value.json()
    def api(path,body=None):return page.evaluate('([path,body])=>body===null?api(path):api(path,"POST",body)',[path,body])
    page.goto(site[0]);page.locator('#journeyHomeOpen').click();page.locator('#journeyStart').click()
    expect(page.locator('#journeyBoard .sq')).to_have_count(64)
    rows=stored('journey_progress')['active']['items'];assert len(rows)==24
    partial=False
    for index,row in enumerate(rows):
        if index<2:
            for move in row['line'][::2]:
                result=move_ui('journeyBoard',move)
                if result['phase']=='feedback':break
                expect(page.locator('#journeySkip')).to_be_enabled()
            expect(page.locator('#journeyFeedback')).to_contain_text('전체 수순 성공')
        elif not partial and len(row['line'])>=3:
            move_ui('journeyBoard',row['line'][0]);expect(page.locator('#journeySkip')).to_be_enabled();page.locator('#journeySkip').click();partial=True
            expect(page.locator('#journeyFeedback')).to_contain_text('전체 수순 미완료')
        else:
            page.locator('#journeySkip').click();expect(page.locator('#journeyFeedback')).to_contain_text('미응답')
        page.locator('#journeyNext').click()
        if index<23:expect(page.locator('#journeyProgress')).to_have_text(f'{index+2} / 24 문항')
    assert partial
    expect(page.locator('.growth-plan progress')).to_have_attribute('value','0')
    report=api('/journey')['latest'];assert sum(a['full_success'] for a in report['areas'])>=2
    # Prepare a real pre-existing concept-stage path. Preserve it while using new tasks.
    old=api('/learning/from-diagnosis',{'report_id':report['id'],'item_id':report['training_plan'][0]['item_id']})
    task=old['active'];card=stored('learning_progress')['cards'][task['card_id']]
    for move in card['line'][::2]:
        task=api('/learning/action',{'session_id':task['session_id'],'revision':task['revision'],'action':'move','move':move})
        if task['done']:break
    api('/learning/path',{'action':'continue'})
    path=stored('learning_progress')['path'];assert path['current']==1 and path['steps'][1]['status']=='active'
    page.evaluate("tab('training')");expect(page.locator('#learningMode')).to_contain_text('개념')
    page.evaluate("tab('diagnosis')")
    expect(page.get_by_role('button',name='새 문제로 다시 진단하기',exact=True)).to_be_disabled()
    for index in range(5):
        page.locator('.growth-plan .growth-task').nth(index).get_by_role('button').click()
        expect(page.locator('#learningMode')).to_have_text('연습')
        expect(page.locator('#learningBoard .sq:enabled')).to_have_count(64)
        if index==0:
            page.get_by_role('button',name='힌트 1단계',exact=True).click()
            expect(page.get_by_role('button',name='힌트 2단계',exact=True)).to_be_visible()
            current=api('/learning/dashboard')['active'];page.reload();page.evaluate("tab('training')")
            expect(page.locator('#learningMode')).to_have_text('연습')
            assert api('/learning/dashboard')['active']['session_id']==current['session_id']
        task=api('/learning/dashboard')['active'];card=stored('learning_progress')['cards'][task['card_id']]
        for move in card['line'][::2]:
            result=move_ui('learningBoard',move)
            if result['done']:break
            expect(page.get_by_role('button',name='답안 수순',exact=True)).to_be_enabled()
        expect(page.get_by_role('button',name='추천 훈련과 진행률 보기',exact=True)).to_be_visible()
        page.get_by_role('button',name='추천 훈련과 진행률 보기',exact=True).click()
        expect(page.locator('.growth-plan progress')).to_have_attribute('value',str(index+1))
        assert stored('learning_progress')['path']==path
    expect(page.get_by_role('button',name='새 문제로 다시 진단하기',exact=True)).to_be_enabled()
    page.screenshot(path=str(Path(__file__).resolve().parents[1]/'docs/qa-growth/real-five-tasks-unlocked.png'),full_page=True)
    page.get_by_role('button',name='새 문제로 다시 진단하기',exact=True).click()
    expect(page.locator('#journeyProgress')).to_have_text('1 / 24 문항')
    current=api('/journey');assert current['latest']['id']==report['id'] and current['cycle']['unlocked']
    for index in range(24):
        page.locator('#journeySkip').click();expect(page.locator('#journeyFeedback')).to_contain_text('미응답');page.locator('#journeyNext').click()
        if index<23:expect(page.locator('#journeyProgress')).to_have_text(f'{index+2} / 24 문항')
    expect(page.locator('.growth-plan progress')).to_have_attribute('value','0')
    assert api('/journey')['latest']['id']!=report['id']
    expect(page.get_by_role('button',name='새 문제로 다시 진단하기',exact=True)).to_be_disabled()
