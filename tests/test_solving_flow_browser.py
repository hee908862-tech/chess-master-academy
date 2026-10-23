"""New clock in actual local Chromium and actual SQLite API, isolated guest only."""
import pytest
from playwright.sync_api import expect
from test_redesign_browser_followup import isolated,site
from test_clarity_browser import solution_positions,play


def start(page,site):
    page.add_init_script("localStorage.setItem('cma_prefs',JSON.stringify({soundOn:false}));")
    page.goto(site[0]+'/#diagnosis/initial')
    page.get_by_role('button',name='로그인 없이 초기 진단 시작',exact=True).click()
    page.wait_for_function('!!token && !cmaJourney.status().busy')
    page.evaluate("cmaNavigation.go('diagnosis/subskill')")
    page.wait_for_function('!cmaJourney.status().busy')
    page.evaluate("cmaJourney.startScoped('subskill','mate','mateIn1')")
    expect(page.locator('#journeyTask')).to_be_visible()
    page.wait_for_function('cmaJourney.state()?.active?.solving_score_version===\'solving-performance-v1\'')


@pytest.mark.parametrize('width,height',[(1366,768),(360,800),(390,844),(1366,540),(800,360)])
def test_ready_solve_feedback_freeze_manual_next_and_server_saved_score(isolated,site,width,height):
    page,_=isolated;page.set_viewport_size(dict(width=width,height=height));start(page,site)
    expect(page.locator('#journeyClock')).to_be_visible()
    assert not page.evaluate('cmaSolvingClock.canInput()')
    expect(page.locator('#journeySkip')).to_be_disabled()
    expect(page.locator('#journeyGoal')).to_be_hidden()
    page.wait_for_function('cmaSolvingClock.canInput()',timeout=15000)
    expect(page.locator('#journeyGoal')).to_be_visible()
    q=page.evaluate('cmaJourney.state().active.question')
    page.wait_for_timeout(350)
    play(page,'journeyBoard',solution_positions()[q['fen']])
    page.wait_for_function("!cmaJourney.status().busy && cmaJourney.state().active?.phase==='feedback'")
    result=page.evaluate("api('/journey')")['active']
    score=result['feedback']['solving_score'];clock=result['feedback']['solving_time']
    assert score['A']==1 and score['base_points']==2850,score
    assert score['final_score']==3000 and score['time_adjustment']==150,score
    expect(page.locator('#journeyFeedback .solving-score')).to_contain_text('3,000')
    shown=page.locator('#journeyClock').inner_text();page.wait_for_timeout(1300)
    assert page.locator('#journeyClock').inner_text()==shown
    assert page.evaluate("api('/journey')")['active']['feedback']['solving_time']==clock
    assert not page.evaluate('cmaSolvingClock.canInput()')
    assert page.evaluate('cmaJourney.state().active.index')==0
    page.locator('#journeyNext').dblclick()
    page.wait_for_function("!cmaJourney.status().busy && cmaJourney.state().active?.index===1")
    assert not page.evaluate('cmaSolvingClock.canInput()')
    page.wait_for_function('cmaSolvingClock.canInput()',timeout=15000)
    assert page.evaluate('cmaJourney.state().active.index')==1
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')


def test_reload_and_pause_keep_performance_without_time_bonus(isolated,site):
    page,_=isolated;start(page,site);page.wait_for_function('cmaSolvingClock.canInput()',timeout=15000)
    page.reload();page.wait_for_function('cmaSolvingClock.canInput()',timeout=15000)
    expect(page.locator('#journeyClock')).to_contain_text('중단')
    q=page.evaluate('cmaJourney.state().active.question');page.wait_for_timeout(300)
    play(page,'journeyBoard',solution_positions()[q['fen']])
    page.wait_for_function("!cmaJourney.status().busy && cmaJourney.state().active?.phase==='feedback'")
    f=page.evaluate("api('/journey')")['active']['feedback']
    assert f['solving_score']['base_points']==2850
    assert f['solving_score']['final_score']==2850,f
    assert f['solving_time']['status']=='interrupted'
    page.reload();expect(page.locator('#journeyClock')).to_contain_text('풀이 종료')
    assert not page.evaluate('cmaSolvingClock.canInput()')


def test_slow_network_and_rejected_input_hold_time_without_changing_goal_result(isolated,site):
    page,_=isolated;start(page,site);page.wait_for_function('cmaSolvingClock.canInput()',timeout=15000)
    q=page.evaluate('cmaJourney.state().active.question');solution=solution_positions()[q['fen']]
    pending=[];page.route('**/api/journey/action',lambda r:pending.append(r))
    play(page,'journeyBoard',solution);page.wait_for_timeout(100)
    assert len(pending)==1
    value=page.locator('#journeyClock .solving-clock-time').inner_text()
    page.wait_for_timeout(3200)
    assert page.locator('#journeyClock .solving-clock-time').inner_text()==value
    pending[0].continue_();page.unroute('**/api/journey/action')
    page.wait_for_function("!cmaJourney.status().busy && cmaJourney.state().active?.phase==='feedback'")
    f=page.evaluate("api('/journey')")['active']['feedback']
    assert f['complete'] and f['solving_score']['base_points']==2850
    assert f['solving_score']['final_score'] is None and f['solving_time']['status']=='uncertain'
    expect(page.locator('#journeyFeedback .solving-score')).to_contain_text('보류')
    assert page.evaluate("api('/journey')")['active']['feedback']==f
