"""Normal Chromium, disposable local accounts; panels never mutate learning state."""
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import page,site
from test_study_browser import login

@pytest.mark.parametrize('width',[320,390,1280])
def test_training_panels_and_info_preserve_current_task(page,site,width):
 page.set_viewport_size({'width':width,'height':844});login(page,site)
 page.evaluate("tab('training')");page.locator('#learningFresh').click()
 expect(page.locator('#learningBoard .sq')).to_have_count(64)
 before=page.evaluate("api('/learning/dashboard')");writes=[]
 page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
 page.get_by_role('button',name='훈련 선택 · 저장 활동 · 기록',exact=True).click()
 expect(page.locator('#trainingLibrary')).to_be_visible()
 expect(page.locator('#learningBoard')).to_be_hidden()
 page.get_by_role('button',name='현재 훈련으로',exact=True).click()
 expect(page.locator('#learningTitle')).to_be_focused()
 expect(page.locator('#learningBoard')).to_be_visible()
 assert writes==[]
 assert page.evaluate("api('/learning/dashboard')")['active']==before['active']
 page.evaluate("tab('profile')")
 expect(page.locator('#profileInformation')).to_be_visible()
 expect(page.locator('#codeField')).to_be_hidden()
 page.get_by_role('button',name='표시 · 학습 설정',exact=True).click()
 expect(page.locator('#boardThemeSelect')).to_be_visible()
 expect(page.locator('#learningIntervals')).to_be_visible()
 expect(page.locator('#profileSettings')).to_be_focused()
 page.locator('#profileSections').get_by_role('button',name='계정 연결',exact=True).click()
 expect(page.locator('#codeField')).to_be_visible()
 expect(page.locator('#boardThemeSelect')).to_be_hidden()
 page.get_by_role('button',name='계정 기록 관리',exact=True).click()
 expect(page.locator('#resetProfileV5')).to_be_visible() # Never click reset.
 page.go_back();expect(page.locator('#codeField')).to_be_visible()
 page.reload();expect(page.locator('#codeField')).to_be_visible()
 assert writes==[]
 assert page.evaluate("api('/learning/dashboard')")['active']==before['active']
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
 Path('docs/qa-focus-interface/captures').mkdir(parents=True,exist_ok=True)
 page.screenshot(path=f'docs/qa-focus-interface/captures/account-{width}.png',full_page=True)
