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


import pytest
@pytest.mark.parametrize('late_error',[False,True])
def test_review_owner_changes_on_real_login_and_late_analysis_is_ignored(page,site,late_error):
    import uuid
    open_page(page,site)
    code='REVIEW-'+uuid.uuid4().hex[:10].upper();pin='local-review-pin'
    account=page.request.post(site[0]+'/api/register',data={'code':code,'pin':pin}).json()
    a=chess.Board();a.push_uci('e2e4')
    b=chess.Board();b.push_uci('d2d4')
    def analysis(move,fen,label):
        return {'color':'white','moves':[dict(uci=move,san=label,side='백',after_fen=fen,centipawn_loss=0,category='참고',comment=label+' 원본',source='검사')]}
    original=analysis('e2e4',a.fen(),'e4');other=analysis('d2d4',b.fen(),'d4')
    page.route('**/api/games/history',lambda r:r.fulfill(json=[dict(index=0,color='white',plies=1,result='draw')]))
    pending=[];a_calls=[]
    def review(r):
        if r.request.headers.get('authorization')=='Bearer '+site[1]:
            a_calls.append(1)
            if len(a_calls)==1:r.fulfill(json=original)
            else:pending.append(r)
        else:r.fulfill(json=other)
    page.route('**/api/games/review/0',review)
    page.evaluate("tab('review')");expect(page.locator('#reviewLoad')).to_be_enabled();page.locator('#reviewLoad').click()
    expect(page.locator('#reviewMoves button')).to_have_count(1)
    page.locator('#reviewNext').click();expect(page.locator('#reviewStatus')).to_contain_text('e4')
    page.locator('#reviewLoad').click()
    for _ in range(100):
        if pending:break
        page.wait_for_timeout(20)
    assert pending
    page.evaluate("tab('profile/account')");page.locator('#codeField').fill(code);page.locator('#pinField').fill(pin);page.locator('#signin').click()
    page.wait_for_function('code=>user?.code===code',arg=code)
    expect(page.locator('#signin')).to_be_enabled()
    page.evaluate("tab('review')");expect(page.locator('#reviewLoad')).to_be_enabled()
    assert page.evaluate('v5Review') is None
    expect(page.locator('#reviewBoard .sq')).to_have_count(0)
    expect(page.locator('#reviewMoves button')).to_have_count(0)
    expect(page.locator('#reviewStatus')).to_have_text('대국을 선택한 뒤 분석하세요.')
    page.locator('#reviewLoad').click();expect(page.locator('#reviewMoves button')).to_have_count(1)
    page.locator('#reviewNext').click();expect(page.locator('#reviewStatus')).to_contain_text('d4')
    pending[0].fulfill(status=503,json={'detail':'A 분석 실패'}) if late_error else pending[0].fulfill(json=original)
    page.wait_for_timeout(100)
    assert page.evaluate('v5Review')==other
    assert page.evaluate('v5ReviewIndex')==1
    expect(page.locator('#reviewStatus')).to_contain_text('d4')
    expect(page.locator('#reviewBranchStatus')).to_contain_text('원본 1 / 1')
