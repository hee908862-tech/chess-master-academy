import json
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page,open_page


@pytest.mark.parametrize('width,height',[(1180,757),(390,844)])
def test_anonymous_discovery_examples_and_opening_no_writes(page,site,width,height):
    page.set_viewport_size({'width':width,'height':height})
    page.add_init_script("localStorage.removeItem('chess_token');localStorage.removeItem('cma_entry_preference_v1')")
    writes=[];page.on('request',lambda r:writes.append(r.url) if r.method not in ('GET','HEAD') else None)
    open_page(page,site)
    shelf=page.locator('#academyTry');expect(shelf).to_be_visible()
    if width==1180:assert shelf.bounding_box()['y']+shelf.bounding_box()['height']<height
    shelf.get_by_role('button',name='나이트 움직이기').click()
    expect(page.locator('#guestActivity')).to_be_visible()
    expect(page.locator('#guestTitle')).to_contain_text('나이트')
    page.locator('#guestHint').click();page.locator('#guestExit').click()
    shelf.get_by_role('button',name='오프닝 이유 보기').click()
    expect(page.locator('#guestOpeningPreview .board .sq')).to_have_count(64)
    frame=page.locator('#guestOpeningPreview .board')
    original=frame.get_attribute('data-fen')
    page.locator('#guestOpeningPreview').get_by_role('button',name='다음 수',exact=True).click()
    assert frame.get_attribute('data-fen')!=original
    page.locator('#guestOpeningPreview').get_by_role('button',name='처음',exact=True).click()
    assert frame.get_attribute('data-fen')==original
    assert writes==[]
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    out=Path('docs/qa-academy-upgrade');out.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(out/f'guest-opening-{width}.png'))


def test_logged_account_form_only_after_explicit_switch_and_cancel(page,site):
    open_page(page,site);page.locator('#loginNav').click()
    expect(page.locator('#connectedAccount')).to_be_visible()
    expect(page.locator('#codeField')).not_to_be_visible()
    expect(page.locator('#signin')).not_to_be_visible()
    before=page.evaluate('token');page.get_by_role('button',name='계정 전환',exact=True).click()
    expect(page.locator('#codeField')).to_be_visible()
    page.locator('#pinField').fill('do-not-keep')
    page.get_by_role('button',name='계정 전환 취소',exact=True).click()
    expect(page.locator('#codeField')).not_to_be_visible()
    assert page.evaluate('token')==before and page.locator('#pinField').input_value()==''
    page.locator('#connectedAccount').screenshot(path='docs/qa-academy-upgrade/account.png')


def test_replay_component_starts_before_answer_and_never_posts(page,site):
    open_page(page,site)
    initial='7k/8/8/3pP3/8/8/8/K7 w - d6 0 12'
    from diagnostic_replay import replay_snapshot
    replay=replay_snapshot({'fen':initial,'line':['e5d6']})
    posts=[];page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
    page.evaluate("data=>{const h=document.createElement('section');h.id='testReplay';document.querySelector('#home').append(h);cmaDiagnosticReplay(h,data).open=true}",replay)
    board=page.locator('#testReplay .board');expect(board).to_have_attribute('data-fen',initial)
    page.locator('#testReplay').get_by_role('button',name='다음 수',exact=True).click()
    expect(board).to_have_attribute('data-fen',replay['frames'][1]['fen'])
    page.locator('#testReplay').get_by_role('button',name='이전 수',exact=True).click()
    expect(board).to_have_attribute('data-fen',initial)
    assert posts==[]


def test_internal_scale_keeps_game_rating_chart_separate(page,site):
    open_page(page,site)
    page.evaluate("""()=>{const host=document.createElement('div');host.id='scoreTest';document.querySelector('#home').append(host);
    growthReport(host,{internal_skill:{label:'내부 실력진단',score:1800,observed:24,unresolved:0,bounds:[1800,1800],note:'기초 40%·응용 60%'},areas:[{id:'mate',performance:{score:1800,scale_min:1,scale_max:3000,observed:4,band_counts:[2,2],comparable:true}}]},null,null,null,null,true);}""")
    expect(page.locator('#scoreTest')).to_contain_text('1800 / 3000')
    assert float(page.locator('#scoreTest .ability-meter>span').evaluate("e=>parseFloat(e.style.width)"))<61


def test_new_education_review_uses_actual_step_count_without_answer_prompt(page,site):
    open_page(page,site);page.evaluate("tab('learn/education')")
    page.locator('#education-start-ending-rook-finish-review').click()
    expect(page.locator('#educationBody')).to_contain_text('관찰 1/6')
    data=page.evaluate("api('/education')")
    assert data['active']['total']==6
    assert 'Kg6' not in data['active']['step']['prompt']
