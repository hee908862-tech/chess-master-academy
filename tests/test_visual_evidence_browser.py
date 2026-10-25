"""Local Chromium with disposable guest identities; mobile emulation, not devices."""
from pathlib import Path
Path('/tmp/cma-pr41-captures').mkdir(exist_ok=True)
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,square
from test_redesign_browser_followup import isolated


def guest(page):
    # Explicitly select the retained course used by these visual assertions.
    from test_activity_flow_browser import start
    start(page)
    page.wait_for_function("document.querySelector('#foundationAcademy').getAttribute('aria-busy')==='false'")


@pytest.mark.parametrize('width,height',[(1366,768),(1180,650),(360,800),(390,844),(844,390)])
def test_auto_en_passant_skip_routes_and_readonly_replay(isolated,site,width,height):
    page,_=isolated;page.set_viewport_size(dict(width=width,height=height));guest(page)
    page.evaluate("cmaNavigation.go('home')")
    skip=page.locator('#homeNextAction .flow-skip-basics');expect(skip).to_be_visible();skip.click()
    before=page.evaluate("api('/foundations')")
    page.evaluate("cmaNavigation.go('home')")
    expect(page.locator('#homeNextAction')).to_contain_text('기초는 건너뛰었습니다')
    page.reload();expect(page.locator('#homeNextAction')).to_contain_text('기초는 건너뛰었습니다')
    assert page.evaluate("api('/foundations')")==before
    page.evaluate("cmaNavigation.go('learn/basics')")
    page.locator('#foundation-open-en-passant').click()
    expect(square(page,'foundationBoard','d5')).to_have_attribute('aria-label','d5 흑 폰')
    expect(page.locator('#foundationDemoStart')).to_be_visible()
    before=page.evaluate("api('/foundations')");writes=[]
    page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
    page.locator('#foundationDemoStart').click()
    expect(square(page,'foundationBoard','d7')).to_have_attribute('aria-label','d7 흑 폰')
    square(page,'foundationBoard','e5').click()
    assert page.locator('#foundationBoard .selected').count()==0
    expect(page.locator('#foundationDemoStart')).to_be_visible()
    assert not writes and page.evaluate("api('/foundations')")==before
    square(page,'foundationBoard','e5').click();square(page,'foundationBoard','d6').click()
    expect(page.locator('#foundationOutcome')).to_contain_text('단계 완료')
    expect(square(page,'foundationBoard','d5')).to_have_attribute('aria-label','d5 빈 칸')
    page.evaluate("cmaNavigation.go('diagnosis')")
    page.locator('.diagnostic-choice[data-scope="balanced"]').click()
    expect(page).to_have_url(site[0]+'/#diagnosis/balanced')
    expect(page.locator('.diagnostic-options')).to_be_hidden()
    expect(page.locator('#diagnosticBegin')).to_be_visible()
    page.reload();expect(page.locator('#diagnosticBegin')).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    out=Path('/tmp/cma-pr41-captures');out.mkdir(exist_ok=True)
    page.screenshot(path=str(out/f'scope-{width}x{height}.png'),full_page=True)


def test_check_mate_arrows_and_square_explanation(isolated,site):
    page,_=isolated;guest(page)
    page.evaluate("cmaNavigation.go('learn/basics')")
    page.locator('#foundation-open-king-check').click()
    square(page,'foundationBoard','g1').click();square(page,'foundationBoard','f2').click()
    page.locator('#foundationNext').get_by_role('button',name='다음 단계',exact=True).click()
    expect(page.locator('#foundationVisualLegend')).to_contain_text('체크 공격')
    assert page.locator('#foundationBoard .foundation-arrows path').count()>=6
    square(page,'foundationBoard','g2').click()
    expect(page.locator('#foundationFeedback')).to_contain_text('g8 룩')
    page.evaluate("cmaNavigation.go('learn/basics')")
    page.locator('#foundation-open-mate-stalemate').click()
    square(page,'foundationBoard','g6').click();square(page,'foundationBoard','g7').click()
    expect(page.locator('#foundationVisualLegend')).to_contain_text('f6가 g7 기물을 보호')
    square(page,'foundationBoard','g7').click()
    expect(page.locator('#foundationFeedback')).to_contain_text('f6 킹')
    page.locator('#foundationBoard').screenshot(path='/tmp/cma-pr41-captures/mate-relations.png')


def test_complete_domain_radar_replay_analysis_and_readonly_state(isolated,site):
    from test_clarity_browser import solution_positions,play
    page,_=isolated;page.set_viewport_size(dict(width=360,height=800));guest(page)
    page.evaluate("cmaNavigation.go('diagnosis')")
    page.locator('.diagnostic-choice[data-scope="domain"]').click()
    page.get_by_label('진단 분야',exact=True).select_option('mate')
    page.locator('#diagnosticBegin').click();expect(page.locator('#journeyTask')).to_be_visible()
    expect(page.locator('#diagnosticBlueprint')).to_be_hidden()
    expect(page.locator('#journeyGoal')).to_have_attribute('data-area','메이트 수순')
    answers=solution_positions();reviewed=False
    for _ in range(100):
        state=page.evaluate("api('/journey')")['active']
        if not state:break
        if state['phase']=='question':
            with page.expect_response('**/api/journey/action'):play(page,'journeyBoard',answers[state['question']['fen']])
        elif state['phase']=='feedback':
            if not reviewed:
                detail=page.locator('#journeyFeedback .diagnostic-replay');detail.locator('summary').click()
                expect(detail.locator('.board .sq')).to_have_count(64)
                expect(detail.locator('.replay-evaluation')).to_contain_text('미분석')
                original=page.evaluate("api('/journey')")['active']
                detail.get_by_role('button',name='다음 수',exact=True).click()
                expect(detail.locator('.replay-effects')).not_to_be_empty()
                detail.get_by_role('button',name='현재 위치 우세 분석',exact=True).click()
                expect(detail.locator('.replay-evaluation')).not_to_contain_text('분석 중',timeout=15000)
                expect(detail.locator('.replay-evaluation')).not_to_contain_text('미분석')
                detail.get_by_role('button',name='처음',exact=True).click()
                assert detail.locator('.board').get_attribute('data-fen')==original['feedback']['replay']['frames'][0]['fen']
                assert page.evaluate("api('/journey')")['active']==original
                reviewed=True
            page.locator('#journeyNext').click()
        page.wait_for_function('!cmaJourney.status().busy')
    result=page.evaluate("api('/journey')")
    assert result['active'] is None and result['profile_evidence']['valid']==8
    assert result['profile_evidence']['areas_ready']==1
    assert result['latest']['score_version']=='skill-index-v1'
    expect(page.locator('#journeyResults .skill-radar')).to_be_visible()
    expect(page.locator('#journeyResults .profile-evidence')).to_contain_text('유효 8/48')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    for width,height in [(360,800),(390,844),(844,390),(1366,768)]:
        page.set_viewport_size(dict(width=width,height=height))
        page.locator('#journeyResults .skill-radar').screenshot(path=f'/tmp/cma-pr41-captures/radar-{width}.png')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    page.reload();expect(page.locator('#journeyResults .profile-evidence')).to_contain_text('유효 8/48')
    assert page.evaluate("api('/journey')")['latest']==result['latest']


def test_radar_overlay_only_matching_scope_version_and_comparable_data(isolated,site):
    page,_=isolated;guest(page);page.evaluate("tab('diagnosis')");page.evaluate("cmaJourney.load()");page.wait_for_function('!cmaJourney.status().busy')
    page.evaluate("""()=>{const areas=['mate','calculation','capture','defense','promotion','endgame'].map((id,i)=>({id,label:id,count:4,performance:{score:500+i*400,scale_min:1,scale_max:3000,comparable:true,observed:4,band_counts:[2,2]}}));window.sampleRadar={id:'new',at:'2026-10-22',score_version:'skill-index-v1',version:'journey-v5',competency_version:'competency-v2',measurement_scope:'broad_area_execution_v1',mode:'balanced',corpus_sha256:'sample',areas};window.oldRadar=structuredClone(sampleRadar);oldRadar.id='old';oldRadar.at='2026-10-21';for(const a of oldRadar.areas)a.performance.score=1;window.drawRadar=(change)=>{const prior={...oldRadar,...change};growthProfile({results:[prior,sampleRadar]});const h=document.getElementById('journeyResults');h.replaceChildren();growthReport(h,sampleRadar,null,()=>{},()=>{},()=>{},true);};drawRadar({});}""")
    checkbox=page.locator('#journeyResults .radar-compare input');expect(checkbox).to_be_visible();checkbox.check()
    expect(page.locator('#journeyResults .radar-previous-values')).to_contain_text('메이트 1')
    for change in [{'version':'journey-v4'},{'mode':'domain'},{'corpus_sha256':'other'},{'measurement_scope':'uncued_execution'}]:
        page.evaluate('(c)=>drawRadar(c)',change)
        expect(checkbox).to_have_count(0)
    page.evaluate('drawRadar({})');page.set_viewport_size(dict(width=360,height=800));checkbox.check()
    page.locator('#journeyResults .skill-radar').screenshot(path='/tmp/cma-pr41-captures/radar-overlay.png')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')


def test_reduced_motion_setting_preserves_en_passant_and_new_state(isolated,site):
    page,_=isolated;guest(page)
    page.evaluate("cmaNavigation.go('profile/settings')")
    page.locator('#reduceBoardMotion').check()
    page.reload();expect(page.locator('#reduceBoardMotion')).to_be_checked()
    page.evaluate("cmaNavigation.go('learn/basics')")
    page.locator('#foundation-open-en-passant').click()
    expect(page.locator('#foundationDemoStart')).to_be_visible()
    expect(page.locator('#foundationFeedback')).not_to_contain_text('읽기 전용')
    assert page.locator('.cma-motion-ghost').count()==0
    square(page,'foundationBoard','e5').click();square(page,'foundationBoard','d6').click()
    expect(page.locator('#foundationOutcome')).to_contain_text('단계 완료')
    assert page.locator('.cma-motion-ghost').count()==0


def test_home_reload_unfinished_ep_resumes_demo_without_stuck_input(isolated,site):
    page,_=isolated;guest(page)
    page.evaluate("cmaNavigation.go('learn/basics')");page.locator('#foundation-open-en-passant').click()
    expect(page.locator('#foundationDemoStart')).to_be_visible()
    before=page.evaluate("api('/foundations')")
    page.evaluate("tab('home')");page.reload()
    expect(page.locator('#homeNextAction')).to_contain_text('앙파상')
    page.wait_for_timeout(900) # Previously consumed a hidden presentation timer.
    page.locator('#homeNextAction > button').click()
    expect(page.locator('#foundationDemoStart')).to_be_visible()
    expect(square(page,'foundationBoard','d5')).to_have_attribute('aria-label','d5 흑 폰')
    assert page.evaluate("api('/foundations')")==before
    square(page,'foundationBoard','e5').click();square(page,'foundationBoard','d6').click()
    expect(page.locator('#foundationOutcome')).to_contain_text('단계 완료')


def test_slow_blueprint_selection_and_visible_error_retry(isolated,site):
    page,_=isolated;guest(page);catalog=page.evaluate("api('/journey/blueprint')")
    pending=[];page.route('**/api/journey/blueprint',lambda r:pending.append(r))
    page.reload();page.evaluate("tab('diagnosis')")
    expect(page.locator('#diagnosticCatalogState')).to_contain_text('확인 중')
    page.evaluate("()=>{window.selectionJob=cmaDiagnosticChoice.select({level:'domain',competency:'promotion'});}")
    assert len(pending)==1
    pending.pop().fulfill(json=catalog)
    expect(page).to_have_url(site[0]+'/#diagnosis/domain')
    expect(page.get_by_label('진단 분야',exact=True)).to_have_value('promotion')
    page.unroute('**/api/journey/blueprint')
    page.route('**/api/journey/blueprint',lambda r:r.fulfill(status=503,json={'detail':'목록 조회 실패 테스트'}))
    page.evaluate("tab('diagnosis')");page.reload()
    expect(page.locator('#diagnosticCatalogState')).to_be_visible()
    expect(page.locator('#diagnosticCatalogState')).to_contain_text('조회 실패')
    page.unroute('**/api/journey/blueprint')
    page.get_by_role('button',name='진단 목록 다시 확인',exact=True).click()
    expect(page.locator('.diagnostic-choice')).to_have_count(3)
    expect(page.locator('#diagnosticCatalogState')).to_be_hidden()


def test_resume_scope_does_not_flash_legacy_choices_during_delayed_read(isolated,site):
    page,_=isolated;guest(page)
    page.evaluate("cmaNavigation.go('diagnosis/subskill')")
    expect(page.locator('#diagnosticBegin')).to_be_enabled()
    page.locator('#diagnosticBegin').click()
    expect(page.locator('#journeyTask')).to_be_visible()
    page.locator('#journeySkip').click()
    expect(page.locator('#journeyNext')).to_be_visible()
    before=page.evaluate("api('/journey')")['active']
    page.locator('#journeyPause').click()
    page.evaluate("""()=>{const real=api;api=async(...a)=>{const value=await real(...a);if(a[0]==='/journey')await new Promise(r=>setTimeout(r,700));return value;};window.badLegacy=false;new MutationObserver(()=>{if(document.querySelector('#diagnosis').classList.contains('active')&&!document.querySelector('#journeyTask').hidden&&!document.querySelector('#diagnosticOther').hidden)window.badLegacy=true;}).observe(document.querySelector('#diagnosticOther'),{attributes:true});cmaJourney.open();}""")
    expect(page).to_have_url(site[0]+'/#diagnosis/subskill')
    expect(page.locator('#diagnosticOther')).to_be_hidden()
    page.wait_for_timeout(850)
    assert not page.evaluate('badLegacy')
    page.evaluate("cmaNavigation.go('profile')")
    page.locator('#profileNextAction').get_by_role('button',name='진단 이어하기',exact=True).click()
    expect(page).to_have_url(site[0]+'/#diagnosis/subskill')
    page.reload();expect(page.locator('#journeyNext')).to_be_visible()
    expect(page.locator('#diagnosticOther')).to_be_hidden()
    page.evaluate("cmaNavigation.go('home')")
    page.go_back();expect(page.locator('#journeyNext')).to_be_visible()
    expect(page.locator('#diagnosticOther')).to_be_hidden()
    assert page.evaluate("api('/journey')")['active']==before


@pytest.mark.parametrize('count',[0,1,2,6])
def test_summary_distinguishes_sparse_evidence_from_equal_scores(isolated,site,count):
    page,_=isolated;guest(page)
    page.evaluate("async()=>{cmaNavigation.go('diagnosis');await cmaJourney.load();}")
    page.evaluate("""count=>{const areas=['mate','calculation','capture','defense','promotion','endgame'].map((id,i)=>({id,label:id,count:i<count?4:0,performance:{score:i<count?1500:null,comparable:i<count,observed:i<count?4:0,band_counts:i<count?[2,2]:[0,0]}}));const report={score_version:'skill-index-v1',areas,insights:{balanced:true,message:'분야별 수행이 고르게 나타났어요',strengths:[],priorities:[]}};window.summaryOriginal=JSON.stringify(report);window.summaryFixture=report;const host=document.createElement('section');host.id='summaryFixtureHost';document.body.append(host);growthReport(host,report,null,()=>{},()=>{},()=>{},true);}""",count)
    intro=page.locator('#summaryFixtureHost .growth-intro')
    if count<2:expect(intro).to_contain_text('분야 간 비교 근거가 부족')
    else:expect(intro).to_contain_text(f'{count}개 분야의 이번 점수가 같습니다')
    expect(intro).not_to_contain_text('고르게 나타났어요')
    assert page.evaluate('JSON.stringify(summaryFixture)===summaryOriginal')
