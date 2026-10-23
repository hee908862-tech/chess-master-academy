"""Actual page/controller with isolated synthetic API responses, no production writes."""
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page
from test_initial_profile import real_rows,report
from initial_profile import initialize,freeze,status
from attempt_evidence import summarize_attempts

@pytest.mark.parametrize('width',[1366,360,390])
def test_initial_and_historical_evidence_explicit_revalidation(page,site,width):
    page.set_viewport_size({'width':width,'height':844})
    page.goto(site[0]);page.wait_for_function('!!token && !!window.cmaAttemptReview')
    rows=real_rows()
    for r in rows:r['outcome']='completed'
    rows[0]['outcome']='unverified_alternative'
    r=report(rows);r['id']='isolated-evidence-report';r['at']='2026-10-23T00:00:00+00:00'
    data=summarize_attempts([r]);a=data['attempts'][0];a['revalidatable']=True;a['original_outcome']='unverified_alternative';a['effective_outcome']='unverified_alternative'
    r['internal_skill']={'score':3000,'version':'synthetic-preserved'}
    state={'results':[r],'active':None};initialize(state,r['corpus_sha256'])
    baseline=status(state);baseline['attempt_evidence']=data
    saved=page.evaluate("api('/journey')");saved.update(active=None,latest=r,results=[r],initial_profile=baseline)
    posts=[]
    page.route('**/api/journey',lambda route:route.fulfill(json=saved))
    page.route('**/api/journey/attempt-evidence/*',lambda route:route.fulfill(json=data))
    def review(route):
        posts.append(route.request.post_data_json);route.fulfill(json={'status':'completed'})
    page.route('**/api/journey/revalidate',review)
    page.evaluate("cmaNavigation.go('diagnosis/initial')")
    expect(page.locator('#initialAttemptEvidence')).to_contain_text('원래 시도')
    assert posts==[]
    page.evaluate("document.querySelector('#journeyPast').open=true")
    page.locator('#journeyPastReport .ae-item-details > summary').click()
    button=page.locator('#journeyPastReport button[data-revalidation]').first
    expect(button).to_be_enabled();button.focus();page.keyboard.press('Enter')
    page.wait_for_function("document.querySelector('#journeyPastReport button[data-revalidation]:not(:disabled)')")
    assert len(posts)==1 and posts[0]['report_id']==r['id'] and posts[0]['item_id']==a['item_id']
    assert len(posts[0]['request_id'])>=16
    page.locator('#journeyPastReport .ae-original summary').click()
    expect(page.locator('#journeyPastReport .ae-original')).to_contain_text('3000 / 3000')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')

def test_revalidation_followup_get_does_not_show_previous_identity(page,site):
    page.goto(site[0]);page.wait_for_function('!!token && !!window.cmaAttemptReview')
    fixture={'report_id':'synthetic-old-report','summary':{'total':1,'correct':0,'incorrect':0,'unresolved':1},'items':[{'item_id':'one','label':'이전 정체성 문항','status':'unresolved','revalidation':{'allowed':True}}]}
    pending=[]
    page.route('**/api/journey/revalidate',lambda r:r.fulfill(json={'status':'completed'}))
    page.route('**/api/journey/attempt-evidence/synthetic-old-report',lambda r:pending.append(r))
    page.evaluate('(d)=>{cmaNavigation.go("home");const h=document.createElement("section");h.id="identityEvidence";document.querySelector("#home").prepend(h);cmaAttemptReview.render(h,d)}',fixture)
    page.locator('#identityEvidence .ae-item-details > summary').click()
    page.locator('#identityEvidence button').click()
    page.wait_for_timeout(250);assert pending
    page.evaluate("token='synthetic-replacement-identity'")
    pending[0].fulfill(json={'title':'이전 계정의 늦은 민감 결과','attempts':[],'totals':{}})
    expect(page.locator('#identityEvidence [role=status]')).to_contain_text('판정을 확인하지 못했습니다')
    expect(page.locator('#identityEvidence')).not_to_contain_text('이전 계정의 늦은 민감 결과')
