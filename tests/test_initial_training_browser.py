"""Local Chromium with journey/dashboard API doubles, not server ownership tests.
Uses a compatible synthetic baseline; no operating account or stored score writes.
"""
import copy
import re
import pytest
from playwright.sync_api import expect
from test_qa_browser import site, page
from test_initial_profile import real_rows, report
from initial_profile import initialize, freeze, status


@pytest.fixture(scope='module')
def baseline():
    result=report(real_rows());state={'results':[result],'active':None}
    initialize(state,result['corpus_sha256']);freeze(state,'fixture')
    state['initial_profile']['reviewed_at']='fixture'
    value=status(state);value['baseline_id']='baseline-current'
    source=next(s for s in value['sources'] if s['outcome']!='completed')
    value['recommended_source']={k:source[k] for k in ('report_id','item_id')}
    return value


def path_for(p,done=True):
    return {'id':'saved-training-path','initial_baseline_id':p['baseline_id'],
        'diagnosis':dict(p['recommended_source']), 'done':done,'current':4 if done else 0,
        'date':'2026-10-23','selection_reason':'저장한 추천 훈련','source_title':'원래 문제',
        'steps':[{'status':'completed' if done else 'active' if i==0 else 'pending','reason':''} for i in range(4)]}


def setup(page,site,baseline):
    page.goto(site[0]);page.wait_for_function('!!token && !!window.cmaInitial')
    journey=page.evaluate("api('/journey')");learning=page.evaluate("api('/learning/dashboard')")
    journey.update(active=None,results=[],initial_profile=copy.deepcopy(baseline),training={'path_done':True})
    learning.update(active=None,path=None)
    page.route('**/api/journey',lambda r:r.fulfill(json=journey))
    page.route('**/api/learning/dashboard',lambda r:r.fulfill(json=learning))
    return journey,learning


def refresh_home(page):
    page.evaluate("async()=>{await cmaJourney.load();await api('/learning/dashboard');cmaNavigation.go('home');}")


@pytest.mark.parametrize('mismatch',['old_baseline','wrong_source','missing_baseline'])
def test_old_or_unidentified_completed_training_cannot_unlock_game(page,site,baseline,mismatch):
    journey,learning=setup(page,site,baseline)
    learning['path']=path_for(journey['initial_profile'])
    if mismatch=='old_baseline':learning['path']['initial_baseline_id']='previous-baseline'
    elif mismatch=='wrong_source':learning['path']['diagnosis']['item_id']='another-item'
    else:journey['initial_profile'].pop('baseline_id')
    refresh_home(page)
    expect(page.locator('#homeNextAction > button')).not_to_have_text('대국에서 적용하기')
    expect(page.locator('#homeNextAction > button')).to_contain_text('훈련')


def test_current_recommendation_completion_and_new_baseline_transition(page,site,baseline):
    journey,learning=setup(page,site,baseline);learning['path']=path_for(journey['initial_profile'])
    refresh_home(page)
    expect(page.locator('#homeNextAction > button')).to_have_text('대국에서 적용하기')
    # A new baseline never inherits an old path's completion, even for the same source.
    journey['initial_profile']['baseline_id']='baseline-new'
    refresh_home(page)
    expect(page.locator('#homeNextAction > button')).not_to_have_text('대국에서 적용하기')
    expect(page.locator('#homeNextAction > button')).to_contain_text('훈련')


@pytest.mark.parametrize('conflict',['path','active'])
def test_unfinished_other_path_is_resumed_without_replacing_it(page,site,baseline,conflict):
    journey,learning=setup(page,site,baseline)
    learning['path']=path_for(journey['initial_profile'],done=False)
    learning['path']['initial_baseline_id']='older-unfinished-baseline'
    if conflict=='active':
        learning['path']=path_for(journey['initial_profile'],done=True)
        learning['active']={'session_id':'preserved-active','revision':0,'card_id':'source',
            'fen':'7k/5K2/6Q1/8/8/8/8/8 w - - 0 1','legal':['g6g7'],
            'side':'white','mode':'practice','done':False,'goal':'기존 실습',
            'category':'mate','hint_level':0,'playback':[]}
        page.route('**/api/learning/exposure',lambda r:r.fulfill(json={'recorded':True}))
    before=copy.deepcopy(learning);writes=[]
    page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
    refresh_home(page)
    primary=page.locator('#homeNextAction > button')
    expect(primary).to_contain_text('이어하기');primary.click()
    expect(page.locator('#training')).to_have_class(re.compile(r'\bactive\b'))
    assert page.evaluate("api('/learning/dashboard')")==before
    # Resuming records exposure, but never creates/replaces a training session.
    assert all(url.endswith('/api/learning/exposure') for url in writes)
    if conflict=='path':assert writes==[]


def test_primary_training_sends_baseline_and_keeps_score_limits_visible(page,site,baseline):
    journey,learning=setup(page,site,baseline);requests=[]
    def conflict(route):
        requests.append(route.request.post_data_json)
        route.fulfill(status=409,json={'detail':{'code':'active_learning_path','message':'기존 훈련을 보존합니다.'}})
    page.route('**/api/learning/from-diagnosis',conflict)
    refresh_home(page);page.evaluate("cmaNavigation.go('diagnosis/initial')")
    panel=page.locator('#initialProfile')
    for text in ['1~3000','기초 40%','응용 60%','체스 전체 숙련을 뜻하지 않습니다.','잠정',
                 '이번 평가 범위의 수행 점수','측정 난도: 문제은행 기초 600–1199 · 응용 1200–1799',
                 '같은 구간 안의 문항별 난이도 차이는 점수에 반영하지 않습니다.',
                 '난이도 보정된 능력 추정은 아직 구현·검증되지 않았습니다.']:
        expect(panel).to_contain_text(text)
    before=copy.deepcopy(journey['initial_profile'])
    panel.locator(':scope > button.primary').click()
    expect(page.locator('#learningMessage')).to_contain_text('기존 훈련')
    assert requests==[{**baseline['recommended_source'],'initial_baseline_id':baseline['baseline_id']}]
    assert journey['initial_profile']==before
