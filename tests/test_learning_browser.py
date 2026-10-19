"""Local real API + Chromium, never production or physical-device QA."""
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page,open_page,square
from v9_server import LIB

@pytest.mark.parametrize('width,height',[(1440,1000),(390,844),(844,390),(768,1024)])
def test_learning_responsive_real_persistence(page,site,width,height):
    page.set_viewport_size({'width':width,'height':height})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    open_page(page,site)
    page.evaluate("tab('training')")
    page.locator('#learningFresh').click()
    expect(page.locator('#learningMode')).to_have_text('연습')
    expect(page.locator('#learningBoard .sq')).to_have_count(64)
    page.get_by_role('button',name='힌트 1단계',exact=True).click()
    expect(page.get_by_role('button',name='힌트 2단계',exact=True)).to_be_visible()
    data=page.evaluate("api('/learning/dashboard')")
    active=data['active'];move=LIB[active['card_id'].removeprefix('puzzle-')]['moves'][1]
    square(page,'learningBoard',move[:2]).click()
    square(page,'learningBoard',move[2:4]).click()
    if len(move)==5:
        page.locator('#cmaPromotionModal').get_by_role('button',name={'q':'퀸','r':'룩','b':'비숍','n':'나이트'}[move[4]]).click()
    expect(page.locator('#learningMode')).to_have_text('연습 완료')
    expect(page.locator('#learningControls')).to_contain_text('도움 사용 후 성공')
    assert page.locator('#learningBoard button:enabled').count()==0
    page.reload();page.evaluate("tab('training')")
    expect(page.locator('#learningMode')).to_have_text('연습 완료')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    if width<=1100:
        expect(page.locator('.mobile-nav')).to_be_hidden()
        expect(page.locator('.learning-mobile-nav')).to_be_visible()
    page.screenshot(path=f'/tmp/learning-{width}x{height}.png',full_page=True)
    page.locator('#learningVerify').click()
    expect(page.locator('#learningTitle')).to_have_text('주제 비공개 · 독립 판단')
    assert page.get_by_role('button',name='힌트 1단계',exact=True).count()==0
    page.evaluate("tab('home')")
    expect(page.locator('#learningPath button')).to_have_count(4)
    assert not errors,errors
