from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,square
from test_redesign_browser_followup import isolated
from test_visual_evidence_browser import guest
from test_clarity_browser import solution_positions,play


@pytest.mark.parametrize('width,height',[(1366,768),(1180,650),(360,800),(390,844),(844,390)])
def test_initial_entry_remaining_resume_and_bounds(isolated,site,width,height):
    page,_=isolated;page.set_viewport_size({'width':width,'height':height});guest(page)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.evaluate("cmaNavigation.go('diagnosis/initial')")
    expect(page.locator('#initialProfile')).to_contain_text('필수 잔여 48문항')
    page.locator('#initialProfile > button').click()
    expect(page.locator('#journeyTask')).to_be_visible(timeout=20000)
    expect(page.locator('#initialProgress')).to_contain_text('이번 묶음 8문항')
    before=page.evaluate("api('/journey')")
    assert before['initial_profile']['assigned']==8
    page.locator('#journeySkip').click();expect(page.locator('#journeyNext')).to_be_visible()
    page.locator('#journeyPause').click()
    expect(page.locator('#homeNextAction > button')).to_have_text('진단 이어하기')
    page.locator('#homeNextAction > button').click()
    expect(page).to_have_url(site[0]+'/#diagnosis/initial')
    expect(page.locator('#diagnosticOther')).to_be_hidden()
    page.reload();expect(page.locator('#journeyNext')).to_be_visible()
    restored=page.evaluate("api('/journey')")
    assert restored['initial_profile']['assigned']==8 and restored['active']['phase']=='feedback'
    assert restored['initial_profile']['valid']==0
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    out=Path('/tmp/cma-initial-captures');out.mkdir(exist_ok=True)
    page.screenshot(path=str(out/f'active-{width}x{height}.png'),full_page=True)
    assert not errors


def test_full_initial_course_result_training_and_game_observation(isolated,site):
    page,_=isolated;page.set_viewport_size({'width':390,'height':844});guest(page)
    answers=solution_positions()
    # Actual API responses and immutable puzzle solutions; no fabricated completion or scores.
    page.evaluate("cmaNavigation.go('diagnosis/initial')")
    for batch in range(6):
        page.locator('#initialProfile > button').click()
        expect(page.locator('#journeyTask')).to_be_visible(timeout=20000)
        while True:
            state=page.evaluate("cmaJourney.state().active")
            if not state:break
            if state['phase']=='feedback':
                page.locator('#journeyNext').click()
            else:play(page,'journeyBoard',answers[state['question']['fen']])
            page.wait_for_function("document.querySelector('#diagnosis').getAttribute('aria-busy')==='false'")
            page.wait_for_timeout(1500)
        expect(page.locator('#initialProfile')).to_be_visible()
    p=page.evaluate("api('/journey')")['initial_profile'];assert p['state']=='ready' and p['valid']==48
    expect(page.locator('#initialProfile')).to_contain_text('3000 / 3000')
    expect(page.locator('#initialProfile')).to_contain_text('체스 전체 숙련을 뜻하지 않습니다')
    page.locator('#initialProfile > button').click()
    expect(page.locator('#initialProfile > button')).to_have_text('맞춤 훈련 시작')
    baseline=page.evaluate("api('/journey')")['initial_profile']
    page.locator('#initialProfile > button').click()
    expect(page.locator('#learningBoard')).to_be_visible(timeout=15000)
    assert page.evaluate("api('/journey')")['initial_profile']==baseline
    page.evaluate("cmaNavigation.go('diagnosis/initial')")
    page.reload();expect(page.locator('#initialProfile')).to_contain_text('초기 관찰 범위 확인 완료')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    page.screenshot(path='/tmp/cma-initial-captures/result-390.png',full_page=True)


def test_confirmed_observation_updates_home_without_new_session(isolated):
    page,_=isolated;guest(page);page.evaluate("cmaNavigation.go('diagnosis/initial')")
    page.locator('#initialProfile > button').click();expect(page.locator('#journeyTask')).to_be_visible(timeout=20000)
    answers=solution_positions()
    for _ in range(30):
        state=page.evaluate("cmaJourney.state().active")
        if state['phase']=='feedback':break
        play(page,'journeyBoard',answers[state['question']['fen']])
        page.wait_for_function("document.querySelector('#diagnosis').getAttribute('aria-busy')==='false'")
    expect(page.locator('#initialProgress')).to_contain_text('필수 관찰 1/48')
    page.locator('#journeyPause').click()
    expect(page.locator('#homeNextAction')).to_contain_text('필수 관찰 1/48')
    expect(page.locator('#homeNextAction')).to_contain_text('필수 잔여 47문항')
    page.locator('#homeNextAction > button').click();expect(page.locator('#journeyNext')).to_be_visible()
    assert page.evaluate("cmaJourney.state().initial_profile.assigned")==8
    page.evaluate("document.documentElement.style.zoom='2'")
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
