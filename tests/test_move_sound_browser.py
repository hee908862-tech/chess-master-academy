"""Local Chromium event/audio-node checks, not physical speaker/device listening."""
import chess
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page
from test_study_browser import login


def fixture(page,site):
    login(page,site)
    page.evaluate("""()=>{tab('play');const host=document.createElement('div');host.id='soundFixture';host.className='board';host.style.width='320px';document.querySelector('#play').prepend(host);window.soundCalls=[];window.originalMoveSound=playMoveSound;playMoveSound=kind=>soundCalls.push(kind);}""")


@pytest.mark.parametrize('fen,move',[(chess.STARTING_FEN,'e2e4'),('4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1','e1g1'),('7k/8/8/3pP3/8/8/8/6K1 w - d6 0 2','e5d6'),('7k/P7/8/8/8/8/8/6K1 w - - 0 1','a7a8n')])
def test_applied_sound_once_and_reverse_not_selection_or_invalid(page,site,fen,move):
    fixture(page,site);page.emulate_media(reduced_motion='reduce')
    board=chess.Board(fen);board.push_uci(move)
    page.evaluate("""r=>{drawBoard('soundFixture',fromFen(r.before));drawBoard('soundFixture',fromFen(r.before),{selected:r.u.slice(0,2)});cmaBoardPresentation.transition('soundFixture',r.u,()=>drawBoard('soundFixture',fromFen(r.before)));}""",{'before':fen,'u':move})
    assert page.evaluate('soundCalls.length')==0
    args={'before':fen,'after':board.fen(),'u':move}
    page.evaluate("""r=>{cmaBoardPresentation.transition('soundFixture',r.u,()=>drawBoard('soundFixture',fromFen(r.after)));drawBoard('soundFixture',fromFen(r.after));cmaBoardPresentation.transition('soundFixture',r.u,()=>drawBoard('soundFixture',fromFen(r.after)));}""",args)
    assert page.evaluate('soundCalls.length')==1
    page.evaluate("r=>cmaBoardPresentation.transition('soundFixture',r.u,()=>drawBoard('soundFixture',fromFen(r.before)),true)",args)
    assert page.evaluate('soundCalls.length')==2
    expect(page.locator('.cma-motion-ghost')).to_have_count(0)


def test_two_plies_single_castling_tap_and_pending_sound_cancel(page,site):
    fixture(page,site);page.emulate_media(reduced_motion='reduce')
    page.evaluate("""()=>{window.runSoundBatch=()=>{drawBoard('soundFixture',fromFen(chessStart));const a=fromFen(chessStart);a.e4=a.e2;delete a.e2;a.e5=a.e7;delete a.e7;cmaBoardPresentation.transition('soundFixture',['e2e4','e7e5'],()=>drawBoard('soundFixture',a));};runSoundBatch();}""")
    page.wait_for_function('soundCalls.length===2')
    page.evaluate("runSoundBatch();cmaBoardPresentation.cancelAll()")
    page.wait_for_timeout(260)
    assert page.evaluate('soundCalls.length')==3
    page.evaluate("runSoundBatch();token='different-local-test-identity'")
    page.wait_for_timeout(260)
    assert page.evaluate('soundCalls.length')==4


def test_mute_volume_and_browser_audio_block_do_not_queue_or_reset(page,site):
    login(page,site)
    page.evaluate("""()=>{window.oscillators=0;window.gains=[];window.makeAudio=state=>({state,currentTime:0,resume:()=>Promise.reject(Error('blocked')),createOscillator(){oscillators++;return {frequency:{setValueAtTime(){},linearRampToValueAtTime(){}},connect(){return {connect(){}}},start(){},stop(){}}},createGain(){return {gain:{setValueAtTime(){},linearRampToValueAtTime(v){gains.push(v)},exponentialRampToValueAtTime(){}},connect(){}}}});audioCtx=makeAudio('suspended');prefs.soundOn=true;playMoveSound();}""")
    assert page.evaluate('oscillators')==0
    page.evaluate("audioCtx=makeAudio('running');prefs.soundOn=false;playMoveSound();prefs.soundOn=true;prefs.soundVolume=0;playMoveSound()")
    assert page.evaluate('oscillators')==0
    page.evaluate("prefs.soundVolume=50;playMoveSound()")
    assert page.evaluate('oscillators')==2
    assert page.evaluate('Math.max(...gains)')==pytest.approx(.06)
    page.evaluate("cmaNavigation.go('settings')")
    # Settings exist in the account section and are moved by the navigation layer.
    volume=page.locator('#soundVolume');expect(volume).to_be_attached()
    page.evaluate("document.querySelector('#soundVolume').value='35';document.querySelector('#soundVolume').dispatchEvent(new Event('input'));prefs.soundOn=false;savePrefs();token='another-local-identity';resetGameAccount()")
    assert page.evaluate("JSON.parse(localStorage.getItem('cma_prefs')).soundVolume") == 35
    assert page.evaluate('prefs.soundOn') is False
    # A fresh page avoids the fixture's per-page init script resetting preferences.
    restored_context=page.context.browser.new_context(storage_state=page.context.storage_state());restored=restored_context.new_page();restored.goto(site[0]);restored.wait_for_function('typeof prefs!=="undefined"')
    assert restored.evaluate('prefs.soundVolume')==35
    assert restored.evaluate('prefs.soundOn') is False
    assert restored.locator('#soundVolume').input_value()=='35'
    restored_context.close()


def test_real_opening_move_and_undo_sound_without_selection_sound(page,site):
    from test_study_browser import click_move
    login(page,site);page.evaluate("tab('opening')")
    expect(page.locator('#studyCourse option')).to_have_count(55)
    page.locator('#focusOpeningSelection > summary').click()
    page.locator('#studyCourse').select_option('london-core')
    expect(page.locator('#studyOpeningBoard .sq:enabled')).to_have_count(64)
    page.evaluate("window.soundCalls=[];playMoveSound=(kind,context)=>{if(context?.board==='studyOpeningBoard')soundCalls.push(kind)}")
    page.locator('#studyOpeningBoard [aria-label^="d2 "]').click()
    assert page.evaluate('soundCalls.length')==0
    page.locator('#studyOpeningBoard [aria-label^="d4 "]').click()
    expect(page.locator('#studyTools').get_by_role('button',name='이전 수',exact=True)).to_be_enabled()
    assert page.evaluate('soundCalls.length')==1
    page.locator('#studyTools').get_by_role('button',name='이전 수',exact=True).click()
    expect(page.locator('#studyTools').get_by_role('button',name='되돌린 수 복원',exact=True)).to_be_enabled()
    assert page.evaluate('soundCalls.length')==2


def test_replay_adjacent_and_autoplay_emit_once_without_writes(page,site):
    login(page,site);board=chess.Board();before=board.fen();board.push_uci('e2e4')
    source={'available':True,'side':'white','basis':'기준 수순','frames':[{'fen':before,'san':'시작','facts':{}},{'fen':board.fen(),'san':'e4','move':'e2e4','facts':{}}]}
    page.evaluate("""data=>{tab('play');window.soundCalls=[];playMoveSound=kind=>soundCalls.push(kind);const host=document.createElement('section');host.id='soundReplayHost';document.querySelector('#play').prepend(host);cmaDiagnosticReplay(host,data);}""",source)
    writes=[];page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
    host=page.locator('#soundReplayHost');host.locator('summary').click()
    expect(host.locator('.board .sq')).to_have_count(64)
    assert page.evaluate('soundCalls.length')==0
    host.get_by_role('button',name='다음 수',exact=True).click()
    assert page.evaluate('soundCalls.length')==1
    host.get_by_role('button',name='이전 수',exact=True).click()
    assert page.evaluate('soundCalls.length')==2
    host.get_by_role('button',name='재생',exact=True).click()
    page.wait_for_function('soundCalls.length===3')
    expect(host.get_by_role('button',name='재생',exact=True)).to_be_visible()
    assert not writes


def test_closed_explanation_board_is_silent(page,site):
    fixture(page,site)
    page.evaluate("""()=>{const d=document.createElement('details');document.querySelector('#play').prepend(d);d.append(document.querySelector('#soundFixture'));drawBoard('soundFixture',fromFen(chessStart));const a=fromFen(chessStart);a.e4=a.e2;delete a.e2;cmaBoardPresentation.transition('soundFixture','e2e4',()=>drawBoard('soundFixture',a));}""")
    assert page.evaluate('soundCalls.length')==0
