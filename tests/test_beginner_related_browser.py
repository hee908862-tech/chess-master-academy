"""Existing 26 exercises remain operable with visible teaching, local Chromium/API."""
import re
import pytest
from playwright.sync_api import expect
from foundation_content import COURSES
from test_redesign_browser_followup import isolated,site


@pytest.mark.parametrize('width,height',[(1366,540),(390,844)])
def test_all_existing_lessons_show_rule_before_action_and_keep_controls(isolated,site,width,height):
    page,_=isolated;page.set_viewport_size({'width':width,'height':height})
    open_legacy_intro(page)
    page.wait_for_function('!!cmaFoundations.state()?.active && !cmaFoundations.status().busy')
    for course in COURSES:
        page.evaluate("cmaNavigation.go('learn/basics')")
        page.get_by_role('button',name='이미 알고 있어요 · 원하는 과정 고르기',exact=True).click()
        page.locator('#foundation-open-'+course['id']).click()
        page.wait_for_function('!cmaFoundations.status().busy')
        for index,step in enumerate(course['steps']):
            expect(page.locator('#foundationRule')).to_be_visible()
            expect(page.locator('#foundationPieceName')).not_to_be_empty()
            assert not page.locator('#foundationTeaching').evaluate("e=>!!e.closest('details:not([open])')")
            if course['id']=='en-passant' and index==0:expect(page.locator('#foundationDemoStart')).to_be_visible()
            if step['kind']=='judge':page.locator('#foundationAnswers').get_by_role('button',name={'mate':'체크메이트','stalemate':'스테일메이트','no_castle':'킹사이드 캐슬링(O-O) 불가','no_ep':'앙파상 불가'}[step['answer']],exact=True).click()
            else:
                for move in step['line'][::2]:
                    page.locator(f'#foundationBoard [aria-label^="{move[:2]} "]').click()
                    page.locator(f'#foundationBoard [aria-label^="{move[2:4]} "]').click()
                    if len(move)==5:page.locator('#cmaPromotionModal').get_by_role('button',name=re.compile({'q':'퀸','n':'나이트'}[move[4]]+'$')).click()
                    page.wait_for_function('!cmaFoundations.status().busy')
            page.wait_for_function('!cmaFoundations.status().busy && cmaFoundations.state().active.solved')
            expect(page.locator('#foundationFeedback')).to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            if index+1<len(course['steps']):
                page.locator('#foundationNext').get_by_role('button',name='다음 단계',exact=True).click()
                page.wait_for_function('!cmaFoundations.status().busy')
    state=page.evaluate("api('/foundations')")
    assert state['completed']==10 and not state['introduction']['done']


def open_legacy_intro(page):
    # Explicit guest creation, then opt into preserved PR48.
    page.locator('#flowBasicsStart').click()
    page.wait_for_function('!!cmaMovement.state().unit && !cmaMovement.state().loading')
    page.evaluate("cmaNavigation.go('learn/basics')")
    page.wait_for_function('!!cmaFoundations.state() && !cmaFoundations.status().busy')
    page.locator('#foundation-recommended-action').click()


def test_intro_demo_uses_one_common_move_sound_per_playback(isolated,site):
    page,_=isolated;open_legacy_intro(page)
    page.wait_for_function('!!cmaFoundations.state()?.active && !cmaFoundations.status().busy')
    page.evaluate("window.introSounds=[];playMoveSound=(kind,ctx)=>{if(ctx?.board==='foundationBoard')introSounds.push(kind)}")
    page.locator('#foundationBoard [aria-label^="a1 "]').click()
    page.wait_for_function('!cmaFoundations.status().busy')
    assert page.evaluate('introSounds.length')==0
    page.locator('#foundationNext').get_by_role('button',name='다음 단계',exact=True).click()
    expect(page.locator('#foundationObserve')).to_be_enabled()
    assert page.evaluate('introSounds.length')==1
    page.get_by_role('button',name='움직임 다시 보기',exact=True).click()
    expect(page.locator('#foundationObserve')).to_be_enabled()
    assert page.evaluate('introSounds.length')==2
