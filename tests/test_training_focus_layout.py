"""Saved local training, normal Chromium. No production account use."""
import json,os
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import page,site
from test_study_browser import login

@pytest.mark.parametrize('width,height,zoom',[(1180,757,1),(1280,720,1),(390,844,1),(320,844,1),(1280,720,2)])
def test_saved_training_core_actions_layout_and_preservation(page,site,width,height,zoom):
 page.set_viewport_size({'width':width,'height':height})
 login(page,site)
 page.evaluate("api('/learning/start','POST',{fresh:true})")
 page.reload();page.evaluate("tab('training')")
 expect(page.locator('#learningBoard .sq')).to_have_count(64)
 expect(page.locator('#learningBoardFeedback')).to_be_visible()
 if zoom!=1:page.evaluate('z=>document.documentElement.style.zoom=z',str(zoom))
 page.evaluate('document.fonts.ready');page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
 before=page.evaluate("api('/learning/dashboard')")['active']
 writes=[];page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
 boxes={k:page.locator('#'+k).bounding_box() for k in ['learningBoard','learningBoardFeedback','learningControls']}
 out=Path('docs/qa-training-focus');out.mkdir(exist_ok=True)
 tag=os.environ.get('CMA_CAPTURE_TAG','after')+f'-{width}-{height}-zoom{zoom}'
 (out/(tag+'.json')).write_text(json.dumps(boxes,indent=2))
 page.screenshot(path=str(out/(tag+'.png')),full_page=True)
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
 assert boxes['learningBoard']['width']>=280
 if zoom==1:
  for key,box in boxes.items():assert box['y']>=0 and box['y']+box['height']<=height,(key,boxes)
 if width>=1180 and zoom==1:
  assert boxes['learningBoardFeedback']['x']>=boxes['learningBoard']['x']+boxes['learningBoard']['width']
 for control in page.locator('#learningControls button').all():
  control.scroll_into_view_if_needed();box=control.bounding_box()
  assert box['height']>=44
  assert control.evaluate('(e)=>{const b=e.getBoundingClientRect();return e.contains(document.elementFromPoint(b.x+b.width/2,b.y+b.height/2));}')
 hint=page.locator('#learningControls').get_by_role('button',name='힌트 1단계',exact=True)
 hint.focus();expect(hint).to_be_focused()
 assert hint.evaluate("e=>getComputedStyle(e).outlineStyle")!='none'
 # Panel switching is navigation only; retained saved task and help count must be identical.
 page.get_by_role('button',name='훈련 선택 · 저장 활동 · 기록',exact=True).click()
 page.get_by_role('button',name='현재 훈련 이어하기',exact=True).click()
 expect(page.locator('#learningBoard')).to_be_visible();expect(page.locator('#learningTitle')).to_be_focused()
 assert page.evaluate("api('/learning/dashboard')")['active']==before
 assert not writes
