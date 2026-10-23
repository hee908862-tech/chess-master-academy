"""Real local API and Chromium. Viewports emulate devices; no human learning claim."""
import pytest
from playwright.sync_api import expect
from test_redesign_browser_followup import isolated, site
from test_movement import PATHS


def ready(page):
    page.wait_for_function('!!cmaMovement.state().unit && !cmaMovement.state().loading && !cmaMovement.state().pending')


def enter(page):
    page.locator('#flowBasicsStart').click()
    ready(page)


def square(page, value):
    return page.locator(f'#movementBoard [aria-label^="{value} "]')


@pytest.mark.parametrize('width,height', [(1366,768),(360,800),(390,844),(844,390)])
def test_continuous_delayed_save_and_selection(isolated,site,width,height):
    page,_=isolated; page.set_viewport_size(dict(width=width,height=height));enter(page)
    assert page.evaluate('cmaMovement.state().selected') is None
    page.evaluate("""()=>{window.realMovementApi=api;window.saveCalls=0; api=async (...args)=>{if(args[0]==='/movement/save'){saveCalls++;await new Promise(r=>setTimeout(r,800));}return realMovementApi(...args)}}""")
    square(page,'b2').click(); square(page,'b5').click()
    page.wait_for_function('cmaMovement.state().pending')
    before=page.locator('#movementBoard').bounding_box()
    square(page,'f5').click()
    assert page.evaluate('cmaMovement.state().source')=='f5'
    assert page.evaluate('cmaMovement.state().selected')=='f5'
    assert page.evaluate('cmaMovement.state().pending')
    after=page.locator('#movementBoard').bounding_box()
    assert abs(before['y']-after['y'])<1
    page.wait_for_function('cmaMovement.state().data.active.moves.length===2 && !cmaMovement.state().pending')
    assert page.evaluate('cmaMovement.state().source')=='f5'
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    page.screenshot(path=f'/tmp/movement-{width}x{height}.png',full_page=True)
    square(page,'f3').click()
    page.wait_for_function("cmaMovement.state().unit.unit_id==='rook-block'",timeout=15000)
    assert page.evaluate('cmaMovement.state().moves.length')==0
    assert page.evaluate("api('/movement')")['summary']['completed']==1


def test_all_units_geometry_matches_authoritative_api(isolated,site):
    page,_=isolated;enter(page);page.evaluate("cmaNavigation.go('home')")
    for unit_id,path in PATHS.items():
        d=page.evaluate("async id=>{const d=await api('/movement');return api('/movement/start','POST',{action:'start',unit_id:id,revision:d.revision,request_id:crypto.randomUUID()})}",unit_id)
        for index in range(len(path)+1):
            a=d['active']
            if not a['done']:
                actual=page.evaluate('a=>cmaMovementRules.legalTargets(fromFen(a.fen),a.source).sort()',a)
                assert actual==sorted(m[2:4] for m in a['legal']), (unit_id,index)
            if index<len(path):
                body=dict(unit_id=unit_id,session_id=a['session_id'],revision=d['revision'],version=a['version'],policy=a['policy'],moves=path[:index+1],mistakes=0,helped=False)
                d=page.evaluate("b=>api('/movement/save','POST',b)",body)
        assert d['active']['done'],unit_id


def test_reload_pending_and_failure_retry_preserves_moves(isolated,site):
    page,_=isolated;enter(page)
    page.evaluate("()=>{window.oldApi=api;api=async (...args)=>{if(args[0]==='/movement/save')throw Error('검사용 저장 실패');return oldApi(...args)}}")
    square(page,'b2').click();square(page,'b5').click()
    page.wait_for_function('!!cmaMovement.state().error')
    expect(page.locator('#movementActions button')).to_be_visible()
    assert page.evaluate('cmaMovement.state().source')=='b5'
    page.reload();ready(page)
    page.wait_for_function("cmaMovement.state().data.active.moves.length===1 && !cmaMovement.state().pending")
    assert page.evaluate('cmaMovement.state().source')=='b5'
    assert page.evaluate('cmaMovement.state().selected')=='b5'


def test_divergent_draft_is_not_overwritten(isolated,site):
    page,_=isolated;enter(page)
    page.evaluate("""async()=>{const d=await api('/movement');const a=d.active;await api('/movement/save','POST',{unit_id:a.unit_id,session_id:a.session_id,revision:d.revision,version:a.version,policy:a.policy,moves:['b2b5'],mistakes:0,helped:false});localStorage.setItem('cma_movement_draft_v1:'+a.session_id,JSON.stringify({version:a.version,policy:a.policy,moves:['b2c2'],mistakes:0,helped:false}));await cmaMovement.load()}""")
    assert page.evaluate('cmaMovement.state().conflict')
    before=page.evaluate("localStorage.getItem('cma_movement_draft_v1:'+cmaMovement.state().unit.session_id)")
    expect(square(page,'b5')).to_be_disabled();expect(square(page,'f5')).to_be_disabled()
    assert page.evaluate("localStorage.getItem('cma_movement_draft_v1:'+cmaMovement.state().unit.session_id)")==before
    assert page.evaluate('cmaMovement.state().source')=='b5'

    page.get_by_role('button',name='기기 이동을 보관하고 서버 위치로 이어가기',exact=True).click();ready(page)
    assert not page.evaluate('cmaMovement.state().conflict')
    assert page.evaluate("Object.keys(localStorage).filter(k=>k.includes(':preserved:')).map(k=>localStorage.getItem(k))")==[before]


def test_pawn_detour_restart_and_navigation_cancel(isolated,site):
    page,_=isolated;enter(page)
    page.evaluate("""async()=>{const d=await api('/movement');await api('/movement/start','POST',{action:'start',unit_id:'pawn-capture',revision:d.revision,request_id:crypto.randomUUID()});await cmaMovement.load()}""")
    page.evaluate("""()=>{window.pawnApi=api;api=async (...args)=>{if(args[0]==='/movement/save')await new Promise(r=>setTimeout(r,600));return pawnApi(...args)}}""")
    square(page,'d3').click();square(page,'d4').click()
    expect(page.get_by_role('button',name='새 판에서 다시 해보기',exact=True)).to_be_disabled()
    page.wait_for_function('cmaMovement.state().data.active.moves.length===1 && !cmaMovement.state().pending')
    expect(page.locator('#movementGoal')).to_contain_text('뒤로 못 가요')
    page.get_by_role('button',name='새 판에서 다시 해보기',exact=True).click();ready(page)
    assert page.evaluate('cmaMovement.state().unit.run')==1
    assert page.evaluate('cmaMovement.state().source')=='d3'
    square(page,'d3').click();square(page,'e4').click();square(page,'e5').click();square(page,'e6').click()
    page.evaluate("cmaNavigation.go('home')")
    page.wait_for_function('!cmaMovement.state().pending && cmaMovement.state().data.active.done')
    page.wait_for_timeout(850)
    assert page.evaluate('cmaMovement.state().unit.unit_id')=='pawn-capture'
    assert page.evaluate("api('/movement')")['active']['unit_id']=='pawn-capture'


def test_reconciliation_blocks_input_and_identity_clears_board(isolated,site):
    page,_=isolated;enter(page)
    page.evaluate("""()=>{window.oldMovementApi=api;api=async (...args)=>{if(args[0]==='/movement')await new Promise(r=>setTimeout(r,700));return oldMovementApi(...args)};cmaMovement.load()}""")
    page.wait_for_function('cmaMovement.state().loading')
    expect(square(page,'b2')).to_be_disabled()
    ready(page)
    page.evaluate("""()=>{window.originalIdentity=token;token='';cmaMovement.route('learn/movement')}""")
    expect(page.locator('#movementBoard .sq')).to_have_count(0)
    assert page.evaluate('cmaMovement.state().unit') is None
    page.evaluate("()=>{token=originalIdentity;cmaMovement.load()}")
    ready(page)
    expect(square(page,'b2')).to_be_enabled()


def test_rule_adapter_matches_python_predicates(isolated,site):
    from basic_rules_content import RULE_UNITS,replay_rule
    import chess
    page,_=isolated
    page.evaluate('cmaBasicRules.load()')
    for unit in RULE_UNITS:
        task={**unit,'initial_fen':unit['fen']}
        paths=[unit['example_actions'][:i] for i in range(len(unit['example_actions'])+1)]
        if unit['kind']=='move':paths += [[m.uci()] for m in chess.Board(unit['fen']).legal_moves]
        for path in paths:
            expected=replay_rule(unit,path)
            actual=page.evaluate('x=>cmaBasicRules.replay(x.unit,x.path)',dict(unit=task,path=path))
            for field in ['done','failed','played','place_symbol','visited','opponent_example']:
                assert actual[field]==expected[field],(unit['id'],path,field)
            assert sorted(actual['legal'])==sorted(expected['legal']),(unit['id'],path,'legal')
            assert actual['fen'].split()[:4]==expected['fen'].split()[:4],(unit['id'],path,'fen')


@pytest.mark.parametrize('width,height',[(1366,768),(360,800)])
def test_all_rule_scenes_actual_board_actions(isolated,site,width,height):
    from basic_rules_content import RULE_UNITS
    page,_=isolated;page.set_viewport_size(dict(width=width,height=height));enter(page)
    for unit in RULE_UNITS:
        # Pace this exhaustive synthetic traversal below the unchanged guest
        # quota, including the normal home/progress refreshes after saves.
        page.wait_for_timeout(2000)
        page.evaluate("""async id=>{cmaMovement.cancel();const d=await api('/movement');await api('/movement/start','POST',{action:'start',unit_id:id,revision:d.revision,request_id:crypto.randomUUID()});await cmaMovement.load()}""",unit['id'])
        ready(page);page.wait_for_function('!cmaMovement.state().demonstrating')
        expect(page.locator('#movementTitle')).to_have_text(unit['name'])
        if unit['kind']=='place':
            while not page.evaluate('cmaMovement.state().done'):
                state=page.evaluate('cmaMovement.state()');symbol=state['ruleState']['place_symbol']
                target=next(s for s,p in unit['predicate']['pieces'].items() if p==symbol and s not in state['ruleState']['visited'])
                square(page,target).click()
        else:
            for action in unit['example_actions']:
                if action.startswith('square:'):square(page,action[7:]).click()
                else:
                    square(page,action[:2]).click();square(page,action[2:4]).click()
                    if len(action)==5:page.locator('#cmaPromotionModal button').filter(has_text={'q':'퀸','r':'룩','b':'비숍','n':'나이트'}[action[4]]).click()
        try:
            page.wait_for_function('cmaMovement.state().done && cmaMovement.state().data.active.done && !cmaMovement.state().pending')
        except Exception as exc:
            # Fast synthetic traversal can reach the existing guest quota. Respect
            # the actual cooldown; exercise explicit recovery, never weaken it.
            error=page.evaluate('cmaMovement.state().error')
            import re
            cooldown=re.search(r'(\d+)초 후',error)
            if cooldown:
                page.wait_for_timeout((int(cooldown.group(1))+1)*1000)
                page.locator('#movementActions').get_by_role('button',name='저장 위치 확인 · 다시 저장',exact=True).click()
                page.wait_for_function('cmaMovement.state().done && cmaMovement.state().data.active.done && !cmaMovement.state().pending')
            else:
                raise AssertionError((unit['id'],error,page.evaluate('cmaMovement.state().moves'))) from exc
        assert page.evaluate('cmaMovement.state().done'),unit['id']
        assert not page.evaluate('cmaMovement.state().ruleState.failed'),unit['id']
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),unit['id']
        page.evaluate('cmaMovement.cancel()')
        if unit['id'] in ['rules-mate-queen','rules-setup-place','rules-ep-now','rules-pawn-promotion']:
            page.screenshot(path=f'/tmp/{unit["id"]}-{width}.png',full_page=True)


def test_anonymous_direct_entry_needs_explicit_guest_creation(isolated,site):
    page,_=isolated;created=[]
    page.on('request',lambda r:created.append(r.url) if r.url.endswith('/api/guest/start') else None)
    page.evaluate("cmaNavigation.go('learn/movement')")
    expect(page.locator('#movementActions').get_by_role('button',name='로그인 없이 시작',exact=True)).to_be_visible()
    assert not page.evaluate('token')
    assert not created
    page.locator('#movementActions').get_by_role('button',name='로그인 없이 시작',exact=True).dblclick()
    ready(page)
    assert len(created)==1
    assert page.evaluate('cmaMovement.state().unit.unit_id')=='rook-path'


def test_keyboard_list_zoom_reduced_motion_and_sound(isolated,site):
    page,_=isolated;page.set_viewport_size(dict(width=1366,height=768));page.emulate_media(reduced_motion='reduce');enter(page)
    page.evaluate("""()=>{document.documentElement.style.zoom='2';window.tapCalls=0;window.oscillators=0;window.realTap=playMoveSound;audioCtx={state:'running',currentTime:0,createOscillator(){oscillators++;return {frequency:{setValueAtTime(){},linearRampToValueAtTime(){}},connect(){return {connect(){}}},start(){},stop(){}}},createGain(){return {gain:{setValueAtTime(){},linearRampToValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){}}}};prefs.soundOn=true;playMoveSound=(kind,context)=>{if(context?.board==='movementBoard')tapCalls++;realTap(kind,context)}}""")
    square(page,'b2').focus();page.keyboard.press('Enter')
    assert page.evaluate('cmaMovement.state().selected')=='b2'
    square(page,'c3').focus();page.keyboard.press('Enter')
    assert page.evaluate('cmaMovement.state().selected') is None
    assert page.evaluate('tapCalls')==0
    page.locator('#movementHelp > summary').click()
    page.locator('#movementDestination').select_option('b5');page.locator('#movementSubmit').focus();page.keyboard.press('Enter')
    assert page.evaluate('cmaMovement.state().source')=='b5'
    assert page.evaluate('tapCalls')==1
    assert page.evaluate('oscillators')==2
    assert not page.evaluate("cmaBoardPresentation.isAnimating('movementBoard')")
    page.evaluate('prefs.soundOn=false')
    page.locator('#movementDestination').select_option('f5');page.locator('#movementSubmit').click()
    assert page.evaluate('cmaMovement.state().source')=='f5'
    assert page.evaluate('tapCalls')==2
    assert page.evaluate('oscillators')==2
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    page.screenshot(path='/tmp/movement-keyboard-200percent.png',full_page=True)


def test_malformed_draft_is_preserved_and_help_cancels_advance(isolated,site):
    page,_=isolated;enter(page)
    page.evaluate("""async()=>{const a=cmaMovement.state().unit;localStorage.setItem('cma_movement_draft_v1:'+a.session_id,JSON.stringify({version:a.version,policy:a.policy,moves:'b2b5'}));await cmaMovement.load()}""")
    assert page.evaluate('cmaMovement.state().conflict')
    expect(square(page,'b2')).to_be_disabled()
    original=page.evaluate("localStorage.getItem('cma_movement_draft_v1:'+cmaMovement.state().unit.session_id)")
    page.get_by_role('button',name='기기 이동을 보관하고 서버 위치로 이어가기',exact=True).click();ready(page)
    assert page.evaluate("Object.keys(localStorage).filter(k=>k.includes(':preserved:')).map(k=>localStorage.getItem(k))")==[original]
    page.evaluate("""async()=>{const a=cmaMovement.state().unit;localStorage.setItem('cma_movement_draft_v1:'+a.session_id,'');await cmaMovement.load()}""")
    assert page.evaluate('cmaMovement.state().conflict')
    page.get_by_role('button',name='기기 이동을 보관하고 서버 위치로 이어가기',exact=True).click();ready(page)
    assert not page.evaluate('cmaMovement.state().conflict')
    assert '' in page.evaluate("Object.keys(localStorage).filter(k=>k.includes(':preserved:')).map(k=>localStorage.getItem(k))")
    page.locator('#movementHelp > summary').click()
    square(page,'b2').click();square(page,'b5').click();square(page,'f5').click();square(page,'f3').click()
    page.wait_for_function('cmaMovement.state().data.active.done && !cmaMovement.state().pending')
    page.locator('#movementHelp > summary').click()
    page.wait_for_timeout(900)
    assert page.evaluate('cmaMovement.state().unit.unit_id')=='rook-path'
