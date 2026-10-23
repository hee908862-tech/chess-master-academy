"""Real local API chunk transitions; Chromium emulation, not production."""
import pytest
from playwright.sync_api import expect
from test_redesign_browser_followup import isolated,site


def prepare_last_feedback(page,site):
    page.goto(site[0]+'/#diagnosis/initial')
    page.get_by_role('button',name='로그인 없이 초기 진단 시작',exact=True).click()
    page.wait_for_function('!!token && !cmaJourney.status().busy')
    page.locator('#initialProfile > button').first.click()
    expect(page.locator('#journeyTask')).to_be_visible()
    page.wait_for_function('!cmaJourney.status().busy')
    page.evaluate('''async()=>{
      let s=(await api('/journey')).active;window.firstSession=s.session_id;
      for(let n=0;n<s.total;n++){
        s=await api('/journey/action','POST',{session_id:s.session_id,revision:s.revision,action:'skip'});
        if(n+1<s.total)s=await api('/journey/action','POST',{session_id:s.session_id,revision:s.revision,action:'next'});
      }await cmaJourney.load();
    }''')
    expect(page.locator('#journeyNext')).to_have_text('다음 문항 · 계속하기')


@pytest.mark.parametrize('width,height',[(1366,768),(360,800)])
def test_chunk_next_continues_once_same_route_then_explicit_pause_restores(isolated,site,width,height):
    page,_=isolated;page.set_viewport_size({'width':width,'height':height})
    prepare_last_feedback(page,site)
    starts=[];page.on('request',lambda r:starts.append(r) if r.method=='POST' and r.url.endswith('/api/journey/start') else None)
    page.locator('#journeyNext').dblclick()
    page.wait_for_function('cmaJourney.state()?.active?.session_id!==window.firstSession && !!cmaJourney.state()?.active')
    assert len(starts)==1
    expect(page).to_have_url(site[0]+'/#diagnosis/initial')
    expect(page.locator('#journeyTask')).to_be_visible()
    expect(page.locator('#initialProgress')).to_contain_text('현재 분야 저장 묶음 1/8')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    page.evaluate("sessionStorage.setItem('testSecondSession',cmaJourney.state().active.session_id)")
    page.locator('#journeyPause').click();expect(page).to_have_url(site[0]+'/#home')
    page.reload();page.wait_for_function('!cmaJourney.status().busy')
    assert len(starts)==1
    page.evaluate("cmaNavigation.go('diagnosis/initial')")
    expect(page.locator('#journeyTask')).to_be_visible()
    assert page.evaluate("cmaJourney.state().active.session_id===sessionStorage.getItem('testSecondSession')")
    # The confirmed first chunk and active second chunk survive without another start.
    assert page.evaluate("api('/journey').then(x=>x.results.length===1 && x.active.index===0)")
    assert len(starts)==1


def test_failed_next_chunk_does_not_restart_on_reload(isolated,site):
    page,_=isolated;prepare_last_feedback(page,site);starts=[]
    def reject(route):
        starts.append(1);route.fulfill(status=503,json={'detail':'테스트 출제 대기'})
    page.route('**/api/journey/start',reject)
    page.locator('#journeyNext').click()
    expect(page.locator('#journeyMessage')).to_contain_text('테스트 출제 대기')
    assert starts==[1]
    page.reload();page.wait_for_function('!cmaJourney.status().busy')
    assert starts==[1]
    state=page.evaluate("api('/journey')")
    assert state['active'] is None and len(state['results'])==1


def test_held_remaining_diagnosis_precedes_old_training_and_shows_exclusion_reason(isolated,site):
    page,_=isolated;page.goto(site[0]+'/#diagnosis/initial')
    page.get_by_role('button',name='로그인 없이 초기 진단 시작',exact=True).click()
    page.wait_for_function('!!token && !cmaJourney.status().busy')
    data=page.evaluate("api('/journey')");p=data['initial_profile']
    p.update(state='held',reviewed=True,held_reason='정해진 추가 확인 상한에 도달했습니다.',supplement_available_to_check=True,technical_failures=2,technical_replacement_credit=2,baseline_id='fixture-held')
    data['training']={'path_done':True};page.route('**/api/journey',lambda r:r.fulfill(json=data))
    page.evaluate("async()=>{await cmaJourney.load();cmaNavigation.go('home');}")
    expect(page.locator('#homeNextAction')).to_contain_text('남은 진단 이어하기')
    page.evaluate("cmaNavigation.go('diagnosis/initial')")
    expect(page.locator('#initialProfile > button.primary')).to_have_text('남은 진단 이어하기 · 새 문제 확인')
    expect(page.locator('#initialProfile')).to_contain_text('기술 실패 2문항')


def test_unconfirmed_branch_exposure_blocks_start_and_submit_without_grading(isolated,site):
    page,_=isolated;page.goto(site[0]+'/#diagnosis/initial')
    page.get_by_role('button',name='로그인 없이 초기 진단 시작',exact=True).click()
    expect(page.locator('#initialProfile > button').first).to_have_text('진단 이어하기 · 남은 분야 바로 풀기')
    page.evaluate("window.originalFlush=cmaExplore.flushExposures;cmaExplore.flushExposures=async()=>false")
    page.locator('#initialProfile > button').first.click()
    expect(page.locator('#journeyMessage')).to_contain_text('탐색 노출 이력 저장 미확인')
    assert page.evaluate("api('/journey').then(x=>x.active===null && x.initial_profile.assigned===0)")
    page.evaluate("async()=>{cmaExplore.flushExposures=window.originalFlush;await cmaJourney.load();}")
    page.locator('#initialProfile > button').first.click();expect(page.locator('#journeyTask')).to_be_visible()
    before=page.evaluate("api('/journey')")['active']
    page.evaluate("cmaExplore.flushExposures=async()=>false")
    page.locator('#journeySkip').click()
    expect(page.locator('#journeyMessage')).to_contain_text('탐색 노출 이력 저장 미확인')
    after=page.evaluate("api('/journey')")['active']
    assert after['revision']==before['revision'] and after['phase']=='question'


def test_navigation_during_confirming_read_prevents_automatic_next_chunk(isolated,site):
    page,_=isolated;prepare_last_feedback(page,site)
    pending=[];starts=[];holding=[True]
    def delay(route):
        if holding[0]:pending.append(route)
        else:route.continue_()
    page.route('**/api/journey',delay)
    page.on('request',lambda r:starts.append(1) if r.method=='POST' and r.url.endswith('/api/journey/start') else None)
    page.locator('#journeyNext').click()
    page.wait_for_timeout(200);assert pending
    page.evaluate("cmaNavigation.go('home')")
    holding[0]=False
    for request in list(pending):request.continue_()
    page.unroute('**/api/journey')
    page.wait_for_function('!cmaJourney.status().busy')
    page.wait_for_timeout(300)
    assert not starts
    state=page.evaluate("api('/journey')")
    assert state['active'] is None and len(state['results'])==1
    expect(page).to_have_url(site[0]+'/#home')
