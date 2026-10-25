"""Independent-review boundaries; disposable accounts and controlled move responses."""
import chess
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page,open_page,square
from test_study_browser import login
from test_focused_learning_browser import open_foundation_list
from test_foundations_browser import choose_course
from test_board_interaction import reply


def test_active_education_list_blocks_start_and_failed_read_allows_return(page,site):
    login(page,site);page.evaluate("cmaNavigation.go('learn/education')")
    page.locator('#educationBody article').first.get_by_role('button',name='설명 보며 학습',exact=True).click()
    expect(page.locator('#educationBoard')).to_be_visible();saved=page.evaluate("api('/education')")
    writes=[];page.on('request',lambda r:writes.append(r.url) if '/api/' in r.url and r.method!='GET' else None)
    page.locator('#learn-list-back').click()
    starts=page.locator('#educationBody article button[id^=education-start-]')
    assert starts.count()==20
    for b in starts.all():expect(b).to_be_disabled()
    resume=page.get_by_role('button',name='저장된 교육 실습 이어하기',exact=True)
    expect(resume).to_be_enabled()
    page.route('**/api/education',lambda r:r.fulfill(status=503,json={'detail':'temporary read failure'}))
    page.locator('#educationRefresh').click();expect(page.locator('#educationStatus')).to_contain_text('temporary read failure')
    expect(resume).to_be_enabled();resume.click();expect(page.locator('#educationBoard')).to_be_visible()
    page.unroute('**/api/education')
    assert writes==[] and page.evaluate("api('/education')")==saved


@pytest.mark.parametrize('target',['learn','learn/tactics'])
def test_course_premove_cancelled_only_on_actual_activity_leave(page,site,target):
    open_page(page,site);b=chess.Board()
    task=dict(id='p1',session_id='s1',fen=b.fen(),legal=[m.uci() for m in b.legal_moves],rating=1400,themes=['전술'],ply=1,index=0,total=15,side='white',opponent_last_move=None)
    page.route('**/api/v9/session/course',lambda r:r.fulfill(json={'active':False}))
    page.route('**/api/v9/course/start',lambda r:r.fulfill(json=task))
    page.evaluate("tab('learn');cmaOpenV9Course('quietMove')")
    page.locator('#v9CourseStart').click();name='v9CourseBoard'
    expect(square(page,name,'e2')).to_be_visible()
    requests=[];page.route('**/api/v9/course/move',lambda r:requests.append(r))
    page.get_by_role('checkbox',name='프리무브 '+name,exact=True).check()
    square(page,name,'e2').click();square(page,name,'e4').click()
    square(page,name,'g1').click();square(page,name,'f3').click()
    expect(page.locator('#'+name+' .premove-arrow')).to_have_count(1)
    page.locator('.nav [data-tab=learn]').click();page.keyboard.press('Escape')
    expect(page.locator('#'+name+' .premove-arrow')).to_have_count(1)
    page.evaluate('(route)=>cmaNavigation.go(route)',target)
    expect(page.locator('#'+name+' .premove-arrow')).to_have_count(0)
    b.push_uci('e2e4');b.push_uci('e7e5');reply(requests[0],'course',b,task)
    page.wait_for_timeout(500)
    assert len(requests)==1
    page.evaluate("cmaOpenV9Course('quietMove')")
    expect(square(page,name,'e5')).to_have_attribute('aria-label',__import__('re').compile('^e5 흑 폰'))
    expect(page.locator('#'+name+' .premove-arrow')).to_have_count(0)


@pytest.mark.parametrize('login_after',[False,True])
def test_public_course_choice_survives_reload_or_login_without_start(page,site,login_after):
    page.add_init_script("localStorage.removeItem('chess_token')")
    page.goto(site[0]);page.evaluate("cmaAcademyNavigate('tactics');cmaOpenV9Course('quietMove')")
    expect(page.locator('#v9CourseTitle')).to_contain_text('조용한 수')
    writes=[];page.on('request',lambda r:writes.append(r.url) if '/api/' in r.url and r.method!='GET' else None)
    if login_after:
        page.locator('#v9CourseStart').click()
        page.locator('#codeField').fill('BROWSER-QA');page.locator('#pinField').fill('test-pin-9384');page.locator('#signin').click()
    else:page.reload()
    expect(page.locator('#v9LearnMode')).to_be_visible()
    expect(page.locator('#v9CourseTitle')).to_contain_text('조용한 수')
    expect(page.locator('#v9CourseLevel')).to_have_value('중급')
    assert all(url.endswith('/login') for url in writes),writes
    assert 'quietMove' in page.evaluate('location.hash')
    assert page.locator('#v9CourseBoard .sq').count()==0


def test_guest_education_login_returns_to_list_without_attempt(page,site):
    page.add_init_script("localStorage.removeItem('chess_token')")
    page.goto(site[0]);page.evaluate("cmaAcademyNavigate('education')")
    writes=[];page.on('request',lambda r:writes.append(r.url) if '/api/' in r.url and r.method!='GET' else None)
    page.get_by_role('button',name='계정 연결 후 교육 선택',exact=True).click()
    page.locator('#codeField').fill('BROWSER-QA');page.locator('#pinField').fill('test-pin-9384');page.locator('#signin').click()
    expect(page.locator('#educationBody article')).to_have_count(10)
    assert page.evaluate('location.hash')=='#learn/education'
    assert page.evaluate("api('/education')")['active'] is None
    assert all(url.endswith('/login') for url in writes),writes


def test_selected_course_reload_does_not_restore_unrelated_saved_session(page,site):
    open_page(page,site)
    page.route('**/api/v9/session/course',lambda r:r.fulfill(json={'active':True,'theme':'interference','level':'중급','session_id':'unrelated-old-session','fen':chess.STARTING_FEN,'legal':[],'themes':['interference'],'index':0,'total':15,'rating':1400,'ply':1}))
    page.evaluate("tab('learn');cmaOpenV9Course('quietMove')")
    page.reload();expect(page.locator('#v9CourseTitle')).to_contain_text('조용한 수')
    expect(page.locator('#v9LearnMode')).to_be_visible()
    assert page.locator('#v9CourseBoard .sq').count()==0
    assert 'unrelated-old-session' not in page.evaluate('location.hash')
    page.goto(site[0]+'/#learn/tactics/practice?theme=not-a-course&level=unknown')
    expect(page.locator('#v9CourseCards')).to_be_visible()
    assert page.evaluate('location.hash')=='#learn/tactics'


def test_hub_zoom_long_text_and_keyboard_return(page,site):
    login(page,site);page.evaluate("tab('learn')")
    page.set_viewport_size({'width':1280,'height':600})
    page.evaluate("document.documentElement.style.zoom='2';document.querySelector('#learn-choice-basics').textContent+=' · 긴 안내 문장에서도 기초 규칙을 선택해 연습할 수 있습니다.'")
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    page.locator('#learn-choice-basics').focus();page.keyboard.press('Enter')
    expect(page.locator('#foundationHeading')).to_be_focused()
    page.locator('#learn-hub-back').click();expect(page.locator('#learn-choice-basics')).to_be_focused()
    page.screenshot(path='/tmp/cma-focused-evidence/hub-zoom-200.png',full_page=True)


def test_saved_education_answer_delayed_return_refetches_authoritative_progress(page,site):
    login(page,site);page.evaluate("cmaNavigation.go('learn/education')")
    page.locator('#educationBody article').first.get_by_role('button',name='설명 가리고 복습',exact=True).click()
    expect(page.locator('#educationBoard')).to_be_visible()
    page.evaluate("""()=>{window.eduActualApi=api;window.eduReads=0;api=async(...args)=>{if(args[0]==='/education')eduReads++;const value=await eduActualApi(...args);if(args[0]==='/education/action')return new Promise(resolve=>window.releaseSavedAnswer=()=>resolve(value));return value;};}""")
    square(page,'educationBoard','c3').click();page.wait_for_function('!!window.releaseSavedAnswer')
    saved=page.evaluate("eduActualApi('/education')")
    reads=page.evaluate('eduReads')
    page.evaluate("tab('home');cmaEducation.open()")
    expect(page.locator('#educationPaths')).to_have_attribute('aria-busy','false')
    assert page.evaluate('eduReads')>reads
    expect(page.get_by_role('button',name='이유 확인 · 다음 비교 위치',exact=True)).to_be_visible()
    page.evaluate('releaseSavedAnswer()')
    expect(page.get_by_role('button',name='이유 확인 · 다음 비교 위치',exact=True)).to_be_visible()
    assert page.evaluate("eduActualApi('/education')")==saved


def test_bare_course_route_late_catalog_does_not_leave_hub(page,site):
    from test_qa_browser import CATALOG,TASK
    pending=[];page.route('**/api/v9/catalog',lambda r:pending.append(r))
    page.route('**/api/v9/session/course',lambda r:r.fulfill(json={**TASK,'active':True,'theme':'quietMove','level':'중급','session_id':'saved-course'}))
    page.goto(site[0]+'/#learn/tactics/practice')
    page.wait_for_function("typeof cmaNavigation!=='undefined'")
    page.evaluate("cmaNavigation.go('learn')")
    assert pending
    pending[0].fulfill(json=CATALOG)
    expect(page.locator('#tactic-quietMove')).to_have_count(1)
    page.wait_for_timeout(200)
    expect(page.locator('#academyHub')).to_be_visible()
    expect(page.locator('#v9LearnMode')).not_to_be_visible()
    assert page.evaluate('location.hash')=='#learn'


def test_nondefault_level_history_keeps_forward_entries(page,site):
    from test_qa_browser import CATALOG
    catalog={**CATALOG,'levels':['입문','중급','고급'],'themes':[{**t,'counts':{'입문':15,'중급':15,'고급':15}} for t in CATALOG['themes']]}
    page.route('**/api/v9/catalog',lambda r:r.fulfill(json=catalog))
    open_page(page,site);page.evaluate("cmaNavigation.go('learn/tactics')")
    page.locator('#tactic-quietMove').click();page.locator('#v9CourseLevel').select_option('고급')
    selected=page.evaluate('location.hash')
    page.locator('#learn-list-back').click();page.locator('#tactic-interference').click()
    length=page.evaluate('history.length')
    page.go_back();expect(page.locator('#v9CourseCards')).to_be_visible()
    page.go_back();expect(page.locator('#v9CourseLevel')).to_have_value('고급')
    assert page.evaluate('location.hash')==selected
    assert page.evaluate('history.length')==length
    page.go_forward();expect(page.locator('#v9CourseCards')).to_be_visible()
    page.go_forward();expect(page.locator('#v9CourseTitle')).to_contain_text('간섭')
    assert page.evaluate('history.length')==length


def test_education_list_focus_returns_to_active_lesson_after_render(page,site):
    login(page,site);page.evaluate("cmaNavigation.go('learn/education')")
    lesson=page.locator('#educationBody article').nth(3);lesson_id=lesson.get_attribute('id')
    lesson.get_by_role('button',name='설명 보며 학습',exact=True).click()
    expect(page.locator('#educationBoard')).to_be_visible()
    page.locator('#learn-list-back').click()
    expect(page.locator('#'+lesson_id)).to_be_focused()
    assert -1<=page.locator('#'+lesson_id).bounding_box()['y']<100  # Browser subpixel scroll rounding.


@pytest.mark.parametrize('activity',['new','basics','diagnosis'])
def test_home_has_one_foundation_entry_with_real_progress(page,site,activity):
    from pathlib import Path
    login(page,site);page.set_viewport_size({'width':390,'height':844})
    if activity!='new':
        open_foundation_list(page);choose_course(page,'rook-bishop')
        square(page,'foundationBoard','a1').click();square(page,'foundationBoard','a4').click()
        page.locator('#foundationNext').get_by_role('button',name='다음 단계',exact=True).click()
        expect(page.locator('#foundationStepTitle')).to_contain_text('2/3')
    if activity=='diagnosis':page.evaluate("api('/journey/start','POST',{mode:'balanced'})")
    saved=page.evaluate("api('/foundations')")
    page.evaluate("tab('home')")
    expect(page.locator('#homeBasicsOpen')).to_be_hidden()
    expect(page.locator('#entrySavedBasics')).to_be_hidden()
    primary=page.locator('#homeNextAction > button')
    expect(primary).to_be_visible()
    if activity=='basics':
        expect(page.locator('#journeyHome')).to_be_hidden()
        expect(primary).to_have_text('기초 이어하기')
        expect(page.locator('#homeNextAction')).to_contain_text('2/3')
    elif activity=='diagnosis':expect(primary).to_have_text('진단 이어하기')
    else:expect(primary).to_have_text('기초부터 배우기')
    out=Path('/tmp/cma-focused-evidence');out.mkdir(exist_ok=True)
    page.screenshot(path=str(out/f'home-distinct-{activity}-390.png'),full_page=True)
    writes=[];page.on('request',lambda r:writes.append(r.url) if '/api/' in r.url and r.method!='GET' else None)
    if activity=='diagnosis':
        page.locator('#homeNextAction > details > summary').click()
        page.locator('#homeNextAction > details button').filter(has_text='기초 이어하기').click()
    else:primary.click()
    if activity!='new':
        expect(page.locator('#foundationStepTitle')).to_contain_text('2/3')
        assert page.evaluate("api('/foundations')")==saved and writes==[]
    else:
        expect(page.locator('#movementBoard .sq')).to_have_count(64)
        page.wait_for_function('!cmaMovement.state().loading && !!cmaMovement.state().unit')
        after=page.evaluate("api('/foundations')")
        assert {k:v for k,v in after.items() if k!='movement'}=={k:v for k,v in saved.items() if k!='movement'}
        assert after['movement']['started'] and after['movement']['completed']==0
        assert len(writes)==1 and writes[0].endswith('/movement/start')


def test_level_history_does_not_reuse_cached_different_level_task(page,site):
    from test_qa_browser import CATALOG,TASK
    catalog={**CATALOG,'levels':['중급','고급'],'themes':[{**t,'counts':{'중급':15,'고급':15}} for t in CATALOG['themes']]}
    page.route('**/api/v9/catalog',lambda r:r.fulfill(json=catalog));open_page(page,site)
    saved={**TASK,'active':True,'theme':'quietMove','level':'중급','session_id':'old-level'}
    page.route('**/api/v9/session/course',lambda r:r.fulfill(json=saved))
    page.evaluate("cmaNavigation.go('learn/tactics/practice?theme=quietMove&level=중급')")
    expect(page.locator('#v9CourseBoard .sq')).to_have_count(64)
    page.locator('#v9CourseLevel').select_option('고급');page.locator('#learn-list-back').click()
    page.go_back();expect(page.locator('#v9CourseLevel')).to_have_value('고급')
    expect(page.locator('#v9CourseBoard .sq')).to_have_count(0)
