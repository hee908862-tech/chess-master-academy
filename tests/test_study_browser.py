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
    page.evaluate("tab('opening')");expect(page.locator('#studyCourse option')).to_have_count(27)
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
    page.reload();page.evaluate("tab('opening')");expect(page.locator('#studyCourse option')).to_have_count(27)
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
    page.get_by_role('button',name='이 위치에서 탐색',exact=True).click();expect(page.locator('#reviewBranchStatus')).to_contain_text('양쪽')
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
    login(page,site);page.evaluate("tab('opening')");expect(page.locator('#studyCourse option')).to_have_count(27)
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
