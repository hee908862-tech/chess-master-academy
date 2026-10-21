from playwright.sync_api import expect
from test_qa_browser import page,site


def test_catalog_delay_explains_existing_feedback_test_failure(page,site):
    page.unroute('**/api/v9/catalog')
    pending=[];page.route('**/api/v9/catalog',lambda r:pending.append(r))
    page.goto(site[0]);page.evaluate("tab('puzzle')")
    expect(page.locator('#v9PuzzleTheme option')).to_have_count(0)
    with page.expect_response('**/api/v9/puzzle/start') as response:
        page.locator('#v9PuzzleStart').click()
    assert response.value.request.post_data_json['theme']==''
    assert response.value.status==400
    assert response.value.json()['detail']=='해당 과목이 없습니다.'
    print('Delayed catalog: empty theme POST, HTTP 400 (existing defect reproduced).')
    for r in pending:r.continue_()
    expect(page.locator('#v9PuzzleTheme')).to_have_value('random')
    with page.expect_response('**/api/v9/puzzle/start') as response:
        page.locator('#v9PuzzleStart').click()
    assert response.value.request.post_data_json['theme']=='random'
    assert response.value.status==200
    expect(page.locator('#v9PuzzleBoardFeedback')).to_contain_text('직접 풀어보세요')
    print('Loaded catalog: random theme POST, HTTP 200, feedback present.')
