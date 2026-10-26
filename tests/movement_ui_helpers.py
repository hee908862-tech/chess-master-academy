"""Visible UI actions shared by movement regression tests."""
from playwright.sync_api import expect


def options(page):
    panel=page.locator('#movementHelp')
    if not panel.evaluate('(e)=>e.open'):panel.locator('summary').click()


def finish_example(page):
    expect(page.locator('#movementExampleDialog')).to_be_visible()
    page.locator('#movementExampleActions button').click()
    expect(page.locator('#movementExampleDialog')).not_to_be_visible()


def independent(page):
    if page.locator('#movementExampleDialog').is_visible():finish_example(page)
    if page.evaluate("cmaMovement.state().unit?.teaching?.phase==='explain'"):
        page.locator('#movementLesson').get_by_role('button',name='연습 시작',exact=True).click()
        page.wait_for_function("cmaMovement.state().unit.teaching.phase==='guided'")
    if page.evaluate("cmaMovement.state().unit?.teaching?.phase==='guided'"):
        options(page)
        page.get_by_role('button',name='따라 하기 건너뛰기',exact=True).click()
        page.wait_for_function("cmaMovement.state().unit.teaching.phase==='independent'")
    page.wait_for_function('!cmaMovement.state().loading && !cmaMovement.state().pending')


def playback(page):
    controls=page.locator('.movement-playback-tools')
    if not controls.evaluate('(e)=>e.open'):controls.locator('summary').click()
