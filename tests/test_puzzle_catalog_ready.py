"""Catalogue is public/read-only; submission waits for readiness without queued writes."""
import uuid
import pytest
from playwright.sync_api import expect
from test_qa_browser import page,site

@pytest.mark.parametrize('failure',['http','unavailable'])
def test_delayed_catalog_blocks_submit_and_supports_explicit_retry(page,site,failure):
    page.unroute('**/api/v9/catalog')
    reads=[];writes=[]
    page.route('**/api/v9/catalog',lambda r:reads.append(r))
    page.on('request',lambda r:writes.append(r) if r.method=='POST' and '/v9/puzzle/start' in r.url else None)
    page.goto(site[0]);page.evaluate("tab('puzzle')")
    expect(page.locator('#v9PuzzleStart')).to_be_disabled()
    expect(page.locator('#v9CatalogStatus')).to_contain_text('불러오는 중')
    page.locator('#v9PuzzleStart').evaluate('(e)=>e.onclick()');page.wait_for_timeout(100)
    assert not writes
    if failure=='http':reads[0].fulfill(status=503,json={'detail':'목록 조회 실패'})
    else:reads[0].fulfill(json={'ready':False,'count':0,'themes':[],'levels':['입문','중급','고급']})
    expect(page.locator('#v9CatalogRetry')).to_be_visible()
    expect(page.locator('#v9PuzzleStart')).to_be_disabled()
    page.locator('#v9CatalogRetry').click()
    page.locator('#v9CatalogRetry').evaluate('(e)=>e.onclick()')
    page.wait_for_timeout(100);assert len(reads)==2
    reads[1].continue_()
    expect(page.locator('#v9PuzzleStart')).to_be_enabled()
    assert not writes  # No postponed start after the read succeeds.
    page.locator('#v9PuzzleTheme').select_option('fork');page.locator('#v9PuzzleLevel').select_option('입문')
    with page.expect_response('**/api/v9/puzzle/start') as response:page.locator('#v9PuzzleStart').click()
    assert response.value.status==200
    assert response.value.request.post_data_json=={'theme':'fork','level':'입문'}
    expect(page.locator('#v9PuzzleBoardFeedback')).to_contain_text('직접 풀어보세요')
    assert len(writes)==1


def test_late_public_catalog_after_account_change_preserves_b_restored_task(page,site):
    code='CATALOG-'+uuid.uuid4().hex[:10].upper();pin='catalog-test-pin'
    b=page.request.post(site[0]+'/api/register',data={'code':code,'pin':pin}).json()
    task=page.request.post(site[0]+'/api/v9/puzzle/start',headers={'Authorization':'Bearer '+b['token']},data={'theme':'random','level':'중급'}).json()
    page.unroute('**/api/v9/catalog');reads=[];writes=[]
    page.route('**/api/v9/catalog',lambda r:reads.append(r))
    page.on('request',lambda r:writes.append(r) if r.method=='POST' and '/v9/puzzle/start' in r.url else None)
    page.goto(site[0]);page.evaluate("tab('profile')")
    page.locator('#codeField').fill(code);page.locator('#pinField').fill(pin);page.locator('#signin').click()
    page.wait_for_function('c=>user?.code===c',arg=code);expect(page.locator('#signin')).to_be_enabled()
    page.evaluate("tab('puzzle')")
    expect(page.locator('#v9PuzzleBoard .sq:enabled')).to_have_count(64)
    before=page.locator('#v9PuzzleMessage').inner_text()
    expect(page.locator('#v9PuzzleStart')).to_be_disabled()
    reads[0].continue_()
    expect(page.locator('#v9PuzzleStart')).to_be_enabled()
    expect(page.locator('#v9PuzzleMessage')).to_have_text(before)
    current=page.evaluate("api('/v9/session/puzzle')")
    assert current['session_id']==task['session_id'] and current['fen']==task['fen']
    assert not writes
