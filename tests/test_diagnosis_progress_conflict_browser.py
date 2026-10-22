"""PR39 operating regressions: real local progression, conflict preservation, retry."""
import copy
from playwright.sync_api import expect
from test_redesign_browser_followup import isolated,site
from test_clarity_browser import solution_positions,play
from test_activity_flow_browser import start


def diagnose(page,answers):
    page.evaluate("tab('diagnosis')")
    page.locator('.diagnostic-choice[data-scope=subskill]').click()
    page.get_by_label('진단 분야',exact=True).select_option('mate')
    page.get_by_label('진단 하위 기술',exact=True).select_option('mateIn1')
    page.locator('#diagnosticBegin').click()
    for index in range(4):
        expect(page.locator('#diagnosticResume')).to_contain_text(f'{index+1} / 4 문항')
        if index==1:
            before=page.evaluate("api('/journey')")['active']
            page.reload();expect(page.locator('#diagnosticResume')).to_contain_text('2 / 4 문항')
            assert page.evaluate("api('/journey')")['active']==before
        state=page.evaluate("api('/journey')")['active']
        if index==3:page.locator('#journeySkip').click()
        else:
            with page.expect_response('**/api/journey/action'):play(page,'journeyBoard',answers[state['question']['fen']])
        expect(page.locator('#journeyNext')).to_be_visible()
        page.locator('#journeyNext').click()
        page.wait_for_function('!cmaJourney.status().busy')
    expect(page.locator('#diagnosticResume')).to_be_hidden()
    result=page.evaluate("api('/journey')")['latest']
    assert result['scoped_training']['tasks']
    page.reload();expect(page.locator('#diagnosticResume')).to_be_hidden()
    return result


def test_progress_conflict_preserve_complete_and_original_retry(isolated):
    page,_=isolated;page.set_viewport_size({'width':360,'height':800});start(page);answers=solution_positions()
    page.evaluate("tab('training')");page.locator('#learningFresh').click()
    expect(page.locator('#learningBoard .sq')).to_have_count(64)
    original=page.evaluate("api('/learning/dashboard')")['active']
    report=diagnose(page,answers)
    starts=[];page.on('request',lambda r:starts.append(r) if r.url.endswith('/learning/scoped/start') else None)
    page.locator('[data-scoped-report]').first.click()
    expect(page.locator('#learningRecommendationReturn')).to_contain_text('기존 훈련을 보존')
    expect(page.locator('#learningBoardFeedback')).not_to_contain_text('미확인')
    current=page.evaluate("api('/learning/dashboard')")['active']
    assert current==original and not starts
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    page.locator('#learningRecommendationReturn').get_by_role('button',name='진단 추천으로 돌아가기').click()
    expect(page.locator('#journeyResults')).to_be_visible()
    page.evaluate("tab('training')");page.reload()
    expect(page.locator('#learningRecommendationReturn')).to_contain_text('기존 훈련을 보존')
    page.locator('#learningRecommendationReturn').get_by_role('button',name='기존 훈련 이어하기').click()
    with page.expect_response('**/api/learning/action'):play(page,'learningBoard',answers[original['fen']])
    expect(page.locator('#learningRecommendationReturn').get_by_role('button',name='선택했던 진단 추천 다시 시작')).to_be_enabled()
    page.locator('#learningRecommendationReturn').get_by_role('button',name='선택했던 진단 추천 다시 시작').click()
    expect(page.locator('#learningRecommendationReturn')).to_be_hidden()
    state=page.evaluate("api('/learning/dashboard')")
    assert state['active']['session_id']!=original['session_id']
    assert state['active']['scoped_task']['report_id']==report['id']
    assert len(starts)==1
    assert any(a['card_id']==original['card_id'] for a in state['attempts'])


def test_confirmed_race_conflict_is_not_unknown_network_result(isolated):
    page,_=isolated;start(page)
    # A server-confirmed 409 racing the read-only preflight; no real session overwritten.
    page.route('**/api/learning/scoped/start',lambda r:r.fulfill(status=409,json={'detail':{'code':'active_training','message':'진행 중인 훈련을 먼저 완료하세요.'}}))
    page.evaluate("learningScoped('test-report','test-item')")
    expect(page.locator('#learningMessage')).to_contain_text('추천 시작 보류')
    expect(page.locator('#learningRecommendationReturn')).to_be_visible()
    assert '저장 여부 미확인' not in page.locator('#training').inner_text()
    page.unroute('**/api/learning/scoped/start')
    page.route('**/api/learning/scoped/start',lambda r:r.abort('failed'))
    page.locator('#learningRecommendationReturn').get_by_role('button',name='선택했던 진단 추천 다시 시작').click()
    expect(page.locator('#learningBoardFeedback')).to_contain_text('저장 여부 미확인')


def test_partial_read_failure_keeps_confirmed_progress_and_targeted_retry(isolated):
    page,_=isolated;start(page)
    before=page.evaluate("api('/foundations')")
    page.route('**/api/me',lambda r:r.fulfill(status=503,json={'detail':'account read unavailable'}))
    page.route('**/api/learning/dashboard',lambda r:r.fulfill(status=503,json={'detail':'training read unavailable'}))
    page.evaluate("tab('home')");page.reload()
    expect(page.locator('#userBadge')).to_have_text('계정 정보 조회 실패')
    expect(page.locator('#homeNextAction .flow-read-errors')).to_contain_text('계정 정보')
    expect(page.locator('#homeNextAction .flow-read-errors')).to_contain_text('훈련 진행')
    expect(page.locator('#homeNextAction > button')).to_have_text('기초 이어하기')
    expect(page.locator('#homeNextAction > button')).to_be_enabled()
    page.unroute('**/api/me');page.unroute('**/api/learning/dashboard')
    reads=[];page.on('request',lambda r:reads.append(r.url.split('/api')[-1]) if r.method=='GET' and '/api/' in r.url else None)
    page.locator('#homeNextAction .flow-read-errors button').click()
    expect(page.locator('#homeNextAction .flow-read-errors')).to_be_hidden()
    expect(page.locator('#userBadge')).not_to_contain_text('조회 실패')
    assert sorted(reads)==['/learning/dashboard','/me']
    assert page.evaluate("api('/foundations')")==before


def test_late_old_diagnosis_read_does_not_reverse_progress(isolated):
    page,_=isolated;start(page);page.evaluate("tab('diagnosis')")
    page.locator('.diagnostic-choice[data-scope=subskill]').click();page.locator('#diagnosticBegin').click()
    expect(page.locator('#diagnosticResume')).to_contain_text('1 / 4 문항')
    stale=page.evaluate("api('/journey')")
    pending=[];page.route('**/api/journey',lambda r:pending.append(r))
    # An unrelated read started before the confirmed action must not replace the home model.
    page.evaluate("()=>{window.oldJourneyRead=api('/journey');}")
    page.locator('#journeySkip').click();expect(page.locator('#journeyNext')).to_be_visible();page.locator('#journeyNext').click()
    expect(page.locator('#diagnosticResume')).to_contain_text('2 / 4 문항')
    for r in pending:r.fulfill(json=stale)
    page.evaluate('oldJourneyRead');page.unroute('**/api/journey')
    expect(page.locator('#diagnosticResume')).to_contain_text('2 / 4 문항')
    assert '2/4문항' in page.evaluate('cmaActivityFlow.model().detail')


def test_unconfirmed_account_keeps_target_in_memory_without_cross_identity(isolated,site):
    import secrets
    page,context=isolated;start(page);page.evaluate("tab('training')");page.locator('#learningFresh').click()
    expect(page.locator('#learningBoard .sq')).to_have_count(64)
    original=page.evaluate("api('/learning/dashboard')")['active']
    page.evaluate('summaryOwner=null')
    page.evaluate("learningScoped('pending-local-report','pending-local-item')")
    expect(page.locator('#learningRecommendationReturn')).to_contain_text('기존 훈련을 보존')
    new=context.request.post(site[0]+'/api/register',data={'code':'PENDING-'+secrets.token_hex(5),'pin':secrets.token_urlsafe(18)}).json()
    page.evaluate("t=>{token=t;user=null;summaryOwner=null;tab('training')}",new['token'])
    expect(page.locator('#learningRecommendationReturn')).to_be_hidden()
    assert page.evaluate("api('/learning/dashboard')")['active'] is None


def test_old_successful_account_read_does_not_hide_new_failure(isolated):
    page,_=isolated;start(page);page.evaluate("tab('home')")
    me=page.evaluate("api('/me')")
    held=[]
    page.route('**/api/me',lambda r:held.append(r))
    page.evaluate('()=>{window.oldAccountRead=refreshSummaryOnly();}')
    page.wait_for_timeout(100)
    assert len(held)==1
    page.evaluate("()=>{sharedReads.clear();window.newAccountRead=api('/me').catch(()=>{});}")
    page.wait_for_timeout(100)
    assert len(held)==2
    held[1].fulfill(status=503,json={'detail':'new account read failed'})
    page.evaluate('newAccountRead')
    expect(page.locator('#userBadge')).to_have_text('계정 정보 조회 실패')
    held[0].fulfill(json=me);page.evaluate('oldAccountRead')
    expect(page.locator('#userBadge')).to_have_text('계정 정보 조회 실패')
    expect(page.locator('#accountReadRetry')).to_be_visible()
