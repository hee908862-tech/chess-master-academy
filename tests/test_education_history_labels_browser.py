"""Display-only history localization, using controlled read responses."""
import copy
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page,open_page

@pytest.mark.parametrize('width',[393,1280])
def test_history_modes_localized_without_writes_or_unknown_inference(page,site,width):
    rows=[dict(id=str(i),title='보관 예시 '+str(i),mode=mode,phase='stopped',hints=1,misses=2)
          for i,mode in enumerate(['learn','review','legacy',None,'__proto__'])]
    data=dict(revision=7,active=None,can_start=True,metrics={},catalog=[],history=rows)
    original=copy.deepcopy(data);writes=[]
    page.route('**/api/education',lambda r:r.fulfill(json=data))
    page.on('request',lambda r:writes.append(r.post_data) if '/api/education/action' in r.url else None)
    page.set_viewport_size(dict(width=width,height=900));open_page(page,site)
    page.evaluate('cmaEducation.open()')
    expect(page.locator('#educationPaths')).to_have_attribute('aria-busy','false')
    history=page.locator('#educationBody details').last
    history.locator('summary').click()
    paragraphs=history.locator(':scope > p')
    expect(paragraphs).to_have_text([
        f'보관 예시 {i} · {label} · 중단 · 도움 1 · 다른 응답 2'
        for i,label in reversed(list(enumerate(['학습','복습','학습 방식 미기록','학습 방식 미기록','학습 방식 미기록'])))])
    if not page.locator('#educationPaths').get_by_role('button',name='저장 상태 다시 확인',exact=True).is_visible():page.locator('#educationPathsFocusScope > summary').click()
    page.locator('#educationPaths').get_by_role('button',name='저장 상태 다시 확인',exact=True).click()
    expect(page.locator('#educationPaths')).to_have_attribute('aria-busy','false')
    assert page.evaluate("api('/education')")==original
    assert writes==[] and data==original
