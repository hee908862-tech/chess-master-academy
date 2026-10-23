"""New solving-time integration on actual local API. Legacy thinking-time preservation is tested separately; no operating identity."""
from playwright.sync_api import expect
from test_redesign_browser_followup import isolated,site
from test_clarity_browser import solution_positions,play
from test_learning import setup
from test_journey import attach,post,saved


def test_invalid_optional_timing_does_not_reject_valid_skip_or_change_score_rules(setup):
    client,_,_,path=attach(setup)
    session=post(client,'start',{'mode':'initial','competency':'calculation'})
    response=client.post('/api/journey/action',json={'session_id':session['session_id'],'revision':session['revision'],
        'action':'skip','solving_time':'untrusted malformed optional telemetry'})
    assert response.status_code==200,response.text
    item=saved(path)['active']['items'][0]
    assert item['outcome']=='not_answered' and not item['complete']
    assert item['solving_time']['active_ms'] is None and item['solving_time']['flags']==['invalid_telemetry']


def test_actual_timing_pauses_during_server_wait_reloads_and_duplicate_action_is_preserved(isolated,site):
    page,_=isolated;page.goto(site[0]+'/#diagnosis/initial')
    page.get_by_role('button',name='로그인 없이 초기 진단 시작',exact=True).click()
    expect(page.locator('#initialProfile > button').first).to_have_text('진단 이어하기 · 남은 분야 바로 풀기')
    page.evaluate("cmaJourney.startScoped('initial','calculation')")
    expect(page.locator('#journeyTask')).to_be_visible()
    page.wait_for_function('!cmaJourney.status().busy && cmaSolvingClock.canInput()')
    page.wait_for_timeout(1100)
    question=page.evaluate('cmaJourney.state().active.question')
    pending=[];page.route('**/api/journey/action',lambda route:pending.append(route))
    play(page,'journeyBoard',solution_positions()[question['fen']])
    page.wait_for_timeout(100);assert len(pending)==1
    body=pending[0].request.post_data_json
    assert body['solving_time']['active_ms']>=1000
    before=page.locator('.solving-clock-time').inner_text()
    page.wait_for_timeout(800)
    assert page.locator('.solving-clock-time').inner_text()==before
    pending[0].continue_();page.unroute('**/api/journey/action')
    page.wait_for_function('!cmaJourney.status().busy')
    current=page.evaluate("api('/journey')")['active']
    assert current['phase']=='question'
    recorded=current['question']['solving_time']
    assert recorded['active_ms']==body['solving_time']['active_ms'] and recorded['status']=='valid'
    duplicate=page.evaluate("async body=>{try{await api('/journey/action','POST',body);return 'accepted';}catch(_){return 'rejected';}}",body)
    assert duplicate=='rejected'
    assert page.evaluate("api('/journey').then(x=>x.active.question.solving_time)")==recorded
    page.reload();expect(page.locator('#journeyTask')).to_be_visible()
    page.wait_for_function('!cmaJourney.status().busy && cmaSolvingClock.canInput()')
    page.wait_for_timeout(300)
    page.evaluate("cmaSolvingClock.pause('manual')")
    page.wait_for_timeout(300)
    paused=page.locator('.solving-clock-time').inner_text();page.wait_for_timeout(600)
    assert page.locator('.solving-clock-time').inner_text()==paused
    page.evaluate("cmaSolvingClock.resume('manual')")
    page.locator('#journeySkip').click();expect(page.locator('#journeyNext')).to_be_visible()
    finished=page.evaluate("api('/journey')")['active']
    final_timing=finished['question']['solving_time']
    assert final_timing['status']=='interrupted' and 'interrupted' in final_timing['flags']
    assert len(final_timing['streams'])==2
    assert finished['feedback']['solving_score']['time_adjustment']==0
    assert finished['feedback']['outcome']=='partial_execution'
