"""Local Chromium + real foundation API; mobile emulation, not people/device research."""
import re, secrets
import pytest
from playwright.sync_api import expect
from test_redesign_browser_followup import isolated,site


def ready(page):
    page.wait_for_function('!!cmaFoundations.state()?.active && !cmaFoundations.status().busy')


def next_step(page):
    page.locator('#foundationNext').get_by_role('button',name='다음 단계',exact=True).click()
    ready(page)


def move(page,source,target):
    page.locator(f'#foundationBoard [aria-label^="{source} "]').click()
    with page.expect_response('**/api/foundations/action') as response:
        page.locator(f'#foundationBoard [aria-label^="{target} "]').click()
    assert response.value.status==200
    ready(page)
    return response.value.json()


def demo(page):
    expect(page.locator('#foundationObserve')).to_be_enabled()
    before=page.evaluate("api('/foundations')")
    page.get_by_role('button',name='움직임 다시 보기',exact=True).click()
    expect(page.locator('#foundationObserve')).to_be_disabled()
    expect(page.locator('#foundationObserve')).to_be_enabled()
    assert page.evaluate("api('/foundations')")==before
    page.locator('#foundationObserve').click();ready(page)
    assert page.evaluate('cmaFoundations.state().active.check_result')=='observed'


@pytest.mark.parametrize('width,height',[(1366,768),(360,800),(390,844),(844,390)])
def test_new_guest_recognition_demo_guided_independent_transfer(isolated,site,width,height):
    page,_=isolated;page.set_viewport_size(dict(width=width,height=height))
    page.locator('#flowBasicsStart').click();ready(page)
    assert page.evaluate('cmaFoundations.state().active.course_id')=='rook-first-v1'
    expect(page.locator('#foundationPieceName')).to_have_text('이 말은 룩이에요')
    expect(page.locator('#foundationRule')).to_be_visible()
    assert not page.locator('#foundationCourseList').evaluate('e=>e.open')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    page.screenshot(path=f'/tmp/beginner-first-{width}x{height}.png',full_page=True)
    page.locator('#foundationBoard [aria-label^="a1 "]').focus();page.keyboard.press('Enter');ready(page)
    assert page.evaluate('cmaFoundations.state().active.check_result')=='recognised'
    next_step(page);demo(page);next_step(page);demo(page);next_step(page)
    assert page.evaluate('cmaFoundations.state().active.phase')=='guided'
    move(page,'a1','a4');next_step(page)
    assert page.evaluate('cmaFoundations.state().active.phase')=='independent'
    page.locator('#foundationBoard [aria-label^="a1 "]').click()
    expect(page.locator('#foundationBoard .target')).to_have_count(0)
    expect(page.locator('#foundationBoard .foundation-arrows path')).to_have_count(0)
    page.locator('#foundationBoard [aria-label^="b1 "]').click();ready(page)
    assert page.evaluate('cmaFoundations.state().active.check_result')=='first_unaided'
    saved=page.evaluate("api('/foundations')");page.reload();ready(page)
    assert page.evaluate("api('/foundations')")==saved
    next_step(page);move(page,'d4','e4')
    assert page.evaluate('cmaFoundations.state().active.check_result')=='first_unaided'
    assert page.evaluate('cmaFoundations.state().introduction.done')
    assert page.evaluate('cmaFoundations.state().completed')==0
    expect(page.locator('#foundationNext')).to_contain_text('한 번의 확인이 숙련 인증은 아니에요')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    page.screenshot(path=f'/tmp/beginner-{width}x{height}.png',full_page=True)
    page.get_by_role('button',name='다음 권장 과정',exact=True).click();ready(page)
    assert page.evaluate('cmaFoundations.state().active.course_id')=='rook-bishop'
    expect(page.locator('#foundationTeaching')).to_be_visible()


def test_existing_course_resume_and_optional_new_check_preserve_session(isolated,site):
    page,_=isolated;page.locator('#flowBasicsStart').click();ready(page)
    page.evaluate("cmaNavigation.go('learn/basics')")
    page.get_by_role('button',name='이미 알고 있어요 · 원하는 과정 고르기',exact=True).click()
    page.locator('#foundation-open-king-check').click();ready(page)
    move(page,'g1','f2');next_step(page)
    saved=page.evaluate("api('/foundations')")['active']
    page.evaluate("cmaNavigation.go('home')");page.reload()
    page.evaluate("cmaNavigation.foundationStart()")
    ready(page);assert page.evaluate('cmaFoundations.state().active')==saved
    expect(page.locator('#foundationPieceName')).to_contain_text('킹')
    expect(page.locator('#foundationRule')).to_be_visible()
    page.evaluate("cmaNavigation.go('learn/basics')")
    page.get_by_role('button',name='룩 이름·움직임 새 확인',exact=True).click();ready(page)
    assert page.evaluate('cmaFoundations.state().active.course_id')=='rook-first-v1'
    page.evaluate("cmaNavigation.go('learn/basics')")
    page.get_by_role('button',name='이미 알고 있어요 · 원하는 과정 고르기',exact=True).click()
    page.locator('#foundation-open-king-check').click();ready(page)
    assert page.evaluate('cmaFoundations.state().active')==saved


    page.evaluate("cmaNavigation.go('learn/basics')")
    page.locator('#foundationCourseList').evaluate('e=>e.open=true')
    page.locator('#foundation-open-mate-stalemate').click();ready(page)
    move(page,'g6','g7');next_step(page)
    expect(page.locator('#foundationPiecePicture img')).to_have_attribute('src',re.compile(r'/bK\.svg$'))
    expect(page.locator('#foundationTurn')).to_contain_text('어두운색')


def test_reduced_motion_keyboard_and_save_failure_preserves_state(isolated,site):
    page,_=isolated;page.emulate_media(reduced_motion='reduce');page.set_viewport_size(dict(width=390,height=844))
    page.locator('#flowBasicsStart').click();ready(page)
    page.locator('#foundationAnswers').get_by_role('button',name=re.compile('룩 선택')).focus();page.keyboard.press('Enter');ready(page)
    next_step(page);expect(page.locator('#foundationObserve')).to_be_enabled()
    before=page.evaluate("api('/foundations')")
    page.route('**/api/foundations/action',lambda r:r.fulfill(status=503,json={'detail':'격리 검사 저장 실패'}))
    page.locator('#foundationObserve').click()
    expect(page.locator('#foundationSave')).to_contain_text('저장 여부 미확인')
    expect(page.locator('#foundationSaveRetry')).to_be_visible()
    assert page.evaluate("api('/foundations')")==before
    page.unroute('**/api/foundations/action');page.locator('#foundationSaveRetry').click();ready(page)
    assert page.evaluate("api('/foundations')")==before
    page.evaluate("document.documentElement.style.zoom='2'")
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')


def test_new_account_separate_from_guest_and_completed_legacy_optional_intro(isolated,site):
    from foundation_content import COURSES
    page,context=isolated;page.locator('#flowBasicsStart').click();ready(page)
    page.locator('#foundationBoard [aria-label^="a1 "]').click();ready(page)
    guest=page.evaluate('token');guest_before=page.evaluate("api('/foundations')")
    account=context.request.post(site[0]+'/api/register',data={'code':'BEGINNER-'+secrets.token_hex(4),'pin':secrets.token_urlsafe(14)})
    assert account.status==200
    account_token=account.json()['token']
    page.evaluate("t=>{localStorage.setItem('chess_token',t);localStorage.setItem('cma_identity','account')}",account_token)
    page.reload();page.wait_for_function('token===localStorage.getItem("chess_token")')
    state=page.evaluate("api('/foundations')")
    assert state['active'] is None and not state['introduction']['started']
    # Complete the preserved standard-course protocol in this isolated synthetic account.
    page.evaluate('''async courses=>{let s=await api('/foundations');const act=async(action,course_id,value='')=>{s=await api('/foundations/action','POST',{action,course_id,value,revision:s.revision,step:s.active?.step||0})};for(const c of courses){await act('start',c.id);for(let i=0;i<c.steps.length;i++){const step=c.steps[i];if(step.kind==='judge')await act('answer',c.id,step.answer);else for(let j=0;j<step.line.length;j+=2)await act('move',c.id,step.line[j]);if(i+1<c.steps.length)await act('next',c.id);}}}''',COURSES)
    page.evaluate("cmaNavigation.go('home')");page.reload()
    page.wait_for_function('!!cmaFoundations.state()')
    page.evaluate("cmaNavigation.foundationStart()")
    expect(page.locator('#foundationCourseList')).to_have_attribute('open','')
    expect(page.locator('#foundationPrimary')).to_contain_text('모두 확인')
    assert page.evaluate('cmaFoundations.state().completed')==10
    assert not page.evaluate('cmaFoundations.state().introduction.done')
    page.get_by_role('button',name='룩 이름·움직임 새 확인',exact=True).click();ready(page)
    assert page.evaluate('cmaFoundations.state().active.phase')=='recognition'
    assert page.evaluate('cmaFoundations.state().completed')==10
    assert context.request.get(site[0]+'/api/foundations',headers={'Authorization':'Bearer '+guest}).json()==guest_before
