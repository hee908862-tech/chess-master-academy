import json,secrets,urllib.request
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page


def login(page,site):
    req=urllib.request.Request(site[0]+'/api/register',json.dumps({'code':'STUDY-'+secrets.token_hex(4),'pin':'local-study-pin'}).encode(),{'Content-Type':'application/json'})
    token=json.load(urllib.request.urlopen(req))['token'];page.add_init_script(f"localStorage.setItem('chess_token',{json.dumps(token)})")
    page.route('**/api/onboarding',lambda r:r.fulfill(json={'status':'completed','version':1}))
    page.goto(site[0]);return token


def click_move(page,board,uci):
    page.locator(f'#{board} [aria-label^="{uci[:2]} "]').click();page.locator(f'#{board} [aria-label^="{uci[2:4]} "]').click()


@pytest.mark.parametrize('width',[390,1280])
def test_opening_actual_api_branch_recall_save_and_reference(page,site,width):
    page.set_viewport_size({'width':width,'height':950});login(page,site)
    page.evaluate("tab('opening')");expect(page.locator('#studyCourse option')).to_have_count(55)
    page.locator('#studyCourse').select_option('french-advance');expect(page.locator('#studyOpeningBoard .sq')).to_have_count(64)
    for u in ['e2e4','e7e6','d2d4','d7d5','e4e5','c7c5']:
        with page.expect_response(lambda r:r.url.endswith('/study/position')):click_move(page,'studyOpeningBoard',u)
        expect(page.locator('#studyMessage')).to_contain_text('등록된')
    expect(page.locator('#studyExplanation')).to_contain_text('폰 사슬의 밑부분 d4')
    page.evaluate("tab('home');tab('opening')");expect(page.locator('#studyOpeningBoard .sq:enabled')).to_have_count(64)
    expect(page.locator('#studyExplanation')).to_contain_text('폰 사슬의 밑부분 d4')
    page.locator('#studyMode').select_option('recall');expect(page.locator('#studyExplanation')).to_contain_text('해설을 가렸어요')
    expect(page.locator('#studyChoices button')).to_have_count(0)
    page.get_by_role('button',name='학습 위치 저장',exact=True).click();expect(page.locator('#studySaveStatus')).to_contain_text('저장했어요')
    page.reload();page.evaluate("tab('opening')");expect(page.locator('#studyCourse option')).to_have_count(55)
    page.get_by_role('button',name='저장 위치 이어하기',exact=True).click();expect(page.locator('#studyMode')).to_have_value('recall');expect(page.locator('#studyOpeningBoard .sq')).to_have_count(64)
    page.locator('#studyMode').select_option('explore');expect(page.locator('#studyExplanation')).to_contain_text('폰 사슬')
    # Unknown legal move is playable and not marked a tactical error.
    page.get_by_role('button',name='처음부터 두기',exact=True).click();expect(page.locator('#studyMessage')).to_contain_text('등록된')
    click_move(page,'studyOpeningBoard','a2a3');expect(page.locator('#studyMessage')).to_contain_text('아직 해설이 없는 수')
    page.locator('#openingStudy').get_by_role('button',name='이전 수',exact=True).click();expect(page.locator('#studyMessage')).to_contain_text('등록된')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    out=Path('docs/qa-interactive');out.mkdir(exist_ok=True);page.screenshot(path=str(out/f'opening-{width}.png'),full_page=True)
    page.get_by_text('CC0 참고 수순 검색 · 강의 해설과 별도',exact=True).click()
    page.get_by_role('textbox',name='참고 오프닝 검색').fill('French Defense: Advance')
    page.get_by_role('button',name='참고 수순 검색',exact=True).click();expect(page.locator('.study-references')).to_contain_text('강의 해설 없음')


def test_review_branch_actual_rules_and_late_engine_cancel(page,site):
    login(page,site)
    # Controlled original game, real branch legality API. Stored game is never written.
    page.route('**/api/games/history',lambda r:r.fulfill(json=[{'index':0,'color':'black','plies':2,'result':'loss'}]))
    import chess
    b=chess.Board();rows=[]
    for u in ['e2e4','e7e5']:
        san=b.san(chess.Move.from_uci(u));b.push_uci(u);rows.append({'uci':u,'san':san,'side':'백' if len(rows)==0 else '흑','after_fen':b.fen(),'centipawn_loss':0,'category':'참고','comment':'원본'})
    original={'color':'black','moves':rows}
    page.route('**/api/games/review/0',lambda r:r.fulfill(json=original))
    page.evaluate("tab('review')");expect(page.locator('#reviewLoad')).to_be_enabled();page.locator('#reviewLoad').click();expect(page.locator('#reviewStep')).to_contain_text('0 / 2')
    before=page.evaluate("api('/me')")
    page.get_by_role('button',name='여기부터 다시 두기',exact=True).click();expect(page.locator('#reviewBranchStatus')).to_contain_text('양쪽')
    click_move(page,'reviewBoard','d2d4');expect(page.locator('#reviewStep')).to_contain_text('분기 1')
    assert page.locator('#reviewBoard .sq').first.get_attribute('aria-label').startswith('h1 ')
    page.get_by_role('button',name='분기 이전',exact=True).click();expect(page.locator('#reviewStep')).to_contain_text('분기 0')
    page.get_by_role('button',name='분기 다음',exact=True).click();expect(page.locator('#reviewStep')).to_contain_text('분기 1')
    # A failed move must roll back the local path as well as the visible board.
    page.evaluate("""() => {const previous=api;window.failStudyOnce=true;api=function(p,...a){if(p==='/study/position'&&window.failStudyOnce){window.failStudyOnce=false;return Promise.reject(Error('테스트 연결 실패'));}return previous(p,...a);};}""")
    click_move(page,'reviewBoard','e7e5');expect(page.locator('#reviewBranchStatus')).to_contain_text('확인된 위치')
    expect(page.locator('#reviewStep')).to_contain_text('분기 1')
    page.get_by_role('button',name='분기 이전',exact=True).click();expect(page.locator('#reviewStep')).to_contain_text('분기 0')
    page.get_by_role('button',name='분기 다음',exact=True).click();expect(page.locator('#reviewStep')).to_contain_text('분기 1 / 1')
    # Hold an actual frontend promise so a late response can arrive after returning to original.
    page.evaluate("""() => {window.studyApi=api;api=function(path,method,body){if(path==='/study/position'&&body.engine)return new Promise(resolve=>window.releaseStudy=resolve);return window.studyApi(path,method,body);};}""")
    page.get_by_role('button',name='현재 차례 엔진 응수',exact=True).click();expect(page.locator('#reviewBranchStatus')).to_contain_text('계산 중')
    page.get_by_role('button',name='원본으로 돌아가기',exact=True).click();expect(page.locator('#reviewStep')).to_contain_text('0 / 2')
    page.evaluate('d=>window.releaseStudy(d)',{'fen':b.fen(),'legal':[],'reply':'e7e5'})
    page.wait_for_timeout(100);expect(page.locator('#reviewStep')).to_contain_text('0 / 2')
    assert page.evaluate('v5Review')==original
    after=page.evaluate("api('/me')");assert after['state']==before['state']
    page.screenshot(path='docs/qa-interactive/review-original-preserved.png',full_page=True)


def test_late_opening_bookmark_cannot_replace_new_course(page,site):
    login(page,site);page.evaluate("tab('opening')");expect(page.locator('#studyCourse option')).to_have_count(55)
    page.locator('#studyCourse').select_option('french-advance');expect(page.locator('#studyOpeningBoard .sq')).to_have_count(64)
    page.get_by_role('button',name='학습 위치 저장',exact=True).click();expect(page.locator('#studySaveStatus')).to_contain_text('저장했어요')
    saved=page.evaluate("api('/study/openings')")
    page.evaluate("""() => {const original=api;window.holdOpening=true;api=function(p,...a){if(p==='/study/openings'&&window.holdOpening){window.holdOpening=false;return new Promise(resolve=>window.releaseOpening=resolve);}return original(p,...a);};}""")
    page.get_by_role('button',name='저장 위치 이어하기',exact=True).click()
    page.locator('#studyCourse').select_option('caro-panov');expect(page.locator('#studyMessage')).to_contain_text('등록된')
    page.evaluate('d=>window.releaseOpening(d)',saved);page.wait_for_timeout(100)
    expect(page.locator('#studyCourse')).to_have_value('caro-panov')
    click_move(page,'studyOpeningBoard','d2d4');expect(page.locator('#studyMessage')).to_contain_text('다른 등록 변형')
    page.get_by_role('button',name='해설 전환 · 디클라인드 · 정통 전개',exact=True).click()
    expect(page.locator('#studyCourse')).to_have_value('queens-declined')


def test_first_visit_auto_board_and_late_resume_does_not_replace_move(page,site):
    login(page,site);page.evaluate("tab('opening')")
    expect(page.locator('#studyOpeningBoard .sq:enabled')).to_have_count(64)
    expect(page.locator('#studyCourse')).to_have_value('italian-pianissimo')
    page.locator('#studyCourse').select_option('french-advance')
    expect(page.locator('#studyMessage')).to_contain_text('등록된')
    click_move(page,'studyOpeningBoard','e2e4');expect(page.locator('#studyMessage')).to_contain_text('등록된')
    page.get_by_role('button',name='학습 위치 저장',exact=True).click()
    expect(page.locator('#studySaveStatus')).to_contain_text('저장했어요')
    saved=page.evaluate("api('/study/openings')")
    click_move(page,'studyOpeningBoard','e7e6');expect(page.locator('#studyMessage')).to_contain_text('등록된')
    page.evaluate("""() => {const original=api;window.holdOpening=true;api=function(p,...a){if(p==='/study/openings'&&window.holdOpening){window.holdOpening=false;return new Promise(resolve=>window.releaseOpening=resolve);}return original(p,...a);};}""")
    page.get_by_role('button',name='저장 위치 이어하기',exact=True).click()
    click_move(page,'studyOpeningBoard','d2d4');expect(page.locator('#studyMessage')).to_contain_text('등록된')
    before=page.locator('#studyOpeningBoard').inner_html()
    page.evaluate('d=>window.releaseOpening(d)',saved);page.wait_for_timeout(150)
    assert page.locator('#studyOpeningBoard').inner_html()==before
    click_move(page,'studyOpeningBoard','d7d5');expect(page.locator('#studyMessage')).to_contain_text('등록된')


def test_delayed_save_ack_after_move_updates_revision_without_replacing_board(page,site):
    login(page,site);page.evaluate("tab('opening')")
    expect(page.locator('#studyOpeningBoard .sq:enabled')).to_have_count(64)
    click_move(page,'studyOpeningBoard','e2e4');expect(page.locator('#studyMessage')).to_contain_text('등록된')
    pending=[];posts=[]
    def hold_first(route):
        posts.append(route.request.post_data_json)
        if len(posts)==1:pending.append(route)
        else:route.continue_()
    page.route('**/api/study/openings/save',hold_first)
    save=page.get_by_role('button',name='학습 위치 저장',exact=True)
    save.click();expect(page.locator('#studySaveStatus')).to_contain_text('저장하고')
    assert len(pending)==1
    click_move(page,'studyOpeningBoard','e7e5');expect(page.locator('#studyMessage')).to_contain_text('등록된')
    expect(page.locator('.cma-motion-ghost')).to_have_count(0)  # Compare settled board DOM, not transient animation opacity.
    current=page.locator('#studyOpeningBoard').inner_html()
    expect(save).to_be_disabled();assert len(posts)==1  # One in-flight save; board remains usable.
    with page.expect_response(lambda r:r.url.endswith('/study/openings/save')) as first:
        pending[0].continue_()
    assert first.value.status==200 and first.value.json()['revision']==1
    expect(page.locator('#studySaveStatus')).to_contain_text('저장했어요')
    assert page.locator('#studyOpeningBoard').inner_html()==current
    with page.expect_response(lambda r:r.url.endswith('/study/openings/save')) as second:save.click()
    assert second.value.status==200 and second.value.json()['revision']==2
    expect(page.locator('#studySaveStatus')).to_contain_text('저장했어요')
    assert posts==[
        {'course_id':'italian-pianissimo','moves':['e2e4'],'mode':'explore','orientation':'white','revision':0},
        {'course_id':'italian-pianissimo','moves':['e2e4','e7e5'],'mode':'explore','orientation':'white','revision':1}]
    assert page.locator('#studyOpeningBoard').inner_html()==current
    stored=page.evaluate("api('/study/openings')")['saved']
    assert stored['revision']==2 and stored['moves']==['e2e4','e7e5']


@pytest.mark.parametrize('width',[390,1280])
def test_opening_redo_boundaries_and_delayed_description(page,site,width):
    page.set_viewport_size({'width':width,'height':950});login(page,site)
    page.evaluate("tab('opening')");expect(page.locator('#studyCourse option')).to_have_count(55)
    page.locator('#studyCourse').select_option('london-core')
    expect(page.locator('#studyMessage')).to_contain_text('등록된')
    previous=page.locator('#studyTools').get_by_role('button',name='이전 수',exact=True)
    redo=page.get_by_role('button',name='되돌린 수 복원',exact=True)
    expect(previous).to_be_disabled();expect(redo).to_be_disabled()
    before=page.evaluate("api('/me')")
    # Hold only the explanation: the actual board request still uses the server.
    page.evaluate("""() => {const original=api;window.holdDescription=true;api=(p,...args)=>p==='/study/openings/position'&&window.holdDescription?new Promise(resolve=>window.releaseDescription=()=>original(p,...args).then(resolve)):original(p,...args)}""")
    click_move(page,'studyOpeningBoard','d2d4')
    expect(page.locator('#studyMessage')).to_have_text('현재 오프닝 위치의 해설을 불러오고 있어요…')
    expect(page.locator('#studyChoices button')).to_have_count(0)
    expect(redo).to_be_disabled()
    page.evaluate('window.holdDescription=false;releaseDescription()')
    expect(page.locator('#studyMessage')).to_contain_text('등록된')
    expect(page.locator('#studyChoices button').first).to_be_visible()
    board_after=page.locator('#studyOpeningBoard').inner_html()
    explanation=page.locator('#studyExplanation').inner_text()
    previous.click();expect(page.locator('#studyMessage')).to_contain_text('등록된')
    expect(previous).to_be_disabled();expect(redo).to_be_enabled()
    redo.click();expect(page.locator('#studyMessage')).to_contain_text('등록된')
    expect(redo).to_be_disabled();expect(previous).to_be_enabled()
    assert page.locator('#studyOpeningBoard').inner_html()==board_after
    assert page.locator('#studyExplanation').inner_text()==explanation
    # An alternative move replaces the old redo path; recall still hides answers.
    previous.click();expect(redo).to_be_enabled()
    page.locator('#studyMode').select_option('recall')
    expect(page.locator('#studyExplanation')).to_contain_text('해설을 가렸어요')
    click_move(page,'studyOpeningBoard','e2e4')
    expect(redo).to_be_disabled()
    expect(page.locator('#studyExplanation')).to_contain_text('해설을 가렸어요')
    expect(page.locator('#studyChoices button')).to_have_count(0)
    assert page.evaluate("api('/me')")['state']==before['state']
