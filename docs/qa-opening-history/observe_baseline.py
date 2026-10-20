from test_study_browser import login,click_move,site,page
from playwright.sync_api import expect

def test_observe_current_redo(page,site):
    login(page,site);page.evaluate("tab('opening')")
    expect(page.locator('#studyCourse option')).to_have_count(55)
    page.locator('#studyCourse').select_option('london-core')
    expect(page.locator('#studyMessage')).to_contain_text('등록된')
    before=page.locator('#studyOpeningBoard').inner_html()
    page.evaluate("""() => {const original=api;api=(p,...args)=>p==='/study/openings/position'?new Promise(resolve=>window.releaseDescription=()=>original(p,...args).then(resolve)):original(p,...args)}""")
    page.locator('#studyTools').get_by_role('button',name='다음 수',exact=True).click()
    expect(page.locator('#studyMessage')).to_contain_text('양쪽 기물을')
    expect(page.locator('#studyChoices button')).to_have_count(0)
    assert page.locator('#studyOpeningBoard').inner_html()==before
    page.evaluate('releaseDescription()')
    expect(page.locator('#studyMessage')).to_contain_text('등록된')
    expect(page.locator('#studyChoices button').first).to_be_visible()
