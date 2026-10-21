from pathlib import Path
from playwright.sync_api import expect
from test_qa_browser import page,site,CATALOG


def test_catalog_state_captures(page,site):
    out=Path('/tmp/pr29-catalog-captures');out.mkdir(exist_ok=True)
    reads=[];page.unroute('**/api/v9/catalog');page.route('**/api/v9/catalog',lambda r:reads.append(r))
    with page.expect_request('**/api/v8/recommendations'):page.goto(site[0])
    for _ in range(300):
        if len(reads)>=2:break
        page.wait_for_timeout(20)
    assert len(reads)==2
    page.evaluate("tab('puzzle')")
    def capture(phase):
        for w,h in [(390,844),(1280,720)]:
            page.set_viewport_size({'width':w,'height':h});page.evaluate('scrollTo(0,0)')
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(out/f'{phase}-{w}.png'),full_page=True)
    expect(page.locator('#v9PuzzleStart')).to_be_disabled();capture('loading')
    for read in reads[:]:read.fulfill(status=503,json={'detail':'목록 조회 실패'})
    expect(page.locator('#v9CatalogRetry')).to_be_visible();capture('error')
    page.locator('#v9CatalogRetry').click();page.wait_for_timeout(100)
    reads[2].fulfill(json=CATALOG)
    expect(page.locator('#v9PuzzleStart')).to_be_enabled();capture('ready')
