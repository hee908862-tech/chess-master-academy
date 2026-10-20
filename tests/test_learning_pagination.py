"""Paginated history must not change the active task or accept stale pages."""
import copy
import json
import subprocess
from pathlib import Path
from playwright.sync_api import expect
from test_qa_browser import site, page, open_page, square
from test_learning import setup, post, action, solution
from v9_server import LIB


def test_old_active_card_keeps_completed_category(setup):
    import sqlite3
    c,_,_,db=setup
    s=post(c,'start',{'fresh':True,'mode':'verify'})
    assert s['category'] is None and s['outcome'] is None
    with sqlite3.connect(db) as conn:
        state=json.loads(conn.execute('SELECT state FROM learning_progress').fetchone()[0])
        card=state['cards'][s['card_id']]
        category=card['category']
        for i in range(62):
            clone=copy.deepcopy(card);clone['id']=f'newer-{i}';state['cards'][clone['id']]=clone
        conn.execute('UPDATE learning_progress SET state=?',(json.dumps(state),))
    assert s['card_id'] not in [c['id'] for c in c.get('/api/learning/dashboard').json()['cards']]
    done=action(c,s,'move',solution(s))
    assert done['done'] and done['outcome']['category']==category
    assert c.get('/api/learning/dashboard').json()['active']['outcome']['category']==category


def test_older_card_next_problem_uses_completed_category(page,site):
    open_page(page,site)
    page.evaluate("async()=>{const s=(await api('/learning/dashboard')).active;return api('/learning/start','POST',{fresh:true,...(s&&!s.done?{pause_session_id:s.session_id,pause_revision:s.revision}:{})});}")
    data=page.evaluate("api('/learning/dashboard')")
    card=next(c for c in data['cards'] if c['id']==data['active']['card_id'])
    newer=[dict(card,id=f'newer-{i}',title=f'Newer {i}') for i in range(62)]
    def dashboard(route):
        response=route.fetch();d=response.json()
        offset='offset=50' in route.request.url
        d.update(cards=[card]+newer[:12] if offset else newer[12:],cards_next=None if offset else 50,cards_total=63)
        route.fulfill(json=d)
    page.route('**/api/learning/dashboard*',dashboard)
    page.evaluate("tab('training')")
    page.get_by_role('button',name='이전 훈련 카드 더 보기',exact=True).click()
    expect(page.locator('#learningCards > .learning-item')).to_have_count(63)
    page.locator('#learningCards > .learning-item').last.get_by_role('button',name='다시 연습',exact=True).click()
    expect(page.locator('#learningCards > .learning-item')).to_have_count(50)
    expect(page.locator('#learningFresh')).to_be_enabled()
    move=LIB[card['id'].removeprefix('puzzle-')]['moves'][1]
    square(page,'learningBoard',move[:2]).click();square(page,'learningBoard',move[2:4]).click()
    if len(move)==5:page.locator('#cmaPromotionModal').get_by_role('button',name={'q':'퀸','r':'룩','b':'비숍','n':'나이트'}[move[4]]).click()
    next_button=page.get_by_role('button',name='다음 첫 수 검증',exact=True)
    expect(next_button).to_be_enabled()
    with page.expect_request('**/api/learning/start') as request:next_button.click()
    assert request.value.post_data_json=={'fresh':True,'mode':'verify','category':card['category']}
    expect(page.locator('#learningTitle')).to_have_text('주제 비공개 · 독립 판단')


def test_page_single_flight_duplicates_and_stale_responses():
    source=(Path(__file__).resolve().parents[1]/'public/learning.js').read_text()
    function=source[source.index('  async function loadMoreCards()'):source.index('  async function act(')]
    script=r'''
const assert=require('node:assert/strict');
let token='A',generation=1,dashboard,cardsRequest=null,resolve,reject,calls=0,message='';
const $=()=>({set textContent(v){message=v;}});
const renderDashboard=()=>{};
const api=()=>{calls++;return new Promise((yes,no)=>{resolve=yes;reject=no;});};
FUNCTION
(async()=>{
 const reset=()=>{dashboard={cards:[{id:'current'}],cards_next:50};};
 reset();const first=loadMoreCards();await loadMoreCards();assert.equal(calls,1);
 resolve({cards:[{id:'older'},{id:'older'},{id:'current'}],cards_next:100});await first;
 assert.deepEqual(dashboard.cards.map(c=>c.id),['older','current']);assert.equal(dashboard.cards_next,100);
 for(const change of [()=>{token='B';},()=>{generation++;},()=>{dashboard={cards:[{id:'fresh'}],cards_next:50};},()=>{dashboard.cards_next=100;}]){
   reset();const pending=loadMoreCards();change();const expected=JSON.stringify(dashboard);
   resolve({cards:[{id:'stale'}],cards_next:null});await pending;
   assert.equal(JSON.stringify(dashboard),expected);assert.equal(cardsRequest,null);
 }
 reset();const pending=loadMoreCards();token='C';reject(Error('old account error'));await pending;assert.equal(message,'');
 reset();const retry=loadMoreCards();reject(Error('retry available'));await retry;assert.equal(message,'retry available');assert.equal(cardsRequest,null);
})().catch(e=>{console.error(e);process.exit(1);});
'''.replace('FUNCTION',function)
    subprocess.run(['node','-e',script],check=True)


def test_more_button_double_click_and_late_page_after_refresh(page,site):
    open_page(page,site)
    page.evaluate("async()=>{const s=(await api('/learning/dashboard')).active;return api('/learning/start','POST',{fresh:true,...(s&&!s.done?{pause_session_id:s.session_id,pause_revision:s.revision}:{})});}")
    data=page.evaluate("api('/learning/dashboard')")
    template=data['cards'][0]
    cards=[dict(template,id=f'card-{i}',title=f'Card {i}') for i in range(50)]
    pending=[]
    def dashboard(route):
        if 'offset=' in route.request.url:
            pending.append(route);return
        d={**data,'cards':cards,'cards_next':50,'cards_total':63}
        route.fulfill(json=d)
    page.route('**/api/learning/dashboard*',dashboard)
    page.evaluate("tab('training')")
    more=page.get_by_role('button',name='이전 훈련 카드 더 보기',exact=True)
    expect(more).to_be_enabled()
    # Fire twice on the same old DOM node, before the first response.
    more.evaluate("e=>{e.click();e.click();}")
    expect(page.get_by_role('button',name='이전 카드 불러오는 중…',exact=True)).to_be_disabled()
    page.wait_for_timeout(100);assert len(pending)==1
    page.locator('#learningRefresh').click()
    expect(page.locator('#learningCards > .learning-item')).to_have_count(50)
    pending[0].fulfill(json={**data,'cards':[dict(template,id='stale',title='Stale page')],'cards_next':None})
    expect(page.get_by_role('button',name='이전 훈련 카드 더 보기',exact=True)).to_be_enabled()
    expect(page.locator('#learningCards > .learning-item')).to_have_count(50)
    expect(page.locator('#learningCards')).not_to_contain_text('Stale page')
