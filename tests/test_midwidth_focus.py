"""500 CSS px is not interchangeable with a narrow 390 px viewport."""
import json,os
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import page,site
from test_focus_interface_browser import foundation
from test_study_browser import login

@pytest.mark.parametrize('mode',['foundation','training','guest'])
def test_midwidth_board_and_primary_completion_actions(page,site,mode):
 page.set_viewport_size({'width':500,'height':757})
 if mode=='foundation':
  foundation(page,site)
  page.locator('#foundationBoard [aria-label^="a1 "]').click();page.locator('#foundationBoard [aria-label^="a4 "]').click()
  expect(page.locator('#foundationOutcome')).to_contain_text('단계 완료')
  board='foundationBoard';actions=['foundationNext'];save='/foundations'
 elif mode=='training':
  login(page,site);page.evaluate("tab('training')");page.locator('#learningFresh').click()
  expect(page.locator('#learningBoard .sq')).to_have_count(64)
  page.locator('#learningControls').get_by_role('button',name='힌트 1단계',exact=True).click()
  expect(page.locator('#learningControls')).to_contain_text('힌트 2단계')
  board='learningBoard';actions=['learningControls'];save='/learning/dashboard'
 else:
  context=page.context.browser.new_context(viewport={'width':500,'height':757});page=context.new_page()
  page.goto(site[0]);page.locator('#flowFreeExamples > summary').click();page.locator('#firstEntry').get_by_role('button',name='기초·예제 퍼즐도 저장 없이 체험').click()
  page.get_by_role('button',name='비숍은 대각선으로',exact=True).click()
  page.locator('#guestBoard [aria-label^="c1 "]').click();page.locator('#guestBoard [aria-label^="g5 "]').click()
  expect(page.locator('#guestOutcome')).to_contain_text('실습 목표 확인')
  board='guestBoard';actions=['guestAgain','guestNext','guestContinue'];save=None
 expect(page.locator('.cma-motion-ghost')).to_have_count(0)
 page.evaluate('scrollTo(0,0)');page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
 ids=[board]+actions;boxes={i:page.locator('#'+i).bounding_box() for i in ids}
 tag=os.environ.get('CMA_CAPTURE_TAG','after')+'-500-'+mode
 out=Path('docs/qa-training-focus');out.mkdir(exist_ok=True)
 (out/(tag+'.json')).write_text(json.dumps(boxes,indent=2));page.screenshot(path=str(out/(tag+'.png')),full_page=True)
 assert boxes[board]['width']>=350,boxes
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
 for name,b in boxes.items():assert 0<=b['y'] and b['y']+b['height']<=757,(name,boxes)
 for name in actions:
  node=page.locator('#'+name);node=node.locator('button').first if name.endswith(('Next','Controls')) and name not in ['guestNext'] else node
  node.focus();expect(node).to_be_focused()
  assert node.evaluate('(e)=>{const b=e.getBoundingClientRect();return e.contains(document.elementFromPoint(b.x+b.width/2,b.y+b.height/2));}')
 # At a shorter height, preserve readable controls and accessible scrolling rather than forcing fit.
 page.set_viewport_size({'width':500,'height':650})
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
 for name in actions:
  node=page.locator('#'+name);node=node.locator('button').first if name in ['foundationNext','learningControls'] else node
  node.scroll_into_view_if_needed();b=node.bounding_box();assert b['height']>=44
  assert node.evaluate('(e)=>{const b=e.getBoundingClientRect();return e.contains(document.elementFromPoint(b.x+b.width/2,b.y+b.height/2));}')
 page.set_viewport_size({'width':500,'height':757})
 if save:
  before=page.evaluate('p=>api(p)',save);page.set_viewport_size({'width':390,'height':844});page.set_viewport_size({'width':500,'height':757})
  assert page.evaluate('p=>api(p)',save)==before
 else:context.close()
