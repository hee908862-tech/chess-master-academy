"""Real local API state; never uses an operational account."""
import pytest
from playwright.sync_api import expect
from foundation_content import COURSES
from test_qa_browser import site,page
from test_study_browser import login

@pytest.mark.parametrize('width',[390,1180])
@pytest.mark.parametrize('progress',['new','active','between','complete','review'])
def test_home_label_destination_and_no_mutation(page,site,width,progress):
    login(page,site);page.set_viewport_size({'width':width,'height':844})
    def api(path,body=None):return page.evaluate('([p,b])=>b===null?api(p):api(p,"POST",b)',[path,body])
    state=api('/foundations')
    def action(kind,course,value=''):
        nonlocal state
        state=api('/foundations/action',dict(action=kind,course_id=course,revision=state['revision'],step=(state.get('active') or {}).get('step',0),value=value))
    if progress!='new':
        for course in (COURSES if progress in ('complete','review') else COURSES[:1]):
            action('start',course['id'])
            if progress=='active':break
            for i,step in enumerate(course['steps']):
                if step['kind']=='judge':action('answer',course['id'],step['answer'])
                else:
                    for move in step['line'][::2]:action('move',course['id'],move)
                if i+1<len(course['steps']):action('next',course['id'])
    if progress=='review':action('review',COURSES[0]['id'])
    # Preserve a separate in-flight diagnosis as well as foundation records.
    api('/journey/start',{'mode':'quick'})
    before=api('/foundations');diagnosis=api('/journey');me=api('/me')
    page.evaluate("tab('home')")
    label={'new':'기초 배우기 시작','active':'이어서 배우기','between':'이어서 배우기','complete':'기초 복습하기','review':'이어서 배우기'}[progress]
    expect(page.locator('#homeBasicsOpen')).to_have_text(label)
    page.reload();expect(page.locator('#homeBasicsOpen')).to_have_text(label)
    writes=[];page.on('request',lambda r:writes.append(r.url) if r.method not in ('GET','HEAD') else None)
    page.locator('#homeBasicsOpen').click()
    expect(page).to_have_url(__import__('re').compile('#learn/basics'+('/practice' if progress in ('active','review') else '')+'$'))
    if progress in ('active','review'):expect(page.locator('#foundationWorkspace')).to_be_visible()
    elif progress=='complete':
        expect(page.locator('#foundationCourseList')).to_be_visible()
        expect(page.locator('#foundationCards').get_by_role('button',name='다시 복습',exact=True)).to_have_count(10)
        expect(page.locator('#foundationWorkspace')).to_be_hidden()
    else:expect(page.locator('#foundationPrimary')).to_be_visible()
    assert api('/foundations')==before and api('/journey')==diagnosis and api('/me')==me
    assert writes==[]
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
