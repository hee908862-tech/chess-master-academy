"""Synthetic GET result doubles: incompatible answer policies cannot form trend."""
from playwright.sync_api import expect
from test_growth_browser import report_fixture,mock_status
from test_qa_browser import site,page,open_page


def test_answer_policy_separates_growth_series(page,site):
    latest=report_fixture(number=2);latest['answer_policy']='goal-alternatives-v1';latest['snapshot']['answer_policy']='goal-alternatives-v1'
    mock_status(page,latest)
    page.route('**/api/games/analysis',lambda r:r.fulfill(json={'games':[],'average':None}))
    open_page(page,site);page.evaluate("tab('profile')")
    expect(page.get_by_label('성장 그래프 비교 조건').locator('option')).to_have_count(2)
    expect(page.locator('#growthProfile line[stroke="#8fe5c8"]')).to_have_count(0)
    expect(page.locator('#growthProfile')).to_contain_text('비교 가능한 관찰이 두 번 이상')
