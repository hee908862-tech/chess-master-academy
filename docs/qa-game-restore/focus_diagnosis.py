import json
from pathlib import Path
from playwright.sync_api import expect
from test_education_browser import enter
from test_qa_browser import page,site

def test_prerequisite_delayed_read_focus_timeline(page,site):
 enter(page,site)
 page.evaluate('cmaFoundations.load()')
 before=page.evaluate("api('/foundations')")
 page.evaluate("""()=>{window.focusTrace=[];window.foundationRelease=null;window.foundationReads=0;window.focusWrites=[];
 const info=()=>({id:document.activeElement.id,tag:document.activeElement.tagName,course:document.activeElement.dataset.course||null});
 document.addEventListener('focusin',()=>focusTrace.push({event:'focus',...info()}));
 const original=api;api=async(...a)=>{if(a[1]==='POST')focusWrites.push(a[0]);if(a[0]==='/foundations'){foundationReads++;const r=await original(...a);return new Promise(resolve=>foundationRelease=()=>{focusTrace.push({event:'release',...info()});resolve(r);});}return original(...a);};
 window.focusInfo=info;}""")
 card=page.locator('#educationBody article').filter(has=page.get_by_role('heading',name='공격선 관찰과 피하기',exact=True))
 card.get_by_role('button',name='관련 기존 기초 보기',exact=True).click()
 expect(page.locator('#foundationCourseList')).to_have_attribute('open','')
 expect(page.locator('[data-course="king-check"]')).to_be_visible()
 page.wait_for_function('foundationRelease!==null')
 early=page.evaluate('focusInfo()')
 page.evaluate('foundationRelease()')
 expect(page.locator('[data-course="king-check"]')).to_be_focused()
 page.wait_for_timeout(300)
 result=page.evaluate('({early:null,final:focusInfo(),trace:focusTrace,reads:foundationReads,writes:focusWrites})');result['early']=early
 assert result['writes']==[]
 assert result['final']['course']=='king-check'
 # Restore the API before inspecting the authoritative unchanged state.
 # The read-only API wrapper deliberately holds subsequent reads too; use request directly.
 r=page.request.get(site[0]+'/api/foundations',headers={'Authorization':'Bearer '+page.evaluate('token')})
 assert r.json()==before
 Path('/tmp/pr29-focus-timeline.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(json.dumps(result,ensure_ascii=False))
