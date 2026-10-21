import chess
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page
from test_study_browser import login,click_move

@pytest.mark.parametrize('fen,uci,count',[(chess.STARTING_FEN,'e2e4',1),('4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1','e1g1',2),('r3k2r/8/8/8/8/8/8/4K3 b kq - 0 1','e8c8',2),('7k/8/8/3pP3/8/8/8/6K1 w - d6 0 2','e5d6',1),('7k/P7/8/8/8/8/8/6K1 w - - 0 1','a7a8n',1)])
def test_explicit_shared_motion_and_cancel_keep_actual_position(page,site,fen,uci,count):
    login(page,site);b=chess.Board(fen);b.push_uci(uci);after=b.fen()
    page.evaluate("""()=>{tab('play');const b=document.createElement('div');b.id='motionFixture';b.className='board';b.style.width='320px';document.querySelector('#play').prepend(b);window.animationsSeen=[];const original=Element.prototype.animate;Element.prototype.animate=function(k,o){animationsSeen.push(o);return original.call(this,k,{...o,duration:2000});};}""")
    args={'before':fen,'after':after,'uci':uci,'flip':fen.split()[1]=='b'}
    n=page.evaluate("""r=>{drawBoard('motionFixture',fromFen(r.before),{flip:r.flip});cmaBoardPresentation.transition('motionFixture',r.uci,()=>drawBoard('motionFixture',fromFen(r.after),{flip:r.flip}));drawBoard('motionFixture',fromFen(r.after),{flip:r.flip});return document.querySelectorAll('.cma-motion-ghost').length;}""",args)
    assert n==count
    assert all(x['duration']==210 for x in page.evaluate('animationsSeen'))
    page.set_viewport_size({'width':390,'height':844})
    expect(page.locator('.cma-motion-ghost')).to_have_count(0)
    assert page.locator('#motionFixture .piece-wrap[style*="opacity: 0"]').count()==0
    # Reverse is explicit and validated; replacement without a move never animates.
    assert page.evaluate("""r=>{cmaBoardPresentation.transition('motionFixture',r.uci,()=>drawBoard('motionFixture',fromFen(r.before),{flip:r.flip}),true);return document.querySelectorAll('.cma-motion-ghost').length;}""",args)==count
    page.evaluate("drawBoard('motionFixture',fromFen(chessStart))")
    expect(page.locator('.cma-motion-ghost')).to_have_count(0)
    page.emulate_media(reduced_motion='reduce')
    assert page.evaluate("""r=>{drawBoard('motionFixture',fromFen(r.before));cmaBoardPresentation.transition('motionFixture',r.uci,()=>drawBoard('motionFixture',fromFen(r.after)));return document.querySelectorAll('.cma-motion-ghost').length;}""",args)==0


def test_current_check_label_cleanup_and_opening_history_motion(page,site):
    login(page,site);page.evaluate("tab('opening')")
    expect(page.locator('#studyCourse option')).to_have_count(55)
    page.locator('#studyCourse').select_option('london-core')
    expect(page.locator('#studyOpeningBoard .sq:enabled')).to_have_count(64)
    page.evaluate("""()=>{window.motionCalls=[];const original=cmaBoardPresentation.transition;cmaBoardPresentation.transition=(id,u,paint,reverse=false)=>{motionCalls.push({id,u,reverse});return original(id,u,paint,reverse);};}""")
    click_move(page,'studyOpeningBoard','d2d4')
    expect(page.locator('#studyTools').get_by_role('button',name='이전 수',exact=True)).to_be_enabled()
    page.locator('#studyTools').get_by_role('button',name='이전 수',exact=True).click()
    expect(page.locator('#studyTools').get_by_role('button',name='되돌린 수 복원',exact=True)).to_be_enabled()
    assert any(x['u']=='d2d4' and x['reverse'] for x in page.evaluate('motionCalls'))
    page.evaluate("drawBoard('studyOpeningBoard',fromFen('4k3/8/8/8/8/8/2K1r3/4R3 w - - 0 1'))")
    expect(page.locator('#studyOpeningBoard .cma-check')).to_have_attribute('aria-label','c2 백 킹 · 체크 당한 킹')
    page.evaluate("drawBoard('studyOpeningBoard',fromFen(chessStart))")
    expect(page.locator('#studyOpeningBoard .cma-check')).to_have_count(0)
    page.evaluate("tab('home')")
    expect(page.locator('.cma-motion-ghost')).to_have_count(0)

def test_motion_account_tab_and_reduced_preference_cancel_without_writes(page,site):
    login(page,site);other=page.evaluate("async()=> (await api('/register','POST',{code:'MOTION-'+crypto.randomUUID().slice(0,8),pin:'local-motion-pin'})).token")
    page.evaluate("""()=>{tab('play');const original=Element.prototype.animate;Element.prototype.animate=function(k,o){return original.call(this,k,{...o,duration:2000});};window.runFixture=()=>{drawBoard('gameBoard',fromFen(chessStart));const p=fromFen(chessStart);p.e4=p.e2;delete p.e2;cmaBoardPresentation.transition('gameBoard','e2e4',()=>drawBoard('gameBoard',p));};}""")
    writes=[];page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
    page.evaluate('runFixture()');expect(page.locator('.cma-motion-ghost')).to_have_count(1)
    page.emulate_media(reduced_motion='reduce');expect(page.locator('.cma-motion-ghost')).to_have_count(0)
    page.emulate_media(reduced_motion='no-preference');page.evaluate('runFixture()')
    page.evaluate('identity=>{token=identity;}',other)
    expect(page.locator('.cma-motion-ghost')).to_have_count(0)
    assert page.locator('#gameBoard .piece-wrap[style*="opacity: 0"]').count()==0
    page.evaluate('runFixture()');page.evaluate("tab('home')")
    expect(page.locator('.cma-motion-ghost')).to_have_count(0)
    assert writes==[]


def test_two_ply_capture_reverse_and_fast_replacement_has_no_residual_ghost(page,site):
    login(page,site);page.evaluate("tab('play')")
    before='3q2k1/8/8/3p4/2B5/8/8/6K1 w - - 0 1';b=chess.Board(before)
    for u in ['c4d5','d8d5']:b.push_uci(u)
    result=page.evaluate("""r=>{const original=Element.prototype.animate;Element.prototype.animate=function(k,o){return original.call(this,k,{...o,duration:2000});};drawBoard('gameBoard',fromFen(r.before));cmaBoardPresentation.transition('gameBoard',['c4d5','d8d5'],()=>drawBoard('gameBoard',fromFen(r.after)));const forward=document.querySelectorAll('.cma-motion-ghost').length;cmaBoardPresentation.transition('gameBoard',['c4d5','d8d5'],()=>drawBoard('gameBoard',fromFen(r.before)),true);return {forward,reverse:document.querySelectorAll('.cma-motion-ghost').length};}""",{'before':before,'after':b.fen()})
    assert result=={'forward':2,'reverse':2}
    page.evaluate('cmaBoardPresentation.cancelAll()')
    expect(page.locator('.cma-motion-ghost')).to_have_count(0)
    assert page.locator('#gameBoard .piece-wrap[style*="opacity: 0"]').count()==0

@pytest.mark.parametrize('width',[390,1280])
def test_real_opening_api_checkmate_display_and_black_orientation_capture(page,site,width):
    from pathlib import Path
    page.set_viewport_size({'width':width,'height':900});login(page,site);page.evaluate("tab('opening')")
    expect(page.locator('#studyOpeningBoard .sq:enabled')).to_have_count(64)
    for u in ['e2e4','e7e5','f1c4','b8c6','d1h5','g8f6','h5f7']:
        click_move(page,'studyOpeningBoard',u)
        if u!='h5f7':expect(page.locator('#studyOpeningBoard .sq:enabled')).to_have_count(64)
    expect(page.locator('#studyOpeningBoard .cma-check')).to_have_attribute('aria-label','e8 흑 킹 · 체크 당한 킹')
    expect(page.locator('#studyOpeningBoard .sq:enabled')).to_have_count(0)
    page.get_by_label('오프닝 보드 방향',exact=True).select_option('black')
    expect(page.locator('#studyOpeningBoard .sq').first).to_have_attribute('aria-label','h1 백 룩')
    expect(page.locator('.cma-motion-ghost')).to_have_count(0)
    out=Path('/tmp/cma-shared-board-captures');out.mkdir(exist_ok=True)
    page.screenshot(path=str(out/f'opening-checkmate-black-{width}.png'),full_page=True)
