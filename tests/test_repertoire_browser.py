"""Local Chromium with real temporary API accounts; injected errors explicitly marked."""
import secrets
import json
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page,open_page
from repertoire_content import lesson

OUT=Path('docs/qa-repertoire')

def enter(page,site):
    open_page(page,site)
    page.evaluate("async code=>{const r=await api('/register','POST',{code,pin:'local-repertoire-pin'});token=r.token;localStorage.setItem('chess_token',token);tab('opening');}",'REP-'+secrets.token_hex(5))
    page.get_by_role('button',name='레퍼토리 선택·이어하기',exact=True).click()
    expect(page.locator('#repertoire')).to_have_attribute('aria-busy','false')

def select_start(page,mode='recall',side='white'):
    page.locator('#repertoire input[value="london-core"]').check()
    page.get_by_role('button',name='선택 저장',exact=True).click()
    expect(page.locator('#repertoire')).to_have_attribute('aria-busy','false')
    page.get_by_role('combobox',name='레퍼토리 연습 색').select_option(side)
    page.get_by_role('button',name='답 가리고 복습 시작' if mode=='recall' else '해설 보며 학습 시작',exact=True).click()
    expect(page.locator('#repertoireBoard .sq')).to_have_count(64)
    expect(page.locator('#repertoire')).to_have_attribute('aria-busy','false')

def move(page,u):
    page.locator(f'#repertoireBoard [aria-label^="{u[:2]} "]').click()
    page.locator(f'#repertoireBoard [aria-label^="{u[2:4]} "]').click()
    expect(page.locator('#repertoire')).to_have_attribute('aria-busy','false')

@pytest.mark.parametrize('width',[390,1280])
def test_actual_recall_no_answers_hint_deviation_resume_completion(page,site,width):
    page.set_viewport_size({'width':width,'height':950});enter(page,site)
    before=page.evaluate("api('/study/openings')")['saved']
    select_start(page)
    expect(page.locator('#openingStudy')).not_to_be_visible()
    expect(page.get_by_role('button',name='d4 · 등록 예시 수',exact=True)).not_to_be_visible()
    assert 'Bf4' not in page.locator('#repertoireBody').inner_text()
    move(page,'e2e4');expect(page.locator('#repertoireBody')).to_contain_text('우열은 판정하지 않습니다')
    page.get_by_role('button',name='현재 수·설명 힌트 (도움 기록)',exact=True).click()
    expect(page.get_by_role('button',name='d4 · 등록 예시 수',exact=True)).to_be_visible()
    page.get_by_role('button',name='처음부터 다시 연습 (이력 유지)',exact=True).click()
    expect(page.locator('#repertoireBody')).to_contain_text('누적 도움 1 · 이탈 1')
    expect(page.get_by_role('button',name='d4 · 등록 예시 수',exact=True)).not_to_be_visible()
    move(page,'d2d4')
    saved=page.evaluate("api('/repertoire')")
    page.add_init_script('localStorage.setItem("chess_token",'+json.dumps(page.evaluate('token'))+');')
    page.reload();page.evaluate("tab('opening')")
    page.get_by_role('button',name='레퍼토리 선택·이어하기',exact=True).click()
    expect(page.locator('#repertoireBody')).to_contain_text('진행 2반수')
    assert page.evaluate("api('/repertoire')")['active']['id']==saved['active']['id']
    line=lesson('london-core')['branches']['bishop-exchange']
    for i in range(2,len(line),2):move(page,line[i])
    expect(page.locator('#repertoireBody')).to_contain_text('레퍼토리 예시를 재현했습니다')
    assert page.evaluate("api('/study/openings')")['saved']==before
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    OUT.mkdir(exist_ok=True,parents=True);page.locator('#repertoire').screenshot(path=str(OUT/f'result-{width}.png'))


def test_black_learning_and_weak_position(page,site):
    enter(page,site);select_start(page,'learn','black')
    expect(page.locator('#repertoireBody')).to_contain_text('흑 수 재현 · 진행 1반수')
    expect(page.get_by_role('button',name='d5 · 등록 예시 수',exact=True)).to_be_visible()
    assert page.locator('#repertoireBoard .sq').first.get_attribute('aria-label').startswith('h1 ')
    move(page,'d7d5')
    page.get_by_role('button',name='현재 수·설명 힌트 (도움 기록)',exact=True).click()
    expect(page.locator('#repertoire')).to_have_attribute('aria-busy','false')
    page.get_by_role('button',name='도움·이탈 위치부터 다시 연습',exact=True).click()
    expect(page.locator('#repertoireBody')).to_contain_text('진행 3반수')
    state=page.evaluate("api('/repertoire')");assert state['active']['start_ply']==3
    OUT.mkdir(exist_ok=True,parents=True);page.locator('#repertoire').screenshot(path=str(OUT/'learn-black.png'))


def test_save_failure_refresh_and_old_account_response(page,site):
    enter(page,site);select_start(page)
    original=page.evaluate("api('/repertoire')")
    page.route('**/api/repertoire/action',lambda r:r.fulfill(status=503,json={'detail':'검사 저장 실패'}))
    move(page,'d2d4');expect(page.locator('#repertoireStatus')).to_contain_text('검사 저장 실패')
    assert page.evaluate("api('/repertoire')")['active']['moves']==[]
    expect(page.get_by_role('button',name='현재 수·설명 힌트 (도움 기록)',exact=True)).to_be_disabled()
    page.unroute('**/api/repertoire/action')
    page.locator('#repertoire').get_by_role('button',name='저장 상태 다시 확인',exact=True).click()
    expect(page.get_by_role('button',name='현재 수·설명 힌트 (도움 기록)',exact=True)).to_be_enabled()
    page.evaluate("""()=>{const old=api;window.ownerA=token;api=(path,...args)=>path==='/repertoire'&&token===ownerA?new Promise(r=>window.releaseRepertoire=r):old(path,...args);} """)
    page.locator('#repertoire').get_by_role('button',name='저장 상태 다시 확인',exact=True).click()
    page.evaluate("async code=>{const r=await api('/register','POST',{code,pin:'local-repertoire-pin'});token=r.token;tab('opening');}",'REP-B-'+secrets.token_hex(4))
    expect(page.locator('#repertoire input')).to_have_count(55)
    page.evaluate('old=>window.releaseRepertoire(old)',original)
    expect(page.locator('#repertoireBoard')).to_have_count(0)
    assert page.evaluate("api('/repertoire')")['active'] is None


def test_help_and_promotion_cancel_do_not_submit_or_mark_hint(page,site):
    enter(page,site);select_start(page)
    saved=page.evaluate("api('/repertoire')")
    page.locator('#opening .feature-toolbar button').click()
    page.keyboard.press('Escape')
    assert page.evaluate("api('/repertoire')")==saved
    # Synthetic promotion boundary: curated opening lessons do not contain promotion.
    import copy
    promotion=copy.deepcopy(saved);r=promotion['active']
    r.update(fen='7k/P7/8/8/8/8/8/7K w - - 0 1',legal=['a7a8q','a7a8r','a7a8b','a7a8n'])
    page.route('**/api/repertoire',lambda route:route.fulfill(json=promotion))
    posts=[]
    page.on('request',lambda req:posts.append(req.post_data_json) if req.url.endswith('/api/repertoire/action') else None)
    page.locator('#repertoire').get_by_role('button',name='저장 상태 다시 확인',exact=True).click()
    expect(page.locator('#repertoire')).to_have_attribute('aria-busy','false')
    page.locator('#repertoireBoard [aria-label^="a7 "]').click();page.locator('#repertoireBoard [aria-label^="a8 "]').click()
    expect(page.locator('.cma-promotion-modal')).to_be_visible()
    page.keyboard.press('Escape')
    expect(page.locator('.cma-promotion-modal')).not_to_be_visible()
    assert posts==[]
    page.unroute('**/api/repertoire')
    assert page.evaluate("api('/repertoire')")==saved


def test_pending_saved_move_navigation_recovers_authoritative_state(page,site):
    enter(page,site);select_start(page)
    page.evaluate("""()=>{const original=api;api=async(path,...args)=>{const value=await original(path,...args);if(path==='/repertoire/action')return new Promise(resolve=>{window.releaseSavedMove=()=>resolve(value);});return value;};}""")
    page.locator('#repertoireBoard [aria-label^="d2 "]').click();page.locator('#repertoireBoard [aria-label^="d4 "]').click()
    page.wait_for_function('typeof window.releaseSavedMove === "function"')
    page.evaluate("tab('home');tab('opening')")
    expect(page.locator('#repertoireBody')).to_contain_text('진행 2반수')
    page.evaluate('window.releaseSavedMove()')
    expect(page.locator('#repertoireBody')).to_contain_text('진행 2반수')
    assert page.evaluate("api('/repertoire')")['active']['moves']==['d2d4','d7d5']
