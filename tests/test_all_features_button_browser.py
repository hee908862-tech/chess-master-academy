"""Small profile-menu presentation regression; disposable local account only."""
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page
from test_study_browser import login

@pytest.mark.parametrize('width,height',[(1280,720),(320,800)])
def test_all_features_button_style_focus_and_existing_dialog(page,site,width,height):
    login(page,site);page.set_viewport_size(dict(width=width,height=height));page.evaluate("tab('profile')")
    writes=[];page.on('request',lambda r:writes.append(r.url) if r.method!='GET' and '/api/' in r.url else None)
    b=page.locator('#moreNavigation')
    expect(b).to_have_text('기능 전체 · 도움말');expect(b).to_have_class('btn')
    b.scroll_into_view_if_needed();box=b.bounding_box()
    assert box['height']>=44 and box['width']>=44
    assert box['x']>=0 and box['x']+box['width']<=width+1
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    page.keyboard.press('Tab');b.focus()
    assert b.evaluate("e=>getComputedStyle(e).outlineStyle")!='none'
    assert b.evaluate("e=>getComputedStyle(e).backgroundColor")=='rgba(255, 255, 255, 0.05)'
    out=Path('/tmp/cma-all-features-evidence');out.mkdir(exist_ok=True)
    page.screenshot(path=str(out/f'button-{width}.png'))
    page.keyboard.press('Enter');expect(page.locator('#moreNavigationDialog')).to_be_visible()
    expect(page.locator('#profile')).to_have_class('view active')
    page.keyboard.press('Escape');expect(b).to_be_focused()
    b.click();page.locator('#moreNavigationDialog').get_by_role('button',name='닫기',exact=True).click()
    expect(b).to_be_focused()
    b.click();page.locator('#moreNavigationDialog').get_by_role('button',name='도움말',exact=True).click()
    expect(page.locator('#help')).to_have_class('view active')
    expect(page.locator('#moreNavigationDialog')).not_to_be_visible()
    assert writes==[]
