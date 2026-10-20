"""Chromium QA against isolated real APIs; no production account mutation."""
from pathlib import Path
from playwright.sync_api import expect
from test_qa_browser import site,page,square
from test_study_browser import login


def test_reference_save_reset_and_mobile_more(page,site):
    login(page,site);page.set_viewport_size({'width':400,'height':860})
    page.locator('.mobile-nav').get_by_role('button',name='더보기',exact=True).click()
    expect(page.locator('#moreNavigationDialog')).to_be_visible()
    page.locator('#moreNavigationDialog').get_by_role('button',name='오프닝 연구실',exact=True).click()
    expect(page.locator('#studyOpeningBoard .sq')).to_have_count(64)
    # Real reference catalog search, not a fabricated no-op result.
    page.locator('.study-references summary').click()
    page.get_by_label('참고 오프닝 검색',exact=True).fill('Italian')
    page.get_by_role('button',name='참고 수순 검색',exact=True).click()
    page.locator('.study-references > div button').first.click()
    expect(page.locator('#studyContext')).to_contain_text('CC0 참고 수순')
    expect(page.get_by_role('button',name='학습 위치 저장',exact=True)).to_be_disabled()
    expect(page.locator('#studySaveStatus')).to_contain_text('지원하지 않습니다')
    page.locator('#opening').get_by_role('button',name='분기 초기화',exact=True).click()
    expect(page.locator('#studyContext')).to_contain_text('CC0 참고 수순')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    Path('/tmp/cma-audit-images').mkdir(exist_ok=True)
    page.screenshot(path='/tmp/cma-audit-images/reference-mobile.png',full_page=True)
    page.get_by_role('button',name='해설 강의로 돌아가기',exact=True).click()
    expect(page.locator('#studyContext')).to_contain_text('해설 강의')


def test_rules_level_board_completion_and_reload(page,site):
    login(page,site);page.set_viewport_size({'width':400,'height':860})
    page.evaluate('cmaStartingLevel.open()')
    dialog=page.locator('#startingLevelDialog');expect(dialog).to_be_visible()
    dialog.get_by_role('button',name='룰부터 배우기',exact=True).click()
    expect(page.locator('#learn')).to_have_class('view active')
    page.evaluate('cmaStartingLevel.open()')
    expect(page.locator('#ruleTitle')).to_contain_text('1/4')
    for i,(start,end) in enumerate([('a1','a4'),('a1','a4'),('a1','a8'),('g1','f2')]):
        square(page,'ruleBoard',start).click();square(page,'ruleBoard',end).click()
        if i<3:expect(page.locator('#ruleTitle')).to_contain_text(f'{i+2}/4')
    expect(page.locator('#startingDiagnosis')).to_be_visible()
    page.locator('#startingDiagnosis').click()
    expect(dialog).not_to_be_visible()
    page.locator('#journeyStart').click()
    expect(page.locator('#journeyBoard .sq:enabled')).to_have_count(64)
    active=page.evaluate("api('/journey')")['active']
    assert active['version']=='journey-entry-v1' and active['total']<=6
    assert active['starting_conditions']['self_choice']=='rules'
    page.reload();page.evaluate("tab('diagnosis')")
    expect(page.locator('#journeyBoard .sq:enabled')).to_have_count(64)
    assert page.evaluate("api('/journey')")['active']['session_id']==active['session_id']
    expect(page.locator('#startingLevelDialog')).not_to_be_visible()
    Path('/tmp/cma-audit-images').mkdir(exist_ok=True)
    page.screenshot(path='/tmp/cma-audit-images/entry-mobile.png',full_page=True)


def test_more_keyboard_focus_and_disabled_no_game_actions(page,site):
    login(page,site);page.set_viewport_size({'width':400,'height':860})
    more=page.locator('.mobile-nav').get_by_role('button',name='더보기',exact=True)
    more.focus();page.keyboard.press('Enter')
    dialog=page.locator('#moreNavigationDialog');expect(dialog).to_be_visible()
    for _ in range(10):
        page.keyboard.press('Tab')
        assert page.evaluate("document.getElementById('moreNavigationDialog').contains(document.activeElement)")
    page.keyboard.press('Escape');expect(dialog).not_to_be_visible();expect(more).to_be_focused()
    page.evaluate("tab('play')")
    for id in ['resign','v7Hint','v7Undo']:
        expect(page.locator('#'+id)).to_be_disabled()
        expect(page.locator('#'+id)).to_have_attribute('aria-describedby','gameActionReason')
    expect(page.locator('#gameActionReason')).to_contain_text('새 대국')
