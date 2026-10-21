import re
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page,square
from test_study_browser import login

def start(page,site,course='rook-bishop'):
    login(page,site);page.evaluate("cmaNavigation.go('learn/basics')")
    page.locator('#foundation-open-'+course).click()
    expect(page.locator('#foundationWorkspace')).to_be_visible()
    expect(page.locator('#foundationAcademy')).to_have_attribute('aria-busy','false')

@pytest.mark.parametrize('width',[360,1280])
def test_guided_status_save_delay_layout_and_explicit_next(page,site,width):
    start(page,site);page.set_viewport_size({'width':width,'height':900})
    expect(page.locator('#foundationVisualLegend')).to_contain_text('a1 → a4')
    expect(page.locator('#foundationOutcome')).to_have_attribute('aria-atomic','true')
    y=page.locator('#foundationBoard').bounding_box()['y']
    page.evaluate("""()=>{const real=api;api=async(...a)=>{const d=await real(...a);if(a[0]==='/foundations/action')return new Promise(r=>window.releaseFoundation=()=>r(d));return d;};}""")
    square(page,'foundationBoard','a1').click();square(page,'foundationBoard','a4').click()
    page.wait_for_function('!!window.releaseFoundation')
    expect(page.locator('#foundationSave')).to_contain_text('응답 대기')
    expect(page.locator('#foundationOutcome')).not_to_contain_text('단계 완료')
    assert abs(page.locator('#foundationBoard').bounding_box()['y']-y)<2
    page.evaluate('releaseFoundation()')
    expect(page.locator('#foundationOutcome')).to_contain_text('단계 완료')
    expect(page.locator('#foundationSave')).to_contain_text('판정·저장 확인됨')
    expect(page.locator('#foundationStepTitle')).to_contain_text('1/3')
    assert abs(page.locator('#foundationBoard').bounding_box()['y']-y)<2
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    out=Path('/tmp/cma-foundation-feedback-captures');out.mkdir(exist_ok=True)
    page.screenshot(path=str(out/f'complete-{width}.png'),full_page=True)

@pytest.mark.parametrize('promotion',['q','r','b','n'])
def test_promotion_picker_selected_piece_goal_and_cancel(page,site,promotion):
    start(page,site,'promotion');before=page.evaluate("api('/foundations')")
    writes=[];page.on('request',lambda r:writes.append(r.url) if '/foundations/action' in r.url else None)
    square(page,'foundationBoard','a7').click();square(page,'foundationBoard','a8').click()
    expect(page.locator('#cmaPromotionModal')).to_be_visible();page.keyboard.press('Escape')
    assert not writes and page.evaluate("api('/foundations')")==before
    expect(square(page,'foundationBoard','a7')).to_be_focused()
    square(page,'foundationBoard','a8').click()
    page.locator('#cmaPromotionModal').get_by_role('button',name=re.compile({'q':'퀸','r':'룩','b':'비숍','n':'나이트'}[promotion]+'$')).click()
    expect(page.locator('#foundationAcademy')).to_have_attribute('aria-busy','false')
    result=page.evaluate("api('/foundations')")
    assert result['active']['solved']==(promotion=='q')
    if promotion!='q':expect(page.locator('#foundationOutcome')).to_contain_text('합법적인 다른 수')


def test_ep_demo_and_overlay_replay_are_read_only(page,site):
    start(page,site,'en-passant');before=page.evaluate("api('/foundations')")
    writes=[];page.on('request',lambda r:writes.append(r.url) if '/api/' in r.url and r.method!='GET' else None)
    page.locator('#foundationDemoStart').click();expect(page.locator('#foundationVisualLegend')).to_contain_text('교육 예시')
    expect(square(page,'foundationBoard','d7')).to_have_attribute('aria-label','d7 흑 폰')
    page.screenshot(path='/tmp/cma-foundation-feedback-captures/ep-before.png',full_page=True)
    page.locator('#foundationDemoNext').click();expect(square(page,'foundationBoard','d5')).to_have_attribute('aria-label','d5 흑 폰')
    page.screenshot(path='/tmp/cma-foundation-feedback-captures/ep-after.png',full_page=True)
    page.locator('#foundationVisualToggle').click();expect(page.locator('.foundation-arrows')).to_have_count(0)
    page.locator('#foundationVisualToggle').click();page.locator('#foundationDemoReturn').click()
    assert page.evaluate("api('/foundations')")==before and writes==[]
    expect(page.locator('#foundationVisualLegend')).to_contain_text('e5 → d6')


def test_save_failure_recovery_and_long_message_do_not_move_board(page,site):
    start(page,site);y=page.locator('#foundationBoard').bounding_box()['y']
    page.route('**/api/foundations/action',lambda r:r.fulfill(status=503,json={'detail':'일시적인 저장 오류입니다. '*20}))
    square(page,'foundationBoard','a1').click();square(page,'foundationBoard','a4').click()
    expect(page.locator('#foundationSave')).to_contain_text('저장 여부 미확인')
    expect(page.locator('#foundationOutcome')).not_to_contain_text('완료')
    assert abs(page.locator('#foundationBoard').bounding_box()['y']-y)<2
    page.unroute('**/api/foundations/action');page.locator('#foundationSaveRetry').click()
    expect(page.locator('#foundationSave')).to_contain_text('서버 저장 상태 확인됨')
    assert not page.evaluate("api('/foundations')")['active']['solved']

@pytest.mark.parametrize('switch_account',[False,True])
def test_saved_response_delay_leave_or_account_change_no_followup_or_focus_theft(page,site,switch_account):
    start(page,site)
    other=page.evaluate("async()=> (await api('/register','POST',{code:'FB-'+crypto.randomUUID().slice(0,8),pin:'local-foundation-pin'})).token")
    page.evaluate("""()=>{const original=api;window.foundationPosts=0;api=async(...a)=>{if(a[0]==='/foundations/action')window.foundationPosts++;const d=await original(...a);if(a[0]==='/foundations/action')return new Promise(r=>window.releaseSavedFoundation=()=>r(d));return d;};}""")
    square(page,'foundationBoard','a1').click();square(page,'foundationBoard','a4').click()
    page.wait_for_function('!!window.releaseSavedFoundation')
    # A second UI action while the first authoritative response waits cannot submit.
    page.evaluate("document.querySelector('#foundationSubmit').click()")
    if switch_account:page.evaluate("identity=>{token=identity;tab('home');}",other)
    else:page.evaluate("tab('home')")
    focused=page.evaluate('document.activeElement.id')
    page.evaluate('releaseSavedFoundation()')
    expect(page.locator('#home')).to_have_class('view active')
    assert page.evaluate('document.activeElement.id')==focused
    assert page.evaluate('foundationPosts')==1
    if switch_account:
        expect(page.locator('#foundationWorkspace')).not_to_be_visible()
        assert page.evaluate("api('/foundations')")['active'] is None
    else:
        page.evaluate("cmaNavigation.go('learn/basics/practice')")
        expect(page.locator('#foundationOutcome')).to_contain_text('단계 완료')
        page.reload();expect(page.locator('#foundationOutcome')).to_contain_text('단계 완료')
        assert page.evaluate("api('/foundations')")['active']['solved']


def test_promotion_leave_cancels_no_submit_and_keeps_destination_focus(page,site):
    start(page,site,'promotion');before=page.evaluate("api('/foundations')")
    writes=[];page.on('request',lambda r:writes.append(r.url) if '/foundations/action' in r.url else None)
    square(page,'foundationBoard','a7').focus();page.keyboard.press('Enter')
    square(page,'foundationBoard','a8').focus();page.keyboard.press('Enter')
    expect(page.locator('#cmaPromotionModal')).to_be_visible()
    page.evaluate("tab('home')")
    expect(page.locator('#cmaPromotionModal')).not_to_be_visible()
    expect(page.locator('#home')).to_have_class('view active')
    assert page.evaluate("!document.querySelector('#foundationWorkspace').contains(document.activeElement)")
    assert not writes and page.evaluate("api('/foundations')")==before


@pytest.mark.parametrize('width,height,zoom',[(320,640,1),(390,844,1),(844,390,1),(1280,720,2)])
def test_check_black_board_reduced_motion_reflow_and_promotion_access(page,site,width,height,zoom):
    page.set_viewport_size({'width':width,'height':height});page.emulate_media(reduced_motion='reduce')
    start(page,site,'promotion');page.evaluate('z=>document.body.style.zoom=z',zoom)
    square(page,'foundationBoard','a7').click();square(page,'foundationBoard','a8').click()
    modal=page.locator('#cmaPromotionModal');expect(modal).to_be_visible()
    for button in modal.get_by_role('button').all():
        button.scroll_into_view_if_needed();box=button.bounding_box()
        assert box['x']>=0 and box['x']+box['width']<=width+1
        assert page.evaluate('(b)=>{const r=b.getBoundingClientRect();return b.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));}',button.element_handle())
    page.keyboard.press('Escape')
    page.evaluate("cmaNavigation.go('learn/basics')");page.locator('#foundation-open-mate-stalemate').click()
    square(page,'foundationBoard','g6').click();square(page,'foundationBoard','g7').click()
    expect(page.locator('#foundationVisualLegend')).to_contain_text('체크메이트')
    expect(page.locator('#foundationBoard .foundation-check')).to_contain_text('체크')
    page.get_by_role('button',name='다음 단계',exact=True).click()
    # The actual black-side position has a check label but no answer / guide arrow.
    expect(page.locator('#foundationTurn')).to_contain_text('흑 차례')
    assert page.locator('#foundationBoard .sq').first.get_attribute('aria-label').startswith('h1 ')
    assert page.locator('#foundationBoard svg line').count()==0
    page.get_by_role('button',name='체크메이트',exact=True).click()
    page.get_by_role('button',name='다음 단계',exact=True).click()
    expect(page.locator('#foundationBoard .foundation-check')).to_have_count(0)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    assert page.locator('#foundationBoard').bounding_box()['width']>=240
    out=Path('/tmp/cma-foundation-feedback-captures');out.mkdir(exist_ok=True)
    page.screenshot(path=str(out/f'black-{width}-{zoom}.png'),full_page=True)
