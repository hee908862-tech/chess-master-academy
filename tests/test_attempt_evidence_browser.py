"""Isolated component fixture tests; no account, production or grading requests."""
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
@pytest.fixture
def view():
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page();page.set_content('<main id="evidence"></main>')
        page.add_style_tag(path=str(ROOT/'public/attempt-evidence.css'));page.add_script_tag(path=str(ROOT/'public/attempt-evidence.js'))
        yield page
        browser.close()
DATA={'report_id':'synthetic-report','original':{'score':3000,'version':'legacy-fixture'},'summary':{'total':3,'correct':1,'incorrect':1,'unresolved':1,'logical_range':{'min':1,'max':2,'unit':'문항'}},'items':[{'item_id':'one','label':'긴 문항 이름 <script>unsafe</script>','status':'unresolved','external_difficulty':{'value':1531,'source':'fixture bank'},'steps':{'completed':1,'total':3},'elapsed_ms':None,'assistance':['힌트'],'repeated':True,'reason':'제한된 분석에서 확정하지 못했습니다.','revalidation':{'allowed':True}}]}
@pytest.mark.parametrize('width,height,zoom',[(1366,768,1),(360,800,1),(390,844,1),(844,390,1),(1366,768,2)])
def test_component_preserves_reference_and_accessible_layout(view,width,height,zoom):
    view.set_viewport_size({'width':width,'height':height});view.evaluate('(d)=>cmaAttemptEvidence.render("evidence",d,{onRevalidate:async()=>({state:"unchanged"})})',DATA)
    view.evaluate('(z)=>document.body.style.zoom=z',zoom)
    expect(view.locator('#evidence')).to_contain_text('미확정은 오답이 아니며')
    expect(view.locator('#evidence')).to_contain_text('1531 · fixture bank')
    expect(view.locator('#evidence')).to_contain_text('1 / 3수')
    expect(view.locator('#evidence')).to_contain_text('과거 시간을 추정하지 않음')
    view.get_by_text('당시 저장된 점수 · 참고값',exact=True).focus();view.keyboard.press('Enter')
    expect(view.locator('#evidence')).to_contain_text('3000 / 3000')
    assert view.locator('#evidence script').count()==0
    assert view.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
    view.locator('.ae-item-details > summary').click()
    for control in view.locator('summary:visible,button:visible').all():control.focus();expect(control).to_be_focused()

def test_revalidate_is_explicit_pending_unique_and_original_immutable(view):
    view.evaluate('(d)=>{window.inputData=d;window.calls=[];cmaAttemptEvidence.render("evidence",d,{onRevalidate:args=>{calls.push(args);return new Promise(resolve=>window.finish=resolve)}})}',DATA)
    assert view.evaluate('calls.length')==0
    view.locator('.ae-item-details > summary').click();button=view.get_by_role('button');button.click();expect(button).to_be_disabled()
    assert view.evaluate('calls')==[{'report_id':'synthetic-report','item_id':'one'}]
    expect(view.get_by_role('status')).to_contain_text('재검증 중')
    view.evaluate('finish({state:"corrected",corrected_status:"incorrect",message:"별도 판정 이력으로 보존"})')
    expect(view.get_by_role('status')).to_contain_text('현재 재검증 판정: 오답')
    assert view.evaluate('inputData.original.score')==3000
    assert view.evaluate('inputData.items[0].status')=='unresolved'

def test_failure_and_stale_callback_do_not_replace_new_report(view):
    view.evaluate('(d)=>cmaAttemptEvidence.render("evidence",d,{onRevalidate:async()=>{throw Error("private detail")}})',DATA)
    view.locator('.ae-item-details').evaluate('(d)=>d.open=true');view.get_by_role('button').click();expect(view.get_by_role('status')).to_contain_text('오답으로 처리하지 않습니다')
    expect(view.locator('#evidence')).not_to_contain_text('private detail')
    view.evaluate('(d)=>cmaAttemptEvidence.render("evidence",d,{onRevalidate:()=>new Promise(resolve=>window.finish=resolve)})',DATA)
    view.locator('.ae-item-details').evaluate('(d)=>d.open=true');view.get_by_role('button').click();view.evaluate('cmaAttemptEvidence.render("evidence",{title:"다른 기록",summary:{}});finish({state:"corrected",message:"오래된 결과"})')
    expect(view.locator('#evidence')).to_contain_text('다른 기록');expect(view.locator('#evidence')).not_to_contain_text('오래된 결과')

def test_real_backend_contract_counts_unknowns_and_cumulative_selected_report(view):
    aggregate={'assigned':4,'original_attempts':3,'success':1,'verified_wrong':0,'unresolved':2,'eligibility_unknown':1,'excluded':{'repeat':1},'logical_bounds':[1/3,1],'external_difficulty':{'min':1200,'max':1857}}
    data={'totals':aggregate,'areas':{'mate':aggregate},'comparison_allowed':False,'attempts':[{'report_id':'report-of-item','item_id':'saved-item','item_fingerprint':'synthetic','competency':'mate','classification':'original','eligibility_unknown':True,'original_outcome':'unverified_alternative','effective_outcome':'unverified_alternative','unresolved_reason':'analysis_limit','rating':1857,'band':[1200,1900],'execution':{'confirmed_own_moves':1,'required_own_moves':3,'forced_submissions':0,'choice_submissions':1},'revalidatable':True}]}
    view.evaluate('(d)=>{window.calls=[];cmaAttemptEvidence.render("evidence",d,{onRevalidate:async a=>{calls.push(a);return {...d,attempts:[]}}})}',data)
    expect(view.locator('#evidence')).to_contain_text('독립 여부 미확인 1문항')
    expect(view.locator('#evidence')).to_contain_text('33–100 % 완료 비율')
    expect(view.locator('#evidence')).to_contain_text('1857')
    expect(view.locator('#evidence')).to_contain_text('1 / 3수 (33%)')
    view.locator('.ae-item-details').evaluate('(d)=>d.open=true');view.get_by_role('button').click()
    assert view.evaluate('calls')==[{'report_id':'report-of-item','item_id':'saved-item'}]
    expect(view.locator('#evidence')).to_contain_text('문항별 근거가 없습니다')

def test_timing_flags_and_minimum_group_observations(view):
    d={**DATA,'items':[{**DATA['items'][0],'elapsed_ms':12000,'timing':{'availability':'observed','usable_for_trend':False,'flags':['multiple_streams']}}],'timing_trends':{'minimum_observations':3,'groups':[{'competency':'mate','count':2,'status':'reference','median_active_ms':99999},{'competency':'capture','count':3,'status':'reference','median_active_ms':14000},{'competency':'defense','count':6,'status':'descriptive_comparison','median_active_ms':12000,'previous_median_ms':18000}]}}
    view.evaluate('(d)=>cmaAttemptEvidence.render("evidence",d)',d)
    expect(view.locator('#evidence')).to_contain_text('12.0초 · 기기에서 보고한 시간')
    expect(view.locator('#evidence')).to_contain_text('여러 탭·기기에서 측정됨')
    view.get_by_text('풀이 활동 시간 · 참고 관찰',exact=True).click()
    expect(view.locator('.ae-timing')).to_contain_text('2개 관찰 · 시간 요약 근거 부족')
    expect(view.locator('.ae-timing')).not_to_contain_text('100.0초')
    expect(view.locator('.ae-timing')).to_contain_text('3개 관찰 · 최근 중앙값 14.0초')
    expect(view.locator('.ae-timing')).to_contain_text('이전 중앙값 18.0초 → 최근 12.0초')


def test_known_unfinished_is_separate_from_wrong_and_analysis_unknown(view):
    data={'totals':{'assigned':5,'original_attempts':5,'success':1,'verified_wrong':0,'unresolved':1,'unfinished':2,'pending':1,'eligibility_unknown':0,'excluded':{},'logical_bounds':[.2,.6]},'attempts':[{'item_id':'partial','report_id':'r','classification':'original','original_outcome':'partial_execution','effective_outcome':'partial_execution','competency':'mate','execution':{},'eligibility_unknown':False},{'item_id':'missing','report_id':'r','original_outcome':'unanswered','effective_outcome':'unanswered','execution':{}}]}
    view.evaluate('(d)=>cmaAttemptEvidence.render("evidence",d)',data)
    counts=view.locator('.ae-counts')
    assert counts.locator('dd').all_text_contents()==['5','1','0','1','2','1']
    expect(view.locator('.ae-items')).to_contain_text('문항 1 · 미완료')
    expect(view.locator('.ae-items')).to_contain_text('문항 2 · 아직 답안 없음')
    expect(view.locator('#evidence')).to_contain_text('20–60 % 완료 비율')


def test_many_attempts_folded_and_one_explicit_training_reference(view):
    items=[{**DATA['items'][0],'report_id':'source-report','item_id':str(i),'label':'관찰 문항 '+str(i),'status':'incorrect' if i==0 else 'unresolved'} for i in range(72)]
    view.set_viewport_size({'width':360,'height':800})
    view.evaluate('(d)=>{window.training=[];cmaAttemptEvidence.render("evidence",d,{onTrain:r=>training.push(r),onRevalidate:async()=>({})})}',{**DATA,'items':items})
    details=view.locator('.ae-item-details');assert not details.evaluate('(d)=>d.open')
    expect(view.get_by_role('button',name='이 장면부터 연습',exact=True)).to_be_visible()
    assert details.locator('li:visible').count()==0
    assert view.locator('.ae-counts dd:visible').count()==6
    view.get_by_role('button',name='이 장면부터 연습',exact=True).click()
    assert view.evaluate('training')==[{'report_id':'source-report','item_id':'0'}]
    details.locator(':scope > summary').focus();view.keyboard.press('Enter')
    assert details.locator('li:visible').count()==72
    assert view.evaluate('document.documentElement.scrollWidth<=innerWidth+1')

def test_known_revalidation_limit_message_is_preserved(view):
    view.evaluate('(d)=>cmaAttemptEvidence.render("evidence",d,{onRevalidate:async()=>{throw {status:409,message:"재검증 횟수 상한에 도달했습니다."}}})',DATA)
    view.locator('.ae-item-details > summary').click();view.get_by_role('button').click()
    expect(view.get_by_role('status')).to_contain_text('재검증 횟수 상한에 도달했습니다')
    expect(view.get_by_role('status')).not_to_contain_text('다시 시도하세요')
