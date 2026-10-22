"""Real local APIs in isolated Chromium. Viewport emulation is not physical hardware."""
import re
import pytest
from playwright.sync_api import expect
from test_redesign_browser_followup import isolated,site

SIZES=[(1366,768),(1180,650),(360,800),(390,844),(844,390)]
def start(page):
    page.locator('#flowBasicsStart').click()
    expect(page.locator('#foundationWorkspace')).to_be_visible(timeout=20000)
    expect(page).to_have_url(re.compile('#learn/basics/practice$'))
def home(page):
    page.evaluate("tab('home')")
    expect(page.locator('#homeNextAction')).to_be_visible()
def fit(page):
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    for button in page.locator('.view.active button:not(.sq)').all():
        if button.is_visible():
            assert button.evaluate('(e)=>e.scrollWidth<=e.clientWidth+2'),button.inner_text()

@pytest.mark.parametrize('width,height',SIZES)
def test_home_direct_foundation_return_reload_and_free_access(isolated,width,height):
    page,_=isolated;page.set_viewport_size(dict(width=width,height=height))
    expect(page.locator('#flowBasicsStart')).to_be_visible()
    expect(page.locator('#firstTry')).to_be_hidden()
    expect(page.locator('#academyTry')).to_be_hidden()
    expect(page.locator('#flowFreeExamples')).to_be_visible()
    fit(page);start(page)
    before=page.evaluate("api('/foundations')")
    assert before['active']['course_id']=='rook-bishop' and before['revision']==1
    home(page)
    expect(page.locator('#homeNextAction')).to_contain_text('기초 이어하기')
    expect(page.locator('#guestAccess')).to_be_hidden()
    page.reload();expect(page.locator('#homeNextAction')).to_contain_text('룩과 비숍')
    writes=[];page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
    page.locator('#homeNextAction > button').click()
    expect(page.locator('#foundationWorkspace')).to_be_visible()
    assert page.evaluate("api('/foundations')")==before
    assert not writes;fit(page)
    page.locator('#foundationBoard [aria-label^="a1 "]').click();page.locator('#foundationBoard [aria-label^="a4 "]').click()
    expect(page.locator('#foundationOutcome')).to_contain_text('완료')
    expect(page.locator('#foundationReasonBrief')).to_contain_text('세로줄')
    home(page);page.locator('#flowFreeExamples > summary').click()
    expect(page.locator('#academyTry')).to_be_visible();fit(page)

@pytest.mark.parametrize('width,height',SIZES)
def test_diagnostic_single_scope_choice_preserves_active(isolated,width,height):
    page,_=isolated;page.set_viewport_size(dict(width=width,height=height));start(page)
    page.evaluate("tab('diagnosis')")
    expect(page.locator('.diagnostic-options button')).to_have_count(3)
    expect(page.locator('#journeyStart')).to_be_hidden()
    expect(page.locator('#diagnosticBlueprint')).to_contain_text('24문항')
    expect(page.locator('#diagnosticBlueprint')).to_contain_text('8문항')
    page.locator('.diagnostic-choice[data-scope=domain]').click()
    expect(page.locator('#diagnosticChoiceDescription')).to_contain_text('종합 점수 없음')
    expect(page.locator('#diagnosticBegin')).to_be_enabled(timeout=15000)
    page.locator('#diagnosticBegin').click()
    expect(page.locator('#journeyTask')).to_be_visible()
    before=page.evaluate("api('/journey')")
    assert before['active']['total']==8
    home(page);expect(page.locator('#homeNextAction')).to_contain_text('진단 이어하기')
    page.reload();page.locator('#homeNextAction > button').click()
    expect(page.locator('#journeyTask')).to_be_visible()
    assert page.evaluate("api('/journey')")['active']==before['active'];fit(page)

@pytest.mark.parametrize('width,height',SIZES)
def test_training_range_opening_board_and_modes(isolated,width,height):
    page,_=isolated;page.set_viewport_size(dict(width=width,height=height));start(page)
    page.evaluate("tab('training')")
    expect(page.locator('#learningFresh')).to_be_visible()
    expect(page.locator('#learningRouteStatus')).to_be_hidden()
    page.locator('#learningFresh').click()
    expect(page.locator('#learningBoard .sq')).to_have_count(64)
    expect(page.locator('#trainingTaskBrief')).to_contain_text('첫 수 1개만')
    expect(page.locator('#learningTitle')).to_contain_text('첫 수만 판단')
    saved=page.evaluate("api('/learning/dashboard')")['active'];fit(page)
    home(page);expect(page.locator('#homeNextAction')).to_contain_text('훈련 이어하기')
    page.evaluate("tab('profile')");expect(page.locator('#profileNextAction')).to_contain_text('훈련 이어하기')
    page.evaluate("tab('opening')")
    expect(page.locator('#studyOpeningBoard .sq')).to_have_count(64)
    assert not page.locator('#focusOpeningSelection').evaluate('(e)=>e.open')
    assert page.locator('#studyOpeningBoard').bounding_box()['y']<height
    expect(page.locator('#openingModeActions')).to_be_visible();fit(page)
    page.locator('#openingModeActions').get_by_role('button',name='혼자 복습하기',exact=True).click()
    expect(page.locator('#studyMode')).to_have_value('recall')
    expect(page.locator('#studyExplanation')).to_contain_text('가렸어요')
    page.locator('#openingModeActions').get_by_role('button',name='설명 보며 배우기',exact=True).click()
    expect(page.locator('#studyExplanation')).to_contain_text('다음 수 해설')
    assert page.evaluate("api('/learning/dashboard')")['active']==saved
    page.evaluate("document.body.style.zoom='1.25'")
    fit(page)

def test_duplicate_start_and_late_read_do_not_change_destination(isolated):
    page,_=isolated
    starts=[];page.on('request',lambda r:starts.append(r) if r.url.endswith('/foundations/action') else None)
    page.locator('#flowBasicsStart').evaluate('(b)=>{b.click();b.click();}')
    expect(page.locator('#foundationWorkspace')).to_be_visible(timeout=20000)
    assert len(starts)==1
    before=page.evaluate("api('/foundations')");home(page)
    expect(page.locator('#homeNextAction')).to_contain_text('기초 이어하기')
    pending=[];page.route('**/api/foundations',lambda r:pending.append(r))
    page.locator('#homeNextAction > button').click()
    page.evaluate("tab('opening')")
    for r in pending:r.fulfill(json=before)
    expect(page.locator('#opening')).to_have_class(re.compile(r'\bactive\b'))
    page.unroute('**/api/foundations')
    assert page.evaluate("api('/foundations')")==before and len(starts)==1


def test_failed_restore_keeps_retry_and_records(isolated):
    page,_=isolated;start(page);saved=page.evaluate("api('/foundations')")
    page.route('**/api/learning/dashboard',lambda r:r.fulfill(status=503,json={'detail':'격리 테스트 지연'}))
    page.reload();home(page)
    expect(page.locator('#homeNextAction')).to_contain_text('저장된 활동 다시 확인')
    page.unroute('**/api/learning/dashboard')
    page.locator('#homeNextAction > button').click()
    expect(page.locator('#homeNextAction')).to_contain_text('기초 이어하기')
    assert page.evaluate("api('/foundations')")==saved

def test_unsaved_trial_handoff_does_not_credit_success(isolated):
    page,_=isolated
    page.locator('#flowFreeExamples > summary').click();page.locator('#firstTry').click()
    page.locator('#trialBoard [aria-label^="a1 "]').click();page.locator('#trialBoard [aria-label^="a4 "]').click()
    expect(page.locator('#trialContinue')).to_be_visible()
    assert page.evaluate('token')==''
    page.locator('#trialContinue').click()
    expect(page.locator('#foundationWorkspace')).to_be_visible(timeout=20000)
    state=page.evaluate("api('/foundations')")
    assert state['completed']==0 and state['active']['step']==0 and not state['active']['solved']

def test_scoped_recommendation_shared_without_inventing_weakness(isolated):
    page,_=isolated
    page.locator('#flowActivityChoices > summary').click()
    page.locator('#guestAccess').get_by_role('button',name='실력 진단',exact=True).click()
    expect(page.locator('#diagnosis')).to_have_class(re.compile(r'\bactive\b'))
    report=page.evaluate("""async()=>{let s=await api('/journey/start','POST',{mode:'domain',competency:'mate'});while(s.phase!=='complete')s=await api('/journey/action','POST',{session_id:s.session_id,revision:s.revision,action:s.phase==='question'?'skip':'next'});return s.report;}""")
    assert not report['scoped_training']['tasks']
    home(page);expect(page.locator('#homeNextAction > button')).to_have_text('같은 범위 추가 확인 선택')
    reason=page.locator('#homeNextAction .flow-next-detail').inner_text()
    page.evaluate("tab('profile')");expect(page.locator('#profileNextAction .flow-next-detail')).to_have_text(reason)
    page.evaluate("tab('diagnosis')");expect(page.locator('#resultNextAction .flow-next-detail')).to_have_text(reason)
    writes=[];page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
    page.locator('#resultNextAction > button').click()
    expect(page.get_by_label('진단 범위',exact=True)).to_have_value('domain')
    expect(page.get_by_label('진단 분야',exact=True)).to_have_value('mate')
    assert not writes
