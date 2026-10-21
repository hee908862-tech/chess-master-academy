import copy
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page,square
from test_study_browser import login,click_move
from v9_server import LIB

@pytest.mark.parametrize('width,height,zoom',[(320,800,1),(390,844,1),(1280,720,1),(844,390,1),(1280,720,2)])
def test_real_training_pending_completion_stable_board_controls(page,site,width,height,zoom):
    page.set_viewport_size({'width':width,'height':height});login(page,site)
    page.evaluate('z=>document.body.style.zoom=z',zoom);page.evaluate("tab('training')")
    page.locator('#learningFresh').click();expect(page.locator('#learningBoardFeedback')).to_be_visible()
    task=page.evaluate("api('/learning/dashboard')")['active'];u=LIB[task['card_id'].removeprefix('puzzle-')]['moves'][1]
    assert page.locator('.feedback-fact-lines').count()==0
    page.locator('#learningBoard').scroll_into_view_if_needed()
    initial=page.locator('#learningBoard').bounding_box()
    page.evaluate("""()=>{const real=api;window.actionCount=0;api=async(...a)=>{const d=await real(...a);if(a[0]==='/learning/action'){actionCount++;return new Promise(resolve=>window.releaseFeedback=()=>resolve(d));}return d;};}""")
    click_move(page,'learningBoard',u)
    if len(u)==5:page.locator('#cmaPromotionModal').get_by_role('button',name={'q':'퀸','r':'룩','b':'비숍','n':'나이트'}[u[4]],exact=False).click()
    page.wait_for_function('!!window.releaseFeedback')
    expect(page.locator('#learningBoardFeedback')).to_contain_text('응답 대기')
    expect(page.locator('#learningBoardFeedback')).not_to_contain_text('판단 완료')
    # Programmatic duplicate presses cannot submit another request while busy.
    page.evaluate("document.querySelector('#learningBoard .sq').click()")
    assert page.evaluate('actionCount')==1
    y=page.locator('#learningBoard').bounding_box()['y']
    page.evaluate("cmaFeedback.set('learningBoard',{detail:'응답을 기다립니다. '.repeat(150)})")
    assert abs(page.locator('#learningBoard').bounding_box()['y']-y)<2
    page.evaluate('releaseFeedback()')
    expect(page.locator('#learningBoardFeedback')).to_contain_text('첫 수 판단 완료')
    expect(page.locator('#learningBoardFeedback')).to_contain_text('서버 상태 확인됨')
    assert page.locator('#learningBoard .sq:enabled').count()==0
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    out=Path('/tmp/cma-centered-captures');out.mkdir(exist_ok=True)
    page.screenshot(path=str(out/f'training-{width}-{height}-{zoom}.png'),full_page=True)


def test_training_failure_requires_authoritative_refresh(page,site):
    login(page,site);page.evaluate("tab('training')");page.locator('#learningFresh').click()
    expect(page.locator('#learningBoardFeedback')).to_be_visible()
    task=page.evaluate("api('/learning/dashboard')")['active'];u=LIB[task['card_id'].removeprefix('puzzle-')]['moves'][1]
    page.route('**/api/learning/action',lambda r:r.abort())
    click_move(page,'learningBoard',u)
    if len(u)==5:page.locator('#cmaPromotionModal').get_by_role('button',name={'q':'퀸','r':'룩','b':'비숍','n':'나이트'}[u[4]],exact=False).click()
    expect(page.locator('#learningBoardFeedback')).to_contain_text('保存' if False else '저장 여부 미확인')
    posts=[];page.on('request',lambda r:posts.append(r.url) if '/learning/action' in r.url else None)
    click_move(page,'learningBoard',u)
    assert posts==[]
    page.unroute('**/api/learning/action');page.locator('#learningRefresh').click()
    expect(page.locator('#learningBoardFeedback')).to_contain_text('서버 상태 확인됨')
    assert page.evaluate("api('/learning/dashboard')")['active']['revision']==task['revision']

@pytest.mark.parametrize('complete,outcome',[ (False,'unverified_alternative'),(False,'partial_execution'),(True,'completed') ])
def test_diagnosis_only_complete_sequence_claims_completion(page,site,complete,outcome):
    from test_journey_browser import question
    value=question();value['phase']='feedback';value['feedback']={'complete':complete,'first_correct':True,'outcome':outcome,'reason':'검증 조건에 따른 기록','fen':value['question']['fen'],'submitted':['e3h3'],'expected':['e3h3'],'correct_plies':1,'total_plies':2}
    page.route('**/api/journey',lambda r:r.fulfill(json={'active':value,'latest':None,'results':[]}))
    login(page,site);page.evaluate("tab('diagnosis')")
    box=page.locator('#journeyBoardFeedback');expect(box).to_be_visible()
    if complete:expect(box).to_contain_text('문제 완료 · 전체 수순 성공')
    else:expect(box).not_to_contain_text('문제 완료')
    expect(page.locator('#journeyNext')).to_be_visible()
    assert page.locator('#journeyBoard .sq:enabled').count()==0


def test_fact_visibility_position_cleanup_and_no_writes(page,site):
    from board_facts import learning_facts
    import chess
    login(page,site);page.evaluate("tab('training')")
    fen='6k1/8/8/8/n7/8/1P6/R5K1 w - - 0 1';b=chess.Board(fen);b.push_uci('a1a2')
    facts=learning_facts({'fen':fen,'line':['a1a2']},{'fen':b.fen(),'done':True,'outcome':{'success':True}})
    writes=[];page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
    page.evaluate("f=>{drawBoard('learningBoard',fromFen(f.fen));cmaFeedback.set('learningBoard',{title:'확인된 배치',facts:f});}",facts)
    expect(page.locator('#learningBoard .feedback-fact-label')).to_have_count(2)
    page.locator('#learningBoardFacts button').click();expect(page.locator('.feedback-fact-lines')).to_have_count(0)
    page.locator('#learningBoardFacts button').click();expect(page.locator('.feedback-fact-lines')).to_have_count(1)
    page.evaluate("drawBoard('learningBoard',fromFen(chessStart))")
    expect(page.locator('#learningBoardFacts')).not_to_be_visible();expect(page.locator('.feedback-fact-label')).to_have_count(0)
    assert writes==[]
