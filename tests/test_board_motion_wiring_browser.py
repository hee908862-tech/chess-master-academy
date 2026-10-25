"""Real local API response wiring, including final single-ply completion."""
import chess
from playwright.sync_api import expect
from test_qa_browser import site,page,square
from test_study_browser import login,click_move
from v9_server import LIB


def observe(page):
    page.evaluate("""()=>{window.observedMotion=[];const old=cmaBoardPresentation.transition;cmaBoardPresentation.transition=(id,u,paint,reverse=false)=>{const result=old(id,u,paint,reverse);observedMotion.push({id,u,ghosts:document.querySelectorAll('.cma-motion-ghost').length});return result;};}""")


def move(page,board,u,endpoint):
    with page.expect_response(lambda r:r.url.endswith(endpoint) and r.request.method=='POST') as response:
        click_move(page,board,u)
        if len(u)==5:page.locator('#cmaPromotionModal').get_by_role('button',name={'q':'퀸','r':'룩','b':'비숍','n':'나이트'}[u[4]],exact=False).click()
    assert response.value.status==200
    expect(page.locator('.cma-motion-ghost')).to_have_count(0)
    return response.value.json()


def test_foundation_real_intermediate_and_final_delta(page,site):
    login(page,site);page.evaluate("cmaNavigation.go('learn/basics')")
    page.locator('#foundationCourseList > summary').click()
    page.locator('#foundation-open-opening-turns').click()
    expect(page.locator('#foundationBoard .sq')).to_have_count(64);observe(page)
    for u,count in [('d2d4',0),('e2e4',2),('g1f3',2),('f1c4',1)]:
        result=move(page,'foundationBoard',u,'/foundations/action')
        assert page.evaluate('observedMotion.at(-1).ghosts')==count
    assert result['active']['solved']
    assert result['active']['visual']['played_moves']==['b8c6','f1c4']


def test_challenge_actual_success_uses_submitted_move_when_offset_is_unchanged(page,site):
    login(page,site);page.evaluate("tab('puzzle')")
    page.locator('#puzzleModeChallenge').click();page.locator('#challengeStart').click()
    expect(page.locator('#challengeBoard .sq:enabled')).to_have_count(64);observe(page)
    state=page.evaluate("api('/challenge')")
    task=state['active'];line=LIB[task['puzzle_id']]['moves'][1:]
    for u in line[::2]:
        result=move(page,'challengeBoard',u,'/challenge/action')
        assert page.evaluate('observedMotion.at(-1).ghosts')>0
        if result['active']['phase']!='playing':break
    assert result['active']['phase']!='playing'
    assert result['active']['score']==10
    page.locator('#challengeNext').click()
    expect(page.locator('#challengeBoard .sq:enabled')).to_have_count(64)
    task=page.evaluate("api('/challenge')")['active'];b=chess.Board(task['fen'])
    correct=LIB[task['puzzle_id']]['moves'][1]
    alternatives=[]
    for m in b.legal_moves:
        trial=b.copy();trial.push(m)
        if m.uci()!=correct and not trial.is_checkmate():alternatives.append(m.uci())
    assert alternatives
    result=move(page,'challengeBoard',alternatives[0],'/challenge/action')
    assert result['active']['lives']==2 and page.evaluate('observedMotion.at(-1).ghosts')==0


def test_learning_actual_completion_motion(page,site):
    login(page,site);page.evaluate("tab('training')");page.locator('#learningFresh').click()
    expect(page.locator('#learningBoard .sq')).to_have_count(64);observe(page)
    task=page.evaluate("api('/learning/dashboard')")['active'];u=LIB[task['card_id'].removeprefix('puzzle-')]['moves'][1]
    result=move(page,'learningBoard',u,'/learning/action')
    assert result['done'] and page.evaluate('observedMotion.at(-1).ghosts')>0


def test_legacy_assessment_actual_nested_answer_response_motion(page,site):
    login(page,site);page.unroute('**/api/v8/assessment/status')
    question=page.evaluate("api('/v8/assessment/start','POST')")['question']
    page.evaluate("tab('assessment')")
    expect(page.locator('#testBoard .sq:enabled')).to_have_count(64);observe(page)
    # Any legal answer is graded by the real endpoint; feedback animates its revealed answer.
    result=move(page,'testBoard',question['legal'][0],'/v8/assessment/answer')
    assert result['feedback']['answer']
    assert page.evaluate('observedMotion.at(-1).u')==result['feedback']['answer']
    assert page.evaluate('observedMotion.at(-1).ghosts')>0


def test_learning_full_line_final_single_ply_real_endpoint(page,site,tmp_path_factory):
    # Seed only this test's disposable SQLite account with a deterministic legal line.
    import json,sqlite3
    login(page,site);page.evaluate("tab('training')");page.locator('#learningFresh').click()
    expect(page.locator('#learningBoard .sq')).to_have_count(64)
    task=page.evaluate("api('/learning/dashboard')")['active'];page.evaluate("tab('home')")
    seeded=False
    for path in tmp_path_factory.getbasetemp().glob('db*/test.sqlite3'):
        with sqlite3.connect(path) as conn:
            for code,raw in conn.execute('SELECT code,state FROM learning_progress').fetchall():
                state=json.loads(raw)
                if (state.get('active') or {}).get('id')!=task['session_id']:continue
                card=state['cards'][task['card_id']]
                card.update(fen=chess.STARTING_FEN,line=['e2e4','e7e5','g1f3','b8c6','f1c4'],full_line=True)
                state['active'].update(fen=chess.STARTING_FEN,moves=[],line_index=0,turns=0,side='white',done=False,opponent_last_move=None)
                conn.execute('UPDATE learning_progress SET state=? WHERE code=?',(json.dumps(state),code));seeded=True
    assert seeded
    page.evaluate("tab('training')");expect(square(page,'learningBoard','e2')).to_have_attribute('aria-label','e2 백 폰');observe(page)
    for u,count in [('d2d4',0),('e2e4',2),('g1f3',2),('f1c4',1)]:
        result=move(page,'learningBoard',u,'/learning/action')
        assert page.evaluate('observedMotion.at(-1).ghosts')==count
    assert result['done'] and result['played_moves']==['b8c6','f1c4']
    assert result['board_explanation']['arrows']
    # Relationship renderer uses an SVG overlay since PR41, not legacy cell labels.
    expect(page.locator('#learningBoard .foundation-arrows')).to_have_count(1)
    assert page.locator('#learningBoard .foundation-arrows path').count() >= len(result['board_explanation']['arrows'])
    expect(page.locator('#learningBoardFacts')).to_be_visible()
