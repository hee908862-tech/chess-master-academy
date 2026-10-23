"""Local persisted timing with actual action API; no operating identity."""
from playwright.sync_api import expect
from test_redesign_browser_followup import isolated,site
from test_clarity_browser import solution_positions,play
from test_learning import setup
from test_journey import attach,post,saved


def test_invalid_optional_timing_does_not_reject_valid_skip_or_change_score_rules(setup):
    client,_,_,path=attach(setup)
    session=post(client,'start',{'mode':'initial','competency':'calculation'})
    response=client.post('/api/journey/action',json={'session_id':session['session_id'],'revision':session['revision'],
        'action':'skip','thinking_time':'untrusted malformed optional telemetry'})
    assert response.status_code==200,response.text
    item=saved(path)['active']['items'][0]
    assert item['outcome']=='not_answered' and not item['complete']
    assert item['thinking_time']['active_ms'] is None and item['thinking_time']['flags']==['invalid_payload']


def test_actual_timing_pauses_during_server_wait_reloads_and_duplicate_action_is_preserved(isolated,site):
    page,_=isolated;page.goto(site[0]+'/#diagnosis/initial')
    page.get_by_role('button',name='로그인 없이 초기 진단 시작',exact=True).click()
    expect(page.locator('#initialProfile > button').first).to_have_text('진단 이어하기 · 남은 분야 바로 풀기')
    page.evaluate("cmaJourney.startScoped('initial','calculation')")
    expect(page.locator('#journeyTask')).to_be_visible()
    page.wait_for_function('!cmaJourney.status().busy && cmaDiagnosisTiming.status().running')
    page.wait_for_timeout(1100)
    question=page.evaluate('cmaJourney.state().active.question')
    pending=[];page.route('**/api/journey/action',lambda route:pending.append(route))
    play(page,'journeyBoard',solution_positions()[question['fen']])
    page.wait_for_timeout(100);assert len(pending)==1
    body=pending[0].request.post_data_json
    assert body['thinking_time']['active_ms']>=1000
    before=page.evaluate('cmaDiagnosisTiming.status().active_ms')
    page.wait_for_timeout(800)
    assert page.evaluate('cmaDiagnosisTiming.status().active_ms')-before<100
    pending[0].continue_();page.unroute('**/api/journey/action')
    page.wait_for_function('!cmaJourney.status().busy')
    current=page.evaluate("api('/journey')")['active']
    assert current['phase']=='question'
    recorded=current['question']['thinking_time']
    assert recorded['active_ms']==body['thinking_time']['active_ms'] and recorded['usable_for_trend']
    duplicate=page.evaluate("async body=>{try{await api('/journey/action','POST',body);return 'accepted';}catch(_){return 'rejected';}}",body)
    assert duplicate=='rejected'
    assert page.evaluate("api('/journey').then(x=>x.active.question.thinking_time)")==recorded
    page.evaluate("sessionStorage.setItem('timingTestStream',cmaDiagnosisTiming.snapshot().stream_id)")
    page.reload();expect(page.locator('#journeyTask')).to_be_visible()
    page.wait_for_function('!cmaJourney.status().busy && cmaDiagnosisTiming.status().running')
    assert page.evaluate("cmaDiagnosisTiming.snapshot().stream_id===sessionStorage.getItem('timingTestStream')")
    page.get_by_role('button',name='생각 시간 일시정지',exact=True).click()
    paused=page.evaluate('cmaDiagnosisTiming.status().active_ms');page.wait_for_timeout(300)
    assert page.evaluate('cmaDiagnosisTiming.status().active_ms')==paused
    page.locator('#journeySkip').click();expect(page.locator('#journeyNext')).to_be_visible()
    finished=page.evaluate("api('/journey')")['active']
    final_timing=finished['question']['thinking_time']
    assert not final_timing['usable_for_trend'] and 'explicit_pause_used' in final_timing['flags']
    assert finished['feedback']['outcome']=='partial_execution'
