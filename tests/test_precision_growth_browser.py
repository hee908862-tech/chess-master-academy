"""Selected-domain growth list uses only observed historical areas."""
from playwright.sync_api import expect
from test_qa_browser import site,page,open_page


def test_unrelated_zero_observation_reports_do_not_fill_selected_growth(page,site):
    open_page(page,site)
    reports=[]
    for n,count in enumerate([2,0,0]):
        reports.append({'id':str(n),'at':f'2026-01-0{n+1}T00:00:00Z','version':'journey-v5',
          'snapshot':{'version':'skill-index-v1','mode':'domain','areas':{'mate':{'observed':count,'score':1501 if count else None,'comparable':False}}}})
    journey=page.evaluate("api('/journey')")
    journey.update(results=reports)
    page.route('**/api/journey',lambda r:r.fulfill(json=journey))
    page.evaluate("async()=>{await cmaJourney.load();tab('profile');}")
    page.get_by_label('성장 그래프 분야',exact=True).select_option('mate')
    expect(page.locator('#growthProfile .growth-records li')).to_have_count(1)
    expect(page.locator('#growthProfile .growth-records')).to_contain_text('2문제 관찰')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
