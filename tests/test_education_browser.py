import json,secrets
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page,open_page

def enter(page,site):
 open_page(page,site)
 page.evaluate("async code=>{const r=await api('/register','POST',{code,pin:'education-local-123'});token=r.token;localStorage.setItem('chess_token',token);cmaEducation.open();}",'EDU-'+secrets.token_hex(5))
 expect(page.locator('#educationPaths')).to_have_attribute('aria-busy','false')
def start(page,title='공격선 관찰과 피하기',review=True):
 card=page.locator('#educationBody article').filter(has=page.get_by_role('heading',name=title,exact=True))
 card.get_by_role('button',name='설명 가리고 복습' if review else '설명 보며 학습',exact=True).click();ready(page)
def ready(page):expect(page.locator('#educationPaths')).to_have_attribute('aria-busy','false')
def sq(page,s):return page.locator(f'#educationBoard [aria-label^="{s} "]')
def next_(page):page.get_by_role('button',name='이유 확인 · 다음 비교 위치',exact=True).click();ready(page)

@pytest.mark.parametrize('width',[393,1280])
def test_real_path_help_wrong_hint_resume_and_completion(page,site,width):
 page.set_viewport_size(dict(width=width,height=900));enter(page,site);before=page.evaluate("api('/me')")['stats'];start(page)
 page.locator('#educationPaths summary').filter(has_text='사용 방법').click()
 assert page.evaluate("api('/education')")['active']['hints']==0
 sq(page,'g1').click();ready(page);expect(page.locator('#educationBody')).to_contain_text('다른 응답 1')
 page.get_by_role('button',name='설명 힌트 (도움 기록)',exact=True).click();ready(page)
 sq(page,'c3').focus();page.keyboard.press('Enter');ready(page);next_(page)
 assert page.locator('#educationBody').get_by_role('button',name='수업 예시 c3a2').count()==0
 sq(page,'c3').click();assert page.evaluate('document.activeElement.getAttribute("aria-label")').startswith('c3 ')
 sq(page,'a2').click();ready(page);next_(page)
 saved=page.evaluate("api('/education')");page.add_init_script('localStorage.setItem("chess_token",'+json.dumps(page.evaluate('token'))+');')
 page.reload();page.evaluate('cmaEducation.open()');ready(page)
 assert page.evaluate("api('/education')")['active']['id']==saved['active']['id']
 page.get_by_role('button',name='나이트가 공격받지만 강제 손실인지는 더 확인해야 한다',exact=True).click();ready(page)
 page.get_by_role('button',name='비교 완료 기록',exact=True).click();ready(page)
 expect(page.locator('#educationBody')).to_contain_text('교육 예시를 완료했습니다')
 assert page.evaluate("api('/me')")['stats']==before
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
 Path('docs/qa-education').mkdir(exist_ok=True,parents=True);page.locator('#educationPaths').screenshot(path=f'docs/qa-education/completed-{width}.png')
 page.get_by_role('button',name='결과 보관 · 다시 선택',exact=True).click();ready(page);start(page)
 expect(page.locator('#educationBody')).to_contain_text('레슨 누적 도움 1 · 다른 응답 1')

def test_black_direction_promotion_cancel_and_save_error(page,site):
 enter(page,site);start(page,'승격 직후 무승부 경계 비교',False)
 page.get_by_role('button',name='보드 방향 바꾸기',exact=True).click()
 assert page.locator('#educationBoard .sq').first.get_attribute('aria-label').startswith('h1 ')
 old=page.evaluate("api('/education')")
 sq(page,'g7').click();sq(page,'g8').click();page.keyboard.press('Escape');ready(page)
 assert page.evaluate("api('/education')")==old
 page.route('**/api/education/action',lambda r:r.fulfill(status=503,json={'detail':'controlled save failure'}))
 page.get_by_role('button',name='수업 예시 g7g8q',exact=True).click();ready(page)
 expect(page.locator('#educationStatus')).to_contain_text('controlled save failure')
 assert page.evaluate("api('/education')")==old
 page.unroute('**/api/education/action')
 page.locator('#educationPaths').get_by_role('button',name='저장 상태 다시 확인',exact=True).click();ready(page)
 page.get_by_role('button',name='수업 예시 g7g8q',exact=True).click();ready(page)
 expect(page.locator('#educationBody')).to_contain_text('스테일메이트')

@pytest.mark.parametrize('switch',[False,True])
def test_delayed_write_account_or_screen_exit_no_stale_render(page,site,switch):
 enter(page,site);start(page)
 page.evaluate("""()=>{window.realEduApi=api;window.releaseEdu=null;api=async(...args)=>{if(args[0]==='/education/action'){const value=await realEduApi(...args);return new Promise(resolve=>releaseEdu=()=>resolve(value));}return realEduApi(...args);};}""")
 sq(page,'c3').click();page.wait_for_function('releaseEdu!==null')
 if switch:
  page.evaluate("async code=>{const r=await realEduApi('/register','POST',{code,pin:'education-local-123'});token=r.token;tab('learn');}",'EDUB-'+secrets.token_hex(5));ready(page)
 else:page.evaluate("tab('home')")
 page.evaluate('releaseEdu()');page.wait_for_timeout(100)
 if switch:
  assert page.evaluate("realEduApi('/education')")['active'] is None
  expect(page.locator('#educationBoard')).to_have_count(0)
 else:expect(page.locator('#home')).to_have_class('view active')

@pytest.mark.parametrize('lesson',['threat-defended','plan-file','plan-piece','ending-opposition','ending-promotion'])
def test_all_other_paths_real_board_or_choice_completion(page,site,lesson):
 from education_content import BY_ID
 c=BY_ID[lesson];enter(page,site);start(page,c['title'])
 for i,s in enumerate(c['steps']):
  answer=s['answers'][0]
  if s['kind']=='square':sq(page,answer).click()
  elif s['kind']=='choice':page.locator('#educationBody').get_by_role('button',name=dict(s['choices'])[answer],exact=True).click()
  else:
   page.get_by_role('combobox',name='교육 합법 착수 목록',exact=True).select_option(answer)
   page.get_by_role('button',name='선택한 합법 수 두기',exact=True).click()
  ready(page)
  page.get_by_role('button',name='비교 완료 기록' if i==2 else '이유 확인 · 다음 비교 위치',exact=True).click();ready(page)
 assert page.evaluate("api('/education')")['active']['phase']=='complete'
 if lesson=='ending-opposition':
  page.get_by_role('button',name='보드 방향 바꾸기',exact=True).click()
  page.locator('#educationPaths').screenshot(path='docs/qa-education/opposition-black.png')


def test_prerequisite_link_opens_exact_existing_card_without_writes(page,site):
 enter(page,site);before=page.evaluate("api('/foundations')")
 card=page.locator('#educationBody article').filter(has=page.get_by_role('heading',name='공격선 관찰과 피하기',exact=True))
 card.get_by_role('button',name='관련 기존 기초 보기',exact=True).click()
 expect(page.locator('#foundationCourseList')).to_have_attribute('open','')
 expect(page.locator('[data-course="king-check"]')).to_be_visible()
 expect(page.locator('[data-course="king-check"]')).to_be_focused()
 assert page.evaluate("api('/foundations')")==before
 assert page.evaluate("api('/education')")['active'] is None


def test_prerequisite_cached_card_waits_for_read_then_focuses_without_writes(page,site):
 enter(page,site)
 page.evaluate('cmaFoundations.load()')  # Cached cards are visible before the next GET resolves.
 before=page.evaluate("api('/foundations')")
 page.evaluate("""()=>{window.foundationRelease=null;window.prerequisiteWrites=[];
 window.prerequisiteApi=api;api=async(...a)=>{
  if(a[1]==='POST')prerequisiteWrites.push(a[0]);
  if(a[0]==='/foundations'){const r=await prerequisiteApi(...a);return new Promise(resolve=>foundationRelease=()=>resolve(r));}
  return prerequisiteApi(...a);
 };}""")
 card=page.locator('#educationBody article').filter(has=page.get_by_role('heading',name='공격선 관찰과 피하기',exact=True))
 card.get_by_role('button',name='관련 기존 기초 보기',exact=True).click()
 expect(page.locator('#foundationCourseList')).to_have_attribute('open','')
 expect(page.locator('[data-course="king-check"]')).to_be_visible()
 page.wait_for_function('foundationRelease!==null')
 expect(page.locator('#foundationHeading')).to_be_focused()
 page.evaluate('foundationRelease()')
 expect(page.locator('[data-course="king-check"]')).to_be_focused()
 assert page.evaluate('prerequisiteWrites')==[]
 assert page.evaluate("prerequisiteApi('/foundations')")==before
 assert page.evaluate("prerequisiteApi('/education')")['active'] is None
