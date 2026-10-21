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
    page.on('dialog',lambda d:d.accept())
    open_page(page,site)
    page.evaluate("tab('training')")
    if page.get_by_role('button',name='훈련 선택 · 저장 활동 · 기록',exact=True).is_visible():page.get_by_role('button',name='훈련 선택 · 저장 활동 · 기록',exact=True).click()
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
    if width<=850:
        expect(page.locator('.mobile-nav')).to_be_visible()
        expect(page.locator('.learning-mobile-nav')).to_be_hidden()
    page.screenshot(path=f'/tmp/learning-{width}x{height}.png',full_page=True)
    page.get_by_role('button',name='훈련 선택 · 저장 활동 · 기록',exact=True).click()
    page.locator('#learningVerify').click()
    expect(page.locator('#learningTitle')).to_have_text('주제 비공개 · 독립 판단')
    assert page.get_by_role('button',name='힌트 1단계',exact=True).count()==0
    page.evaluate("tab('home')")
    expect(page.locator('#learningPath button')).to_have_count(4)
    assert not errors,errors

@pytest.fixture
def route_page(site):
    import json, secrets, urllib.request
    from playwright.sync_api import sync_playwright
    request=urllib.request.Request(site[0]+'/api/register',json.dumps({'code':'ROUTE-'+secrets.token_hex(4),'pin':'qa-route-pin-42'}).encode(),{'Content-Type':'application/json'})
    account=json.load(urllib.request.urlopen(request))
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page()
        page.add_init_script(f"localStorage.setItem('chess_token',{json.dumps(account['token'])});")
        yield page
        browser.close()


@pytest.mark.parametrize('width,height',[(1440,1000),(390,844)])
def test_saved_route_review_concept_transfer_resume(route_page,site,width,height):
    page=route_page
    page.set_viewport_size({'width':width,'height':height})
    page.on('dialog',lambda d:d.accept())
    open_page(page,site)
    page.evaluate("api('/learning/start','POST',{fresh:true})")
    page.evaluate("tab('home')")
    expect(page.locator('#learningReason')).to_contain_text('복습할 위치 1개')
    page.locator('#homeExplore > summary').click()
    page.locator('.learning-home > summary').click()
    page.locator('#learningPath button').first.click()
    expect(page.locator('#learningRouteStatus')).to_contain_text('1/4')
    first=page.evaluate("api('/learning/dashboard')")
    source=first['path']['source_card']
    page.reload();page.evaluate("tab('training')")
    expect(page.locator('#learningRouteStatus')).to_contain_text('1/4')
    s=page.evaluate("api('/learning/dashboard')")['active']
    move=LIB[s['card_id'].removeprefix('puzzle-')]['moves'][1]
    square(page,'learningBoard',move[:2]).click();square(page,'learningBoard',move[2:4]).click()
    if len(move)==5:page.locator('#cmaPromotionModal').get_by_role('button',name={'q':'퀸','r':'룩','b':'비숍','n':'나이트'}[move[4]]).click()
    expect(page.locator('#learningMode')).to_have_text('연습 완료')
    page.get_by_role('button',name='경로 다음 단계',exact=True).click()
    expect(page.locator('#learningRouteStatus')).to_contain_text('2/4')
    page.locator('#learningRoute > summary').click()
    page.get_by_role('button',name='개념 읽기 확인',exact=True).click()
    page.get_by_role('button',name='경로 시작 · 이어가기',exact=True).click()
    expect(page.locator('#learningMode')).to_have_text('검증')
    second=page.evaluate("api('/learning/dashboard')")
    assert second['path']['source_card']==source and second['active']['card_id']!=source
    assert source not in [x['id'] for x in second['due']]
    page.reload();page.evaluate("tab('training')")
    expect(page.locator('#learningRouteStatus')).to_contain_text('3/4')
    expect(page.locator('#learningTitle')).to_have_text('주제 비공개 · 독립 판단')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=f'/tmp/learning-route-{width}.png',full_page=True)
