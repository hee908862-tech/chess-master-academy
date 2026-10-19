from pathlib import Path
import chess
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page,open_page,TASK,FEN,square
from mate_explanation import explain_mate

@pytest.mark.parametrize('width,height,black',[(1366,768,False),(390,844,False),(390,844,True)])
def test_puzzle_mate_panel_next_and_reload(page,site,width,height,black):
 page.set_viewport_size({'width':width,'height':height})
 task={**TASK,'session_id':'mate'}
 if black:task.update(fen='8/8/8/8/8/4r3/5k2/1R5K b - - 0 1',legal=['e3h3'],side='black')
 move='e3h3' if black else 'd7d8q'
 b=chess.Board(task['fen']);b.push_uci(move);data=explain_mate(b)
 result={'solved':True,'correct':True,'done':True,'message':'해결','completed_fen':b.fen(),'mate_explanation':data}
 page.route('**/api/v9/puzzle/start',lambda r:r.fulfill(json=task))
 page.route('**/api/v9/puzzle/move',lambda r:r.fulfill(json=result))
 page.route('**/api/v9/session/puzzle',lambda r:r.fulfill(json={'active':False}))
 open_page(page,site);page.evaluate("tab('puzzle')");page.locator('#v9PuzzleStart').click()
 expect(page.locator('.mate-panel')).to_have_count(0)
 square(page,'v9PuzzleBoard',move[:2]).click();square(page,'v9PuzzleBoard',move[2:4]).click()
 if not black:page.locator('#cmaPromotionModal button').filter(has_text='퀸').click()
 panel=page.locator('.mate-panel');panel.locator('summary').click()
 expect(panel).to_contain_text('합법 대응 0개')
 assert panel.locator('.board .sq').first.get_attribute('aria-label').startswith('h1' if black else 'a8')
 panel.locator('.mate-choices button').filter(has_text='g1' if black else 'f8').click()
 expect(panel.locator('.mate-label').filter(has_text='통제')).not_to_have_count(0)
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 Path('/tmp/mate-shots').mkdir(exist_ok=True);panel.screenshot(path=f'/tmp/mate-shots/mate-{width}-{"black" if black else "white"}.png')
 page.route('**/api/v9/session/puzzle',lambda r:r.fulfill(json={'active':True,'session_id':'mate','result':result}))
 page.reload();page.evaluate("tab('puzzle')")
 expect(page.locator('.mate-panel')).to_have_count(1)
 page.locator('#v9PuzzleNext').click();expect(page.locator('.mate-panel')).to_have_count(0)

@pytest.mark.parametrize('correct',[True,False])
def test_diagnostic_feedback_gating_and_next(page,site,correct):
 b=chess.Board(FEN);b.push_uci('d7d8q')
 q={'id':0,'fen':FEN,'legal':['d7d8q'],'difficulty':1,'description':'메이트'}
 feedback={'correct':correct,'original_fen':FEN,'answer_fen':b.fen(),'answer':'d7d8q','domain':'메이트','difficulty':1,'seconds':1,'points':100,'mate_explanation':explain_mate(b)}
 page.route('**/api/v8/assessment/status',lambda r:r.fulfill(json={'active':True,'phase':'feedback','feedback':feedback,'index':0}))
 page.route('**/api/v8/assessment/next',lambda r:r.fulfill(json={'index':1,'domain':'메이트','question':q}))
 open_page(page,site);page.evaluate("tab('assessment')")
 expect(page.locator('.mate-panel')).to_have_count(1 if correct else 0)
 page.reload();page.evaluate("tab('assessment')");expect(page.locator('.mate-panel')).to_have_count(1 if correct else 0)
 page.locator('#v8Next').click();expect(page.locator('.mate-panel')).to_have_count(0)
