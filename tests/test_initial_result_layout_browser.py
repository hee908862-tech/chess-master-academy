"""Synthetic compatible baseline via GET double; real SVG/DOM at mobile sizes."""
import pytest
from pathlib import Path
from playwright.sync_api import expect
from test_redesign_browser_followup import isolated,site
from test_visual_evidence_browser import guest
from test_initial_profile import real_rows,report
from initial_profile import initialize,freeze,status


@pytest.mark.parametrize('width',[360,390])
def test_initial_result_chart_labels_and_training_primary(isolated,width):
    page,_=isolated;page.set_viewport_size({'width':width,'height':844})
    page.evaluate("cmaNavigation.go('diagnosis/initial')")
    page.get_by_role('button',name='로그인 없이 초기 진단 시작',exact=True).click()
    page.wait_for_function('!!token && !cmaJourney.status().busy')
    expect(page.locator('#initialProfile > button').first).to_have_text('진단 이어하기 · 남은 분야 바로 풀기')
    rows=real_rows()
    for row in rows:row['outcome']='completed'
    r=report(rows);state={'results':[r],'active':None};initialize(state,r['corpus_sha256']);freeze(state,'fixture');state['initial_profile']['reviewed_at']='fixture'
    view=page.evaluate("api('/journey')");view['initial_profile']=status(state)
    writes=[]
    page.on('request',lambda request:writes.append(request.url) if request.method=='POST' else None)
    page.route('**/api/journey',lambda route:route.fulfill(json=view))
    page.evaluate("cmaNavigation.go('diagnosis/initial')")
    # Fetch the synthetic baseline after the real guest bootstrap has settled.
    expect(page.locator('#journeyRefresh')).to_be_enabled()
    with page.expect_response('**/api/journey'):
        page.locator('#journeyRefresh').click()
    expect(page.locator('#initialProfile > button')).to_have_text('맞춤 훈련 시작')
    expect(page.locator('#initialProfile')).to_contain_text('추가 출제 종료')
    assert page.evaluate('''() => {const rects=[...document.querySelectorAll('#initialProfile svg text')].map(x=>x.getBoundingClientRect());return rects.length===12 && rects.every((a,i)=>rects.every((b,j)=>i===j||a.right<=b.left||b.right<=a.left||a.bottom<=b.top||b.bottom<=a.top));}''')
    page.locator('#initialProfile > button').focus();expect(page.locator('#initialProfile > button')).to_be_focused()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    assert not writes
    if width==390:
        Path('/tmp/cma-initial-captures').mkdir(exist_ok=True)
        page.screenshot(path='/tmp/cma-initial-captures/result-layout-390.png',full_page=True)
