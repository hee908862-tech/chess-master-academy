"""Real UI rules → entry, preserving an unfinished standard cycle and active sessions."""
from playwright.sync_api import expect
from test_qa_browser import site, page
from test_study_browser import login
from test_entry_followup_browser import finish_ui


def rules_ui(page):
    page.evaluate('cmaStartingLevel.open()')
    page.get_by_role('button',name='룰부터 배우기',exact=True).click()
    for move in ['a1a4','a1a4','a1a8','g1f2']:
        with page.expect_response('**/api/starting-level/move') as response:
            page.locator(f'#ruleBoard [aria-label^="{move[:2]} "]').click()
            page.locator(f'#ruleBoard [aria-label^="{move[2:]} "]').click()
        assert response.value.status==200
        assert response.value.json()['correct']
    expect(page.locator('#ruleBoard .sq')).to_have_count(0)
    page.get_by_role('button',name='부담 적은 입문 진단 화면으로',exact=True).click()


def start_status(page,mode):
    return page.evaluate("async mode=>{const r=await fetch('/api/journey/start',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},body:JSON.stringify({mode})});return r.status;}",mode)


def test_rules_to_entry_keeps_unfinished_standard_cycle(page,site):
    page.set_viewport_size({'width':400,'height':900})
    login(page,site)
    standard=page.evaluate("async()=>{let s=await api('/journey/start','POST',{mode:'balanced'});while(s.phase!=='complete')s=await api('/journey/action','POST',{session_id:s.session_id,revision:s.revision,action:s.phase==='question'?'skip':'next'});return s.report;}")
    before=page.evaluate("api('/journey')")
    learning=page.evaluate("api('/learning/dashboard')")
    assert before['cycle']['completed']==0 and not before['cycle']['unlocked']
    rules_ui(page)
    button=page.get_by_role('button',name='입문 관찰 시작 · 최대 6문항',exact=True)
    expect(button).to_be_enabled()
    button.click()
    expect(page.locator('#journeyBoard .sq:enabled')).to_have_count(64)
    assert page.evaluate("api('/journey')")['active']['starting_conditions']['mode']=='gentle'
    after=finish_ui(page)
    assert after['latest']['mode']=='gentle' and 'snapshot' not in after['latest']
    assert after['cycle']==before['cycle'] and after['cycle_report']==standard
    assert page.evaluate("api('/learning/dashboard')")==learning
    page.reload();page.evaluate("tab('diagnosis')")
    expect(page.locator('#journeyEntryNext')).to_contain_text('기존 추천 과제 5개')
    for label,mode in [('표준 균형 진단으로 · 24문항','balanced'),('표준 간이 진단으로 · 12문항','quick')]:
        expect(page.get_by_role('button',name=label,exact=True)).to_be_disabled()
        assert start_status(page,mode)==409
    page.get_by_role('button',name='기존 표준 추천 이어가기',exact=True).click()
    expect(page.locator('#journeyPreviousCycle')).to_have_attribute('open','')
    expect(page.locator('#journeyCycleReport progress')).to_have_attribute('value','0')
    page.get_by_role('button',name='입문 새 문제로 다시 확인',exact=True).click()
    expect(page.locator('#journeyBoard .sq:enabled')).to_have_count(64)
    assert page.evaluate("api('/journey')")['cycle']==before['cycle']


def test_rules_entry_offer_resumes_existing_diagnosis(page,site):
    login(page,site)
    active=page.evaluate("api('/journey/start','POST',{mode:'balanced'})")
    rules_ui(page)
    expect(page.locator('#journeyEntryOffer')).to_contain_text('진행 중인 진단이 있습니다')
    expect(page.get_by_role('button',name='입문 관찰 시작 · 최대 6문항',exact=True)).to_have_count(0)
    page.get_by_role('button',name='진행 중인 진단 이어하기',exact=True).click()
    expect(page.locator('#journeyBoard .sq:enabled')).to_have_count(64)
    assert start_status(page,'gentle')==409
    assert page.evaluate("api('/journey')")['active']==active
