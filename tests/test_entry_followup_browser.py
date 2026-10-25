"""Complete a real entry observation, then practice/recheck/choose standard assessment."""
import json
import sqlite3
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page
from test_study_browser import login


def finish_ui(page):
    while True:
        status=page.evaluate("api('/journey')")
        if not status['active']:return status
        if status['active']['phase']=='question':page.locator('#journeySkip').click()
        expect(page.locator('#journeyNext')).to_be_visible()
        page.locator('#journeyNext').click()
        expect(page.locator('#journeyRefresh')).to_be_enabled()


@pytest.mark.parametrize('mode,total',[('balanced',24),('quick',12)])
def test_entry_complete_practice_then_direct_standard_choice(page,site,mode,total):
    login(page,site)
    page.evaluate("api('/starting-level','POST',{choice:'beginner',revision:0})")
    page.evaluate("tab('diagnosis')");page.locator('#diagnosticOther > summary').click();page.locator('#journeyStart').click()
    expect(page.locator('#journeyBoard .sq:enabled')).to_have_count(64)
    status=finish_ui(page);report=status['latest']
    assert report['mode']=='gentle' and 'snapshot' not in report and status['cycle'] is None
    expect(page.locator('#journeyEntryNext')).to_be_visible()
    with page.expect_response('**/api/learning/from-diagnosis') as response:
        page.locator('#journeyEntryNext').get_by_role('button',name='먼저 연결된 수순 연습하기',exact=True).click()
    assert response.value.status==200
    learning=page.evaluate("api('/learning/dashboard')")
    assert learning['path']['diagnosis']['report_id']==report['id']
    expect(page.locator('#learningBoard .sq:enabled')).to_have_count(64)
    expect(page.locator('#trainingCycle')).to_contain_text('입문 연습은 5개 주기와 별도')
    page.reload();page.evaluate("tab('diagnosis')")
    expect(page.locator('#journeyEntryNext')).to_be_visible()
    label='표준 균형 진단으로 · 24문항' if mode=='balanced' else '표준 간이 진단으로 · 12문항'
    with page.expect_response('**/api/journey/start') as response:
        page.locator('#journeyEntryNext').get_by_role('button',name=label,exact=True).click()
    assert response.value.status==200,response.value.text()
    assert response.value.json()['total']==total
    assert response.value.request.post_data_json['mode']==mode
    assert page.evaluate("api('/starting-level')")['choice']=='beginner'
    assert page.evaluate("api('/learning/dashboard')")['active']['session_id']==learning['active']['session_id']


def test_prior_standard_cycle_then_new_entry_survives_reload(page,site,tmp_path_factory):
    login(page,site)
    code=page.evaluate("api('/me')")['code']
    standard=page.evaluate("async()=>{let s=await api('/journey/start','POST',{mode:'balanced'});while(s.phase!=='complete'){s=await api('/journey/action','POST',{session_id:s.session_id,revision:s.revision,action:s.phase==='question'?'skip':'next'});}return s.report;}")
    # Prepare an already-earned prior cycle in this uniquely named local QA account only.
    found=False
    for path in tmp_path_factory.getbasetemp().glob('db*/test.sqlite3'):
        with sqlite3.connect(path) as db:
            if not db.execute('SELECT 1 FROM journey_progress WHERE code=?',(code,)).fetchone():continue
            state={'cards':{},'attempts':[],'seen':[],'intervals':[1,3,7],'active':None,'cycles':{standard['id']:{'cards':{},'completed':{t['id']:{'position':t['id']} for t in standard['training_plan']}}}}
            db.execute('INSERT OR REPLACE INTO learning_progress(code,state) VALUES(?,?)',(code,json.dumps(state)));found=True
    assert found
    page.evaluate("api('/starting-level','POST',{choice:'beginner',revision:0})")
    page.evaluate("api('/journey/start','POST',{mode:'entry'})")
    page.evaluate("tab('diagnosis')");expect(page.locator('#journeyBoard .sq:enabled')).to_have_count(64)
    status=finish_ui(page);entry=status['latest']
    assert entry['mode']=='gentle' and entry['id']!=standard['id']
    page.reload();page.evaluate("tab('diagnosis')")
    expect(page.locator('#journeyEntryNext')).to_be_visible()
    expect(page.locator('#journeyPreviousCycle')).to_be_visible()
    page.locator('#journeyPreviousCycle > summary').click()
    expect(page.locator('#journeyCycleReport .growth-plan progress')).to_have_attribute('value','5')
    state=page.evaluate("api('/journey')")
    assert state['latest']['id']==entry['id'] and state['cycle_report']['id']==standard['id']
    assert state['cycle']['completed']==5
    page.locator('#journeyEntryNext').get_by_role('button',name='시작 수준 선택 / 변경',exact=True).click()
    expect(page.locator('#startingLevelDialog')).to_be_visible()
