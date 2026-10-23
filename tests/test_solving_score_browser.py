"""New score display contract with synthetic server payloads; no grading writes."""
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_redesign_browser_followup import isolated,site
ROOT=Path(__file__).resolve().parents[1]


def score(**updates):
    value={'version':'solving-performance-v1','timing_version':'solving-time-v1','comparison':{'target_policy_version':'authored-target-v1','answer_policy':'goal-alternatives-v2'},'status':'final','A':1,'B':.5,'base_points':2850,'time_adjustment':75,'final_score':2925,
           'target':{'rating':1400,'goal_type':'mate_in_n','choice_count':2,'forced_count':1,'target_seconds':60,'authored_assumption':True},
           'time':{'active_ms':90000,'status':'valid','reason':None},'execution':{'original_choices':2,'original_forced':1,'confirmed_own_moves':3,'confirmed_choices':2,'confirmed_forced':1,'partial_fraction':None,'is_key_skill_estimate':False},'reasons':[]}
    return {**value,**updates}


def render(page,value,item=False,width=1366,height=768):
    page.set_viewport_size(dict(width=width,height=height))
    if not page.evaluate('!!window.cmaSolvingScore'):page.add_script_tag(path=str(ROOT/'public/solving-score.js'))
    page.add_style_tag(path=str(ROOT/'public/solving-score.css'))
    page.evaluate("""r=>{cmaNavigation.go('home');document.querySelector('#scoreFixture')?.remove();const host=document.createElement('section');host.id='scoreFixture';host.className='card';document.querySelector('main').prepend(host);const old=document.createElement('p');old.textContent='이전 기록: 별도 점수 1501';old.id='preservedOldScore';host.append(old);cmaSolvingScore.render(host,r.value,{item:r.item});}""",{'value':value,'item':item})
    return page.locator('#scoreFixture')


@pytest.mark.parametrize('width,height',[(1366,768),(360,800),(390,844),(800,360)])
def test_final_score_breakdown_keyboard_and_no_overflow(isolated,width,height):
    page,_=isolated;panel=render(page,score(),True,width,height)
    expect(panel.locator('.solving-score-total')).to_have_text('2,925 / 3,000')
    expect(panel.locator('.solving-score-breakdown')).to_contain_text('2,850점')
    expect(panel.locator('.solving-score-breakdown')).to_contain_text('+75점')
    expect(panel.locator('#preservedOldScore')).to_have_text('이전 기록: 별도 점수 1501')
    summary=panel.locator('.solving-score-details > summary');summary.focus();page.keyboard.press('Enter')
    expect(panel.locator('.solving-score-details')).to_have_attribute('open','')
    expect(panel.locator('.solving-score-facts')).to_contain_text('60초')
    expect(panel.locator('.solving-score-facts')).to_contain_text('90초')
    expect(panel).to_contain_text('초기 가정')
    expect(panel).to_contain_text('Elo가 아니며')
    expect(panel.locator('.solving-score-technical')).to_contain_text('authored-target-v1')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    if width==360:panel.screenshot(path='/tmp/cma-solving-score-mobile.png')


@pytest.mark.parametrize('updates',[{'status':'held','final_score':None},{'status':'final','time_adjustment':-2},{'status':'final','final_score':None},{'version':'unrecognized-v2'}])
def test_held_unknown_and_invalid_never_display_final_or_zero(isolated,updates):
    page,_=isolated;panel=render(page,score(**updates),True,360,800)
    expect(panel.locator('.solving-score-held')).to_have_text('판단 보류 · 최종 점수 미확정')
    expect(panel.locator('.solving-score-total')).to_have_count(0)
    expect(panel.locator('.solving-score-breakdown')).to_have_count(0)
    expect(panel).to_contain_text('0점으로 처리하지 않습니다')


def test_interruption_has_no_base_penalty_and_practice_is_separate(isolated):
    page,_=isolated;panel=render(page,score(final_score=2850,time_adjustment=0,B=0,reasons=['interrupted']),True)
    expect(panel.locator('.solving-score-total')).to_have_text('2,850 / 3,000')
    expect(panel.locator('.solving-score-breakdown')).to_contain_text('+0점')
    expect(panel.locator('.solving-score-reasons')).to_contain_text('기본 수행 점수는 유지')
    page.evaluate("cmaSolvingScore.render(document.querySelector('#scoreFixture'),{status:'practice',final_score:3000},{item:true})")
    expect(panel.locator('.solving-score-total')).to_have_count(0)
    expect(panel.locator('.solving-practice-notice')).to_contain_text('시간 가산을 바꾸지 않습니다')
    expect(panel.locator('#preservedOldScore')).to_be_visible()


def test_report_long_explanations_and_nested_items_are_readonly(isolated):
    page,_=isolated;long='중단 후 다시 시작한 풀이의 시간 측정 근거를 확인하고 다음 결과를 해석하세요. '*14
    value=score(items=[score(reasons=[long]),score(status='held',final_score=None,reasons=['engine_failed'])],reasons=[long])
    panel=render(page,value,False,360,800)
    requests=[];page.on('request',lambda r:requests.append(r.url) if r.method=='POST' else None)
    items=panel.locator('.solving-score-items');items.locator(':scope > summary').click()
    expect(items.locator('.solving-score')).to_have_count(2)
    expect(items.locator('.solving-score-held')).to_have_count(1)
    page.evaluate("document.querySelector('#scoreFixture').style.fontSize='200%'")
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    technical=panel.locator(':scope > .solving-score > .solving-score-technical > summary');technical.focus();page.keyboard.press('Enter')
    expect(panel.locator(':scope > .solving-score > .solving-score-technical')).to_contain_text('최대 150')
    assert not requests
    page.evaluate("cmaSolvingScore.render(document.querySelector('#scoreFixture'),null)")
    expect(panel.locator('.solving-score')).to_have_count(0)
    expect(panel.locator('#preservedOldScore')).to_be_visible()


def test_backend_contract_uses_recorded_time_and_execution_without_recalculation(isolated):
    from solving_score import item_score,report_score
    from test_solving_score import item
    page,_=isolated
    source=item(solving_time={'version':'solving-time-v1','status':'valid','active_ms':5000,'flags':[]})
    backend=report_score({'items':[source]});panel=render(page,backend)
    expect(panel.locator(':scope > .solving-score > .solving-score-total')).to_have_text('3,000 / 3,000')
    panel.locator('.solving-score-items > summary').click()
    panel.locator('.solving-score-items .solving-score-details > summary').click()
    facts=panel.locator('.solving-score-items .solving-score-facts')
    expect(facts).to_contain_text('67.5초');expect(facts).to_contain_text('5초');expect(facts).to_contain_text('2 / 2')
    unmeasured=item_score(item(solving_time=None))
    page.evaluate("r=>cmaSolvingScore.render(document.querySelector('#scoreFixture'),r,{item:true})",unmeasured)
    expect(panel.locator('.solving-score-total')).to_have_count(0)
    expect(panel.locator('.solving-score-observed')).to_contain_text('2,850점 · 최종 점수 아님')
    expect(panel.locator('.solving-score-reasons')).to_contain_text('최종 점수 확정을 보류')


def test_uncertain_time_flags_and_subsecond_do_not_imply_zero_bonus(isolated):
    page,_=isolated;panel=render(page,score(status='held',final_score=None,time_adjustment=None,time={'active_ms':350,'status':'uncertain','reason':'solving_time_uncertain','flags':['preparation_delay','client_measurement_limited']}),True)
    expect(panel.locator('.solving-score-reasons')).to_contain_text('시간 평가를 보류합니다')
    expect(panel.locator('.solving-score-reasons')).not_to_contain_text('시간 가산을 적용하지')
    panel.locator('.solving-score-details > summary').click()
    expect(panel.locator('.solving-score-facts')).to_contain_text('0.35초')
    value=score(status='held',final_score=None,time_adjustment=None,time={'active_ms':0,'status':'uncertain','reason':'zero_duration_below_resolution'})
    page.evaluate("r=>cmaSolvingScore.render(document.querySelector('#scoreFixture'),r,{item:true})",value)
    panel.locator('.solving-score-details > summary').click()
    expect(panel.locator('.solving-score-facts')).to_contain_text('측정 분해능 미만')
    expect(panel.locator('.solving-score-reasons')).not_to_contain_text('미측정이어서')
