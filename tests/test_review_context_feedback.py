"""Read-only review selection / analysis / navigation keeps contextual labels aligned."""
import chess
from playwright.sync_api import expect
from test_qa_browser import page,site,open_page


def test_loaded_review_context_survives_history_refresh_and_tab_return(page,site):
    open_page(page,site)
    writes=[];page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
    page.route('**/api/games/history',lambda r:r.fulfill(json=[{'index':0,'color':'white','plies':2,'result':'draw'}]))
    b=chess.Board();rows=[]
    for side,u in [('백','e2e4'),('흑','c7c6')]:
        san=b.san(chess.Move.from_uci(u));b.push_uci(u)
        rows.append(dict(uci=u,san=san,side=side,after_fen=b.fen(),centipawn_loss=0,category='참고',comment='원본 해설',source='검사'))
    original={'color':'white','moves':rows}
    page.route('**/api/games/review/0',lambda r:r.fulfill(json=original))
    page.evaluate("tab('review')")
    expect(page.locator('#reviewLoad')).to_be_enabled()
    expect(page.locator('#reviewStatus')).to_have_text('대국을 선택한 뒤 분석하세요.')
    page.locator('#reviewLoad').click()
    expect(page.locator('#reviewBranchStatus')).to_contain_text('원본 0 / 2 반수')
    page.locator('#reviewNext').click()
    expect(page.locator('#reviewBranchStatus')).to_contain_text('원본 1 / 2 반수')
    expect(page.locator('#reviewStatus')).to_contain_text('백 e4')
    page.evaluate("tab('home');tab('review')")
    expect(page.locator('#reviewLoad')).to_be_enabled()
    expect(page.locator('#reviewStatus')).to_contain_text('백 e4')
    expect(page.locator('#reviewBranchStatus')).to_contain_text('원본 1 / 2 반수')
    assert page.evaluate('v5ReviewIndex')==1
    assert page.evaluate('v5Review')==original
    assert not writes
