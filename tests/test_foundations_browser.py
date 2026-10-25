import re
"""Real isolated account APIs and Chromium. No production mutations."""
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page
from test_study_browser import login


def open_rules(page):
    page.evaluate('cmaStartingLevel.open()')
    page.get_by_role('button',name='룰부터 배우기',exact=True).click()
    expect(page.locator('#learn')).to_contain_class('view active')
    expect(page.locator('#foundationHeading')).to_be_focused()
    expect(page.locator('#foundationRecommendedBadge')).to_have_text('추천')


def choose_course(page, course):
    if not page.locator('#foundationCourseList').evaluate('e=>e.open'):
        page.locator('#foundationCourseList > summary').click()
    page.locator(f'#foundation-open-{course}').click()


def move(page,from_,to,promotion=None):
    with page.expect_response('**/api/foundations/action') as response:
        page.locator(f'#foundationBoard [aria-label^="{from_} "]').click()
        page.locator(f'#foundationBoard [aria-label^="{to} "]').click()
        if promotion:page.locator('#cmaPromotionModal').get_by_role('button',name=re.compile({'q':'퀸','r':'룩','b':'비숍','n':'나이트'}[promotion]+'$')).click()
    assert response.value.status==200,response.value.text()
    return response.value.json()


@pytest.mark.parametrize('width,height',[(320,640),(400,860),(1280,900)])
def test_rules_route_saved_progress_layout_and_keyboard(page,site,width,height):
    login(page,site);page.set_viewport_size({'width':width,'height':height})
    before=page.evaluate("api('/journey/start','POST',{mode:'balanced'})")
    training=page.evaluate("api('/learning/start','POST',{fresh:true})")
    course=page.evaluate("api('/v9/course/start','POST',{theme:'mateIn1',level:'입문'})")
    open_rules(page)
    assert page.evaluate("api('/journey')")['active']==before
    assert page.evaluate("api('/learning/dashboard')")['active']==training
    saved=page.evaluate("api('/v9/session/course')")
    assert saved['session_id']==course['session_id']
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    # Exercise the retained three-step course explicitly; the primary entry is now introductory.
    if not page.locator('#foundationCourseList').evaluate('e=>e.open'):
        page.locator('#foundationCourseList > summary').click()
    page.locator('#foundation-open-rook-bishop').focus();page.keyboard.press('Enter')
    expect(page.locator('#foundationStepTitle')).to_be_focused()
    expect(page.locator('#foundationBoard .sq:enabled')).to_have_count(64)
    wrong=move(page,'a1','b2');assert not wrong['active']['solved']
    expect(page.locator('#foundationFeedback')).to_contain_text('방향')
    page.locator('#foundationAlternative summary').click()
    page.locator('#foundationFrom').select_option('a1');page.locator('#foundationTo').select_option('a4')
    page.locator('#foundationSubmit').focus();page.keyboard.press('Enter')
    expect(page.locator('#foundationFeedback')).to_contain_text('도착')
    # Solved boards remain clickable for square explanations, but cannot submit moves.
    solved=page.evaluate("api('/foundations')")
    assert solved['active']['solved']
    page.locator('#foundationBoard [aria-label^=a4]').click()
    page.locator('#foundationBoard [aria-label^=a5]').click()
    assert page.evaluate("api('/foundations')")==solved
    page.get_by_role('button',name='다음 단계',exact=True).click()
    expect(page.locator('#foundationStepTitle')).to_contain_text('2/3')
    page.reload()
    expect(page.locator('#learn')).to_contain_class('view active')
    expect(page.locator('#startingLevelDialog')).not_to_be_visible()
    page.evaluate('cmaFoundations.openRecommended()')
    expect(page.locator('#foundationStepTitle')).to_contain_text('2/3')
    assert page.evaluate("api('/journey')")['active']==before
    assert page.evaluate("api('/learning/dashboard')")['active']==training
    assert page.evaluate("api('/v9/session/course')")['session_id']==course['session_id']
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    out=Path(__file__).resolve().parents[1]/'docs/qa-foundations';out.mkdir(exist_ok=True)
    page.locator('#foundationWorkspace').scroll_into_view_if_needed()
    page.screenshot(path=str(out/f'practice-{width}.png'),full_page=True)
    page.evaluate("cmaNavigation.go('learn/basics')");page.get_by_text('다른 학습으로 이동 · 저장된 활동 보존',exact=True).click()
    page.locator('#foundationReturnDiagnosis').click()
    expect(page.locator('#journeyProgress')).to_have_text('1 / 24 문항')


def test_promotion_judgement_retry_and_choice_changes(page,site):
    login(page,site);page.evaluate("cmaNavigation.go('learn/basics')")
    expect(page.locator('#foundationCards article')).to_have_count(10)
    page.evaluate("cmaNavigation.go('learn/basics')")
    choose_course(page,'promotion')
    wrong=move(page,'a7','a8','n');assert not wrong['active']['solved']
    expect(page.locator('#foundationFeedback')).to_contain_text('합법적인 수')
    move(page,'a7','a8','q')
    page.get_by_role('button',name='다음 단계',exact=True).click()
    move(page,'a7','a8','n')
    expect(page.locator('[data-course="promotion"]')).to_contain_text('확인 완료')
    # Other self-selected levels stay on their current view; do not force the academy.
    page.evaluate("tab('profile');cmaStartingLevel.open()")
    page.get_by_role('button',name='대국 경험 있음',exact=True).click()
    expect(page.locator('#profile')).to_contain_class('view active')
    page.locator('#startingLevelClose').click();page.reload()
    expect(page.locator('#profile')).to_contain_class('view active')
    page.evaluate("cmaNavigation.go('learn/basics')")
    page.evaluate("cmaNavigation.go('learn/basics')")
    expect(page.locator('[data-course="promotion"]')).to_contain_text('확인 완료')
    # A failed read prevents stale-board submissions until an explicit successful retry.
    page.route('**/api/foundations',lambda r:r.fulfill(status=503,json={'detail':'temporary local fixture failure'}))
    page.locator('#foundationReload').click()
    expect(page.locator('#foundationStatus')).to_contain_text('불러오지 못했습니다')
    expect(page.locator('#foundationBoard .sq:enabled')).to_have_count(0)
    page.unroute('**/api/foundations');page.locator('#foundationReload').click()
    expect(page.locator('#foundationStatus')).to_contain_text('진단 점수와 훈련 크레딧에 포함하지 않습니다')
    page.evaluate("cmaNavigation.go('learn/basics')");page.get_by_text('다른 학습으로 이동 · 저장된 활동 보존',exact=True).click()
    page.locator('#foundationToTactics').click();page.locator('#academySearch').fill('없는과목123')
    expect(page.locator('#academyTactics')).to_contain_text('맞는 과목이 없습니다')
    page.locator('#academySearch').fill('')
    expect(page.locator('#v9CourseCards button:visible')).not_to_have_count(0)


def test_all_authored_steps_with_real_board_and_judgement_controls(page,site):
    from foundation_content import COURSES,CHOICES
    login(page,site);page.set_viewport_size({'width':1280,'height':900})
    page.evaluate("cmaNavigation.go('learn/basics')")
    expect(page.locator('#foundationCards article')).to_have_count(10)
    page.evaluate("cmaNavigation.go('learn/basics')")
    before=page.evaluate("api('/me')")['stats']
    page.evaluate("async()=>{let s=await api('/journey/start','POST',{mode:'balanced'});while(s.phase!=='complete')s=await api('/journey/action','POST',{session_id:s.session_id,revision:s.revision,action:s.phase==='question'?'skip':'next'});}")
    cycle=page.evaluate("api('/journey')")['cycle']
    assert cycle['completed']==0 and not cycle['unlocked']
    for course in COURSES:
        page.evaluate("cmaNavigation.go('learn/basics')")
        choose_course(page,course['id'])
        expect(page.locator('#foundationStepTitle')).to_contain_text(course['title'])
        for index,step in enumerate(course['steps']):
            if step['kind']=='judge':
                expect(page.locator('#foundationBoard .sq:enabled')).to_have_count(0)
                page.locator('#foundationAnswers').get_by_role('button',name=CHOICES[step['answer']],exact=True).click()
            else:
                for u in step['line'][::2]:
                    move(page,u[:2],u[2:4],u[4] if len(u)==5 else None)
            expect(page.locator('#foundationFeedback')).to_contain_text(step['reason'])
            if index+1<len(course['steps']):page.locator('#foundationNext').get_by_role('button',name='다음 단계',exact=True).click()
        expect(page.locator(f'[data-course="{course["id"]}"]')).to_contain_text('확인 완료')
    assert all(c['done'] for c in page.evaluate("api('/foundations')")['courses'])
    expect(page.locator('#foundationRecommendedTitle')).to_contain_text('모두 확인')
    assert page.evaluate("api('/me')")['stats']==before
    assert page.evaluate("api('/journey')")['cycle']==cycle
    page.reload();page.evaluate("cmaNavigation.go('learn/basics')")
    assert all(c['done'] for c in page.evaluate("api('/foundations')")['courses'])
    expect(page.locator('#foundationRecommendedTitle')).to_contain_text('모두 확인')
    page.locator('#foundationPrimary').get_by_role('button',name='입문 관찰 선택',exact=True).click()
    expect(page.get_by_role('button',name='입문 관찰 시작 · 최대 6문항',exact=True)).to_be_enabled()


@pytest.mark.parametrize('width,height',[(320,640),(1280,900)])
def test_unstarted_vs_started_zero_progress_and_visible_recommendation(page,site,width,height):
    login(page,site);page.set_viewport_size({'width':width,'height':height})
    page.evaluate('cmaFoundations.openRecommended()')
    expect(page.locator('#foundationHeading')).to_be_focused()
    if not page.locator('#foundationCourseList').evaluate('e=>e.open'):
        page.locator('#foundationCourseList > summary').click()
    expect(page.locator('#foundationCourseList')).to_have_attribute('open','')
    heading=page.locator('#foundationRecommendedTitle')
    expect(heading).to_be_visible();expect(heading).to_contain_text('▶ 다음 기초')
    expect(page.locator('#foundation-recommended-action')).to_be_visible()
    expect(page.locator('#foundationRecommendedBadge')).to_be_visible()
    expect(page.locator('#foundationRecommendedBadge')).to_have_text('추천')
    assert page.locator('#foundationPrimary').evaluate("e=>parseFloat(getComputedStyle(e).borderTopWidth)")>=2
    first=page.locator('[data-course="rook-bishop"]')
    other=page.locator('[data-course="knight-queen"]')
    expect(first.locator('small')).to_contain_text('시작 전')
    expect(other.locator('small')).to_contain_text('시작 전')
    choose_course(page,'rook-bishop')
    expect(first.locator('small')).to_contain_text('연습 중 · 0/3단계')
    square=page.locator('#foundationBoard [aria-label^="a1 "]')
    square.focus();page.keyboard.press('Enter')
    expect(square).to_be_focused();expect(square).to_have_attribute('aria-pressed','true')
    page.keyboard.press('Enter')
    expect(square).to_be_focused();expect(square).to_have_attribute('aria-pressed','false')
    page.evaluate("cmaNavigation.go('learn/basics')")
    if not page.locator('#foundationCourseList').evaluate('e=>e.open'):
        page.locator('#foundationCourseList > summary').click()
    expect(first.get_by_role('button',name='이어서 연습',exact=True)).to_be_visible()
    other.get_by_role('button',name='과정 보기',exact=True).click()
    page.reload();page.evaluate("cmaNavigation.go('learn/basics')")
    expect(first.locator('small')).to_contain_text('연습 중 · 0/3단계')
    expect(other.locator('small')).to_contain_text('연습 중 · 0/2단계')
    expect(page.locator('[data-course="pawn-capture"] small')).to_contain_text('시작 전')
