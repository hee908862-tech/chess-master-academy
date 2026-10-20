import copy
from playwright.sync_api import expect
from test_qa_browser import site,page,open_page
from test_growth_browser import report_fixture
from test_journey_browser import question


def test_active_session_history_and_stale_refresh_never_mix(page,site):
    report=report_fixture(number=1);active=question()
    data={'active':active,'latest':report,'results':[report],'cycle':{'report_id':report['id'],'unlocked':True,'completed':5,'remaining':0,'tasks':[]},'activity':{'diagnoses':1,'answered':6,'recommended_completed':5}}
    page.route('**/api/journey',lambda r:r.fulfill(json=data))
    open_page(page,site);page.evaluate("tab('diagnosis')");expect(page.locator('#journeyProgress')).to_contain_text('1 / 2')
    page.locator('#journeyRefresh').click();expect(page.locator('#journeyResults')).to_be_empty()
    expect(page.locator('#journeyPast')).to_be_visible();expect(page.locator('#journeyPastReport')).to_be_empty()
    page.evaluate("""() => {window.savedJourneyApi=api;window.holdJourney=true;api=function(p,...a){if(p==='/journey'&&window.holdJourney){window.holdJourney=false;return new Promise(resolve=>window.lateJourney=resolve);}return window.savedJourneyApi(p,...a);};}""")
    page.locator('#journeyRefresh').click();page.evaluate("tab('home');tab('diagnosis')")
    expect(page.locator('#journeyProgress')).to_contain_text('1 / 2')
    page.evaluate('d=>window.lateJourney(d)',{**data,'active':None})
    page.wait_for_timeout(100)
    expect(page.locator('#journeyTask')).to_be_visible();expect(page.locator('#journeyResults')).to_be_empty()
    page.evaluate("tab('home')");expect(page.locator('#journeyActivity')).to_contain_text('완료한 추천 훈련 5개')


def test_one_observation_is_additional_confirmation_not_unmeasured(page,site):
    report=report_fixture(number=1)
    for a in report['areas']:
        if a['id']=='strategy':continue
        a['performance'].update(score=None,observed=1,band_counts=[1,0],comparable=False)
        a['first_success']=1;a['observation']='4문제 중 1개 수순을 끝까지 풀었어요.'
    page.route('**/api/journey',lambda r:r.fulfill(json={'active':None,'latest':report,'results':[report]}))
    open_page(page,site);page.evaluate("tab('diagnosis')")
    expect(page.locator('.ability-card').first).to_contain_text('추가 확인 필요')
    expect(page.locator('.ability-card').first).to_contain_text('기초 1개, 응용 0개')
    expect(page.locator('.ability-card').last).to_contain_text('미측정')


def test_equivalent_observation_is_not_unanswered(page,site):
    report=report_fixture(number=1);a=report['areas'][0]
    a['performance'].update(score=None,observed=0,band_counts=[0,0],comparable=False)
    a.update(first_success=0,unverified=0,partial=0,equivalent=1)
    page.route('**/api/journey',lambda r:r.fulfill(json={'active':None,'latest':report,'results':[report]}))
    open_page(page,site);page.evaluate("tab('diagnosis')")
    expect(page.locator('.ability-card').first).to_contain_text('추가 확인 필요')


def test_past_lazy_evidence_is_read_only_during_active_diagnosis(page,site):
    report=report_fixture(number=1)
    report['areas'][0]['items']=[{'id':'past-item','fen':'8/8/8/8/8/8/K7/7k w - - 0 1','expected':['a2a3']}]
    data={'active':question(),'latest':report,'results':[report]}
    page.route('**/api/journey',lambda r:r.fulfill(json=data))
    mutations=[]
    page.on('request',lambda r:mutations.append(r.url) if r.method=='POST' and '/api/learning/' in r.url else None)
    open_page(page,site);page.evaluate("tab('diagnosis')")
    expect(page.locator('#journeyProgress')).to_contain_text('1 / 2')
    before=page.evaluate("api('/learning/dashboard')")
    page.locator('#journeyPast > summary').click()
    page.locator('#journeyPastReport').get_by_text('문항별 풀이와 자세한 근거',exact=True).click()
    page.locator('#journeyPastReport').get_by_text('문항별 근거 확인',exact=True).first.click()
    expect(page.locator('#journeyPastReport .journey-item')).to_have_count(1)
    expect(page.locator('#journeyPastReport button:enabled')).to_have_count(0)
    expect(page.locator('#journeyPastReport button:not(.sq)')).to_have_count(0)
    assert not mutations
    assert page.evaluate("api('/learning/dashboard')")==before
    expect(page.locator('#journeyProgress')).to_contain_text('1 / 2')
