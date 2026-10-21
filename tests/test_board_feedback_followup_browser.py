from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page
from test_education_browser import enter as edu_enter,start as edu_start
from test_repertoire_browser import enter as rep_enter,select_start

@pytest.mark.parametrize('width',[390,1280])
@pytest.mark.parametrize('mode',['education','repertoire'])
def test_actual_pending_and_same_grid_column(page,site,mode,width):
    page.set_viewport_size({'width':width,'height':900})
    if mode=='education':edu_enter(page,site);edu_start(page)
    else:rep_enter(page,site);select_start(page)
    board=mode+'Board'
    expect(page.locator('#'+board+'Feedback')).to_be_visible()
    column=page.locator('#'+board).locator('..')
    assert 'board-feedback-column' in column.get_attribute('class')
    assert column.locator('..').locator(':scope > *').count()==2
    assert column.locator('..').locator('.focus-lesson-panel > #'+board+'Feedback').count()==1
    boxes=page.evaluate('id=>{const c=document.getElementById(id).parentElement;return [c.getBoundingClientRect().toJSON(),c.nextElementSibling.getBoundingClientRect().toJSON()]}',board)
    if width==1280:
        assert boxes[1]['x']>=boxes[0]['right']-1
        assert abs(boxes[0]['y']-boxes[1]['y'])<=8
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    page.evaluate("mode=>{const real=api;window.releaseFollowup=null;api=async(...args)=>{const result=await real(...args);if(args[0]==='/'+mode+'/action')return new Promise(resolve=>releaseFollowup=()=>resolve(result));return result;};}",mode)
    if mode=='repertoire':page.locator('#repertoireBoard [aria-label^="d2 "]').click()
    page.evaluate('id=>window.followupSquare=document.querySelector("#"+id+" .sq")',board)
    page.locator('#'+board+' [aria-label^="'+('c3' if mode=='education' else 'd4')+' "]').click()
    page.wait_for_function('!!releaseFollowup')
    expect(page.locator('#'+board+'Feedback')).to_have_attribute('data-kind','pending')
    assert page.evaluate('id=>followupSquare===document.querySelector("#"+id+" .sq")',board)
    page.evaluate('releaseFollowup()')
    expect(page.locator('#'+board+'Feedback')).not_to_have_attribute('data-kind','pending')
    out=Path('docs/qa-board-centered-feedback/captures');out.mkdir(exist_ok=True)
    page.screenshot(path=str(out/f'{mode}-{width}.png'),full_page=True)

@pytest.mark.parametrize('board',['studyOpeningBoard','reviewBoard'])
def test_study_initial_failure_and_retry(page,site,board):
    from test_study_browser import login
    login(page,site)
    page.route('**/api/study/position',lambda r:r.fulfill(status=503,json={'detail':'first position unavailable'}))
    if board=='studyOpeningBoard':page.evaluate("tab('opening')")
    else:
        page.route('**/api/games/history',lambda r:r.fulfill(json=[{'index':0,'color':'white','plies':0,'result':'draw'}]))
        page.route('**/api/games/review/0',lambda r:r.fulfill(json={'color':'white','moves':[]}))
        page.evaluate("tab('review')");page.locator('#reviewLoad').click()
        page.get_by_role('button',name='여기부터 다시 두기',exact=True).click()
    expect(page.locator('#'+board+'Feedback')).to_have_attribute('data-kind','error')
    expect(page.locator('#'+board+'Feedback')).to_contain_text('위치 조회 실패')
    page.unroute('**/api/study/position')
    page.get_by_role('button',name='분기 초기화',exact=True).filter(visible=True).click()
    expect(page.locator('#'+board+' .sq')).to_have_count(64)
    expect(page.locator('#'+board+'Feedback')).to_have_attribute('data-kind','ready')


def test_legacy_feedback_game_result_and_error_recovery(page,site):
    from test_qa_browser import open_page,START,RESULT
    open_page(page,site)
    feedback={'active':True,'phase':'feedback','index':48,'feedback':{'correct':True,'domain':'test','difficulty':1,'seconds':1,'points':1,'original_fen':START,'answer_fen':START,'answer':'e2e4'}}
    response=feedback.copy()
    page.route('**/api/v8/assessment/status',lambda r:r.fulfill(json=response))
    page.evaluate("tab('assessment')")
    expect(page.locator('#testBoardFeedback')).to_contain_text('첫 수 판정')
    board=page.evaluate("({squares:fromFen(chessStart),turn:'white',legal:[]})")
    page.route('**/api/v8/assessment/next',lambda r:r.fulfill(json={'phase':'game','board':board}))
    page.locator('#v8Next').click()
    expect(page.locator('#testBoardFeedback')).to_contain_text('평가 대국')
    expect(page.locator('#testBoardFeedback')).not_to_contain_text('정답')
    response.clear();response.update(active=False,phase='results',result=RESULT)
    page.locator('#v8Retry').click();expect(page.locator('#testBoardFeedback')).to_contain_text('평가 전체 완료')
    page.route('**/api/v8/assessment/status',lambda r:r.fulfill(status=503,json={'detail':'status unavailable'}))
    page.locator('#v8Retry').click();expect(page.locator('#testBoardFeedback')).to_have_attribute('data-kind','error')
    page.unroute('**/api/v8/assessment/status');page.route('**/api/v8/assessment/status',lambda r:r.fulfill(json={'active':False}))
    page.locator('#v8Retry').click();expect(page.locator('#testBoardFeedback')).to_have_count(0)
    page.route('**/api/v8/assessment/start',lambda r:r.fulfill(status=503,json={'detail':'start unavailable'}))
    page.locator('#v8Start').click();expect(page.locator('#testBoardFeedback')).to_contain_text('시작 여부 확인')
    page.locator('#v8Retry').click();expect(page.locator('#testBoardFeedback')).to_have_count(0)


def test_settings_preserve_actual_board_verdict(page,site):
    from test_study_browser import login
    login(page,site);page.evaluate("tab('training')");page.locator('#learningFresh').click()
    expect(page.locator('#learningBoardFeedback')).to_be_visible()
    before=page.locator('#learningBoardFeedback').text_content()
    saved=page.evaluate("api('/learning/dashboard')")['active']
    page.route('**/api/learning/settings',lambda r:r.fulfill(status=503,json={'detail':'settings unavailable'}))
    page.evaluate("tab('profile/settings')")
    page.locator('#learningSaveIntervals').click()
    expect(page.locator('#learningSettingsStatus')).to_contain_text('settings unavailable')
    assert page.locator('#learningBoardFeedback').text_content()==before
    assert page.evaluate("api('/learning/dashboard')")['active']==saved
    page.unroute('**/api/learning/settings')
    page.locator('#learningSaveIntervals').click()
    expect(page.locator('#learningSettingsStatus')).to_contain_text('복습 간격을 저장')
    assert page.locator('#learningBoardFeedback').text_content()==before
    assert page.evaluate("api('/learning/dashboard')")['active']==saved

@pytest.mark.parametrize('width',[320,1280])
def test_course_board_feedback_column(page,site,width):
    from test_study_browser import login
    page.unroute('**/api/v9/catalog');page.set_viewport_size({'width':width,'height':900});login(page,site)
    theme=page.evaluate("async()=>{const c=await api('/v9/catalog');return c.themes.find(t=>Object.values(t.counts).some(n=>n>=15)).id}")
    page.evaluate('async t=>{tab("learn");return cmaOpenV9Course(t)}',theme);page.locator('#v9CourseStart').click()
    expect(page.locator('#v9CourseBoard .sq')).to_have_count(64)
    column=page.locator('#v9CourseBoard').locator('..')
    assert 'board-feedback-column' in column.get_attribute('class')
    assert column.locator('#v9CourseBoardFeedback').count()==1
    boxes=page.evaluate('()=>{const c=document.getElementById("v9CourseBoard").parentElement;return [c.getBoundingClientRect().toJSON(),document.getElementById("v9CourseHint").parentElement.getBoundingClientRect().toJSON()]}')
    if width==1280:assert boxes[1]['x']>=boxes[0]['right']-1 and abs(boxes[0]['y']-boxes[1]['y'])<=8
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    page.screenshot(path=f'docs/qa-board-centered-feedback/captures/course-{width}.png',full_page=True)
