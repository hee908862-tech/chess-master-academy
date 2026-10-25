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
    if not page.locator('#repertoire').get_by_role('button',name='저장 상태 다시 확인',exact=True).is_visible():page.locator('#repertoireFocusScope > summary').click()
    page.locator('#repertoire').get_by_role('button',name='저장 상태 다시 확인',exact=True).click()
    expect(page.get_by_role('button',name='현재 수·설명 힌트 (도움 기록)',exact=True)).to_be_enabled()
    page.evaluate("""()=>{const old=api;window.ownerA=token;api=(path,...args)=>path==='/repertoire'&&token===ownerA?new Promise(r=>window.releaseRepertoire=r):old(path,...args);} """)
    if not page.locator('#repertoire').get_by_role('button',name='저장 상태 다시 확인',exact=True).is_visible():page.locator('#repertoireFocusScope > summary').click()
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
    if not page.locator('#repertoire').get_by_role('button',name='저장 상태 다시 확인',exact=True).is_visible():page.locator('#repertoireFocusScope > summary').click()
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


def test_integrated_first_recall_color_and_unknown_display(page,site):
    enter(page,site)
    # Use the actual account API to complete white, then begin black.
    data=page.evaluate("api('/repertoire')")
    def action(name,**extra):
        nonlocal data
        data=page.evaluate("body=>api('/repertoire/action','POST',body)",{'action':name,'revision':data['revision'],'attempt_id':(data.get('active') or {}).get('id'),**extra})
    action('select',selected=['london-core']);action('start',lesson_id='london-core',mode='recall',side='white')
    line=lesson('london-core')['branches']['main']
    while data['active']['phase']=='playing':action('move',move=line[len(data['active']['moves'])])
    action('finish');action('start',lesson_id='london-core',mode='recall',side='black')
    if not page.locator('#repertoire').get_by_role('button',name='저장 상태 다시 확인',exact=True).is_visible():page.locator('#repertoireFocusScope > summary').click()
    page.locator('#repertoire').get_by_role('button',name='저장 상태 다시 확인',exact=True).click()
    expect(page.locator('#repertoireBody')).to_contain_text('흑 수 재현')
    expect(page.locator('#repertoireBody')).to_contain_text('레슨 통합 첫 복습 · 백')
    expect(page.locator('#repertoireBody')).to_contain_text('백·흑 통합 누적')
    expect(page.locator('#repertoire')).to_contain_text('백 차례 핵심 위치')
    expect(page.locator('#repertoire')).to_contain_text('동일한 심화 해설을 제공하지 않습니다')
    legacy=__import__('copy').deepcopy(data);legacy['metrics']['london-core']['first_recall'].pop('side')
    page.route('**/api/repertoire',lambda route:route.fulfill(json=legacy))
    if not page.locator('#repertoire').get_by_role('button',name='저장 상태 다시 확인',exact=True).is_visible():page.locator('#repertoireFocusScope > summary').click()
    page.locator('#repertoire').get_by_role('button',name='저장 상태 다시 확인',exact=True).click()
    expect(page.locator('#repertoireBody')).to_contain_text('색 미기록 (이전 결과)')
    OUT.mkdir(exist_ok=True,parents=True);page.locator('#repertoire').screenshot(path=str(OUT/'review-color-unknown.png'))
    page.unroute('**/api/repertoire')
    assert page.evaluate("api('/repertoire')")['metrics']['london-core']['first_recall']['side']=='white'


@pytest.mark.parametrize('operation',['finish','hint'])
@pytest.mark.parametrize('switch_account',[False,True])
def test_chained_action_stale_completion_cannot_start_or_close(page,site,operation,switch_account):
    enter(page,site);select_start(page,'learn' if operation=='finish' else 'recall')
    if operation=='finish':
        for u in lesson('london-core')['branches']['main'][::2]:
            page.evaluate("async u=>{const s=await api('/repertoire');return api('/repertoire/action','POST',{action:'move',move:u,revision:s.revision,attempt_id:s.active.id});}",u)
        if not page.locator('#repertoire').get_by_role('button',name='저장 상태 다시 확인',exact=True).is_visible():page.locator('#repertoireFocusScope > summary').click()
        page.locator('#repertoire').get_by_role('button',name='저장 상태 다시 확인',exact=True).click()
        expect(page.get_by_role('button',name='같은 레슨 답 가리고 복습',exact=True)).to_be_enabled()
    owner_a=page.evaluate('token')
    if switch_account:
        owner_b=page.evaluate("async code=>{const r=await api('/register','POST',{code,pin:'local-repertoire-pin'});const previous=token;token=r.token;const s=await api('/repertoire');await api('/repertoire/action','POST',{action:'select',revision:s.revision,selected:['london-core']});token=previous;return r.token;}",'CHAIN-B-'+secrets.token_hex(4))
    page.evaluate("""kind=>{const original=api;window.chainedStarts=0;api=async(path,...args)=>{if(path==='/repertoire/action'&&args[1]?.action==='start')window.chainedStarts++;const value=await original(path,...args);if(path==='/repertoire/action'&&args[1]?.action===kind)return new Promise(resolve=>window.releaseChain=()=>resolve(value));return value;};}""",operation)
    page.get_by_role('button',name='같은 레슨 답 가리고 복습' if operation=='finish' else '기존 탐색 보기 (복습 도움 기록)',exact=True).click()
    page.wait_for_function('typeof window.releaseChain === "function"')
    if switch_account:
        page.evaluate("identity=>{token=identity;tab('opening');}",owner_b)
        expect(page.locator('#repertoire')).to_have_attribute('aria-busy','false')
        expect(page.get_by_role('button',name='답 가리고 복습 시작',exact=True)).to_be_visible()
    else:page.evaluate("tab('home')")
    page.evaluate('window.releaseChain()')
    assert page.evaluate('window.chainedStarts')==0
    if not switch_account:
        expect(page.locator('#home')).to_contain_class('view active');page.evaluate("tab('opening')")
    expect(page.locator('#repertoireBody')).to_be_visible()
    if switch_account or operation=='finish':assert page.evaluate("api('/repertoire')")['active'] is None
    else:assert page.evaluate("api('/repertoire')")['active']['hints']==1


def test_capacity_ui_finish_lost_response_reconnect_and_exploration(page,site):
    enter(page,site);select_start(page)
    # Boundary display is controlled; server boundary persistence has a 24-case matrix.
    def limited(route):
        value=route.fetch().json();value.update(can_start=False,capacity_notice='정규 보관64개 한도입니다. 현재 시도의 종료와 기록 조회·강의 탐색은 가능합니다.')
        route.fulfill(json=value)
    page.route('**/api/repertoire',limited)
    if not page.locator('#repertoire').get_by_role('button',name='저장 상태 다시 확인',exact=True).is_visible():page.locator('#repertoireFocusScope > summary').click()
    page.locator('#repertoire').get_by_role('button',name='저장 상태 다시 확인',exact=True).click()
    expect(page.get_by_role('button',name='처음부터 다시 연습 (이력 유지)',exact=True)).to_be_disabled()
    expect(page.get_by_role('button',name='이 시도 기록하고 마치기',exact=True)).to_be_enabled()
    def lost(route):
        response=route.fetch();assert response.status==200
        route.fulfill(status=503,json={'detail':'종료 저장 후 응답 유실 검사'})
    page.route('**/api/repertoire/action',lost)
    page.get_by_role('button',name='이 시도 기록하고 마치기',exact=True).click()
    expect(page.locator('#repertoireStatus')).to_contain_text('응답 유실 검사')
    expect(page.get_by_role('button',name='홈으로 돌아가기',exact=True)).to_be_enabled()
    page.unroute('**/api/repertoire/action')
    if not page.locator('#repertoire').get_by_role('button',name='저장 상태 다시 확인',exact=True).is_visible():page.locator('#repertoireFocusScope > summary').click()
    page.locator('#repertoire').get_by_role('button',name='저장 상태 다시 확인',exact=True).click()
    expect(page.get_by_role('button',name='답 가리고 복습 시작',exact=True)).to_be_disabled()
    expect(page.locator('#repertoireBoard')).to_have_count(0)
    expect(page.get_by_role('button',name='기존 강의 탐색·북마크 보기',exact=True)).to_be_enabled()
    OUT.mkdir(exist_ok=True,parents=True);page.locator('#repertoire').screenshot(path=str(OUT/'review-capacity.png'))
    page.get_by_role('button',name='기존 강의 탐색·북마크 보기',exact=True).click()
    expect(page.locator('#openingStudy')).to_be_visible()
