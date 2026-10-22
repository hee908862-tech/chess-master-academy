"""Real Chromium and real local APIs; temporary accounts only."""
import json
import secrets
import urllib.request
import pytest
from playwright.sync_api import sync_playwright, expect
from test_qa_browser import site

def load_review(page):
    if not page.locator('#reviewSelection').evaluate('(e)=>e.open'):
        page.locator('#reviewSelection > summary').click()
    page.locator('#reviewLoad').click()


@pytest.mark.parametrize('width,height',[(1440,1000),(390,844)])
def test_hint_undo_review_and_reload(site,width,height):
    code='HELP-'+secrets.token_hex(4)
    req=urllib.request.Request(site[0]+'/api/register',json.dumps({'code':code,'pin':'qa-help-pin42'}).encode(),{'Content-Type':'application/json'})
    account=json.load(urllib.request.urlopen(req))
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':width,'height':height})
        page.add_init_script(f"localStorage.setItem('chess_token',{json.dumps(account['token'])});")
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(site[0]);page.wait_for_timeout(600)
        page.evaluate("api('/game/new','POST',{color:'white',difficulty:1})")
        page.evaluate("tab('play');resumeGame()")
        page.locator('#v7Hint').click()
        expect(page.locator('#gameStatus')).to_contain_text('추천:')
        # The real API gives the exact hint, independent of heuristic engine choices.
        hint=page.evaluate("api('/v7/game/hint')")['move']
        def play(u):return page.evaluate("u=>api('/game/move','POST',{from_sq:u.slice(0,2),to_sq:u.slice(2,4),promotion:u.slice(4)||'q'})",u)
        play(hint)
        page.evaluate('resumeGame()')
        page.locator('#v7Undo').click()
        expect(page.locator('#gameStatus')).to_contain_text('되돌렸습니다')
        page.reload();page.evaluate("tab('play');resumeGame()")
        play(hint)
        page.evaluate("api('/game/resign','POST')")
        page.evaluate("tab('review')")
        expect(page.locator('#reviewGameSelect')).to_have_value('0')
        load_review(page)
        first=page.locator('.review-move').first
        expect(first).to_contain_text('힌트 채택')
        expect(first).to_contain_text('무르기 후 재착수')
        first.click()
        expect(page.locator('#reviewStatus')).to_contain_text('힌트 채택 · 무르기 후 재착수')
        page.reload();page.evaluate("tab('review')")
        expect(page.locator('#reviewGameSelect')).to_have_value('0')
        load_review(page)
        expect(page.locator('.review-move').first).to_contain_text('무르기 후 재착수')
        page.locator('.review-move').first.click()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=f'/tmp/review-assistance-{width}.png',full_page=True)
        assert not errors,errors
        browser.close()


def test_different_move_and_legacy_labels(site):
    from test_qa_browser import START
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page();page.add_init_script(f"localStorage.setItem('chess_token',{json.dumps(site[1])});")
        page.route('**/api/games/history',lambda r:r.fulfill(json=[{'index':0,'color':'white','plies':1,'result':'loss'}]))
        row={'ply':1,'side':'백','uci':'d2d4','san':'d4','before_fen':START,'after_fen':START,'category':'미평가','centipawn_loss':0,'comment':'fixture','source':'fixture','assistance':{'known':True,'hint_viewed':True,'hint_adopted':False,'undo_replayed':False}}
        data={'color':'white','moves':[row],'hint_plies':[1]}
        page.route('**/api/games/review/0',lambda r:r.fulfill(json=data))
        page.goto(site[0]);page.evaluate("tab('review')");load_review(page)
        expect(page.locator('.review-move').first).to_contain_text('힌트 제공 · 다른 수')
        assert page.locator('.review-move.undo-assisted').count()==0
        row.pop('assistance')
        expect(page.locator('#reviewGameSelect')).to_have_value('0')
        load_review(page)
        expect(page.locator('.review-move').first).to_contain_text('도움 기록 없음')
        assert page.locator('.review-move.hint-assisted').count()==0
        page.locator('.review-move').first.click()
        expect(page.locator('#reviewStatus')).to_contain_text('도움 기록 없음')
        browser.close()
