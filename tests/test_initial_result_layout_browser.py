"""Synthetic compatible baseline via GET double; real SVG/DOM at mobile sizes."""
import pytest
from playwright.sync_api import expect
from test_redesign_browser_followup import isolated,site
from test_visual_evidence_browser import guest
from test_initial_profile import real_rows,report
from initial_profile import initialize,freeze,status


@pytest.mark.parametrize('width',[360,390])
def test_initial_result_chart_labels_and_training_primary(isolated,width):
    page,_=isolated;page.set_viewport_size({'width':width,'height':844});guest(page)
    rows=real_rows()
    for row in rows:row['outcome']='completed'
    r=report(rows);state={'results':[r],'active':None};initialize(state,r['corpus_sha256']);freeze(state,'fixture');state['initial_profile']['reviewed_at']='fixture'
    view=page.evaluate("api('/journey')");view['initial_profile']=status(state)
    page.route('**/api/journey',lambda route:route.fulfill(json=view))
    page.evaluate("cmaNavigation.go('diagnosis/initial')")
    expect(page.locator('#initialProfile > button')).to_have_text('맞춤 훈련 시작')
    expect(page.locator('#initialProfile')).to_contain_text('추가 출제 종료')
    assert page.evaluate('''() => {const rects=[...document.querySelectorAll('#initialProfile svg text')].map(x=>x.getBoundingClientRect());return rects.length===12 && rects.every((a,i)=>rects.every((b,j)=>i===j||a.right<=b.left||b.right<=a.left||a.bottom<=b.top||b.bottom<=a.top));}''')
    page.locator('#initialProfile > button').focus();expect(page.locator('#initialProfile > button')).to_be_focused()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    if width==390:page.screenshot(path='/tmp/cma-initial-captures/result-layout-390.png',full_page=True)
