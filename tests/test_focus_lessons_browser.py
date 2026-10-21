from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import page,site

@pytest.mark.parametrize('mode',['education','repertoire'])
@pytest.mark.parametrize('width',[390,1280])
def test_lesson_board_first_and_scope_is_readonly(page,site,mode,width):
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.set_viewport_size({'width':width,'height':900})
 if mode=='education':
  from test_education_browser import enter,start
  enter(page,site);start(page)
  host='educationPaths';body='educationBody';board='educationBoard';api='/education'
 else:
  from test_repertoire_browser import enter,select_start
  enter(page,site);select_start(page)
  host='repertoire';body='repertoireBody';board='repertoireBoard';api='/repertoire'
 expect(page.locator('#'+host)).to_have_class(__import__('re').compile('focus-lesson-active'))
 box=page.locator('#'+board).bounding_box()
 assert box['y']<400 and box['y']+box['height']<=900
 assert not errors,errors
 assert '다시 확인하세요' not in page.locator('#'+('educationStatus' if mode=='education' else 'repertoireStatus')).text_content()
 before=page.evaluate('path=>window.api(path)',api);writes=[]
 page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
 panel=page.locator('#'+host+'FocusScope');panel.locator('summary').first.click()
 expect(panel).to_have_attribute('open','')
 panel.press('Escape');expect(panel).not_to_have_attribute('open','');expect(panel.locator('summary').first).to_be_focused()
 assert page.evaluate('path=>window.api(path)',api)==before and writes==[]
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
 page.screenshot(path=f'docs/qa-focus-interface/captures/{mode}-focused-{width}.png',full_page=True)
