"""Diagnosis to training bridge: actual SQLite storage, provenance and exposure boundaries."""
import copy
import json
import sqlite3

import chess
import pytest
import learning_server as learning
from test_learning import setup, post, action


def report_fixture(ns):
    puzzle = next(p for p in learning.LIB.values() if len(p['moves']) >= 4 and 'mateIn2' in p['themes'])
    b = chess.Board(puzzle['fen']); b.push_uci(puzzle['moves'][0])
    item = {'id': 'item-1', 'puzzle_id': puzzle['id'], 'fen': b.fen(), 'line': puzzle['moves'][1:],
            'tags': puzzle['themes'], 'competency': 'mate', 'first_correct': True,
            'complete': False, 'correct_plies': 1, 'total_plies': (len(puzzle['moves'])//2),
            'reason': '후속 응수 뒤 미완성'}
    report = {'id': 'report-A', 'version': 'competency-v2', 'items': [item]}
    ns['journey_report'] = lambda code, report_id=None: copy.deepcopy(report) if code == 'A' and report_id in (None, report['id']) else None
    ns['journey_seen'] = lambda code: {puzzle['id']} if code == 'A' else set()
    ns['journey_positions'] = lambda code: {' '.join(b.fen().split()[:4])} if code == 'A' else set()
    return report, item


def state_from(path):
    with sqlite3.connect(path) as conn:
        return json.loads(conn.execute("SELECT state FROM learning_progress WHERE code='A'").fetchone()[0])


def test_bridge_full_line_provenance_no_independent_credit(setup):
    client, ns, legacy, db = setup
    report, item = report_fixture(ns)
    linked = post(client, 'from-diagnosis', {'report_id': report['id'], 'item_id': item['id']})
    assert linked['diagnosis']['reason'] == item['reason']
    assert linked['active']['fen'] == item['fen'] and linked['path']['current'] == 0
    assert not linked['active']['done']
    assert linked['path']['steps'][0]['status'] == 'active'
    # Idempotence does not create another path or erase work.
    again = post(client, 'from-diagnosis', {'report_id': report['id'], 'item_id': item['id']})
    assert again['path']['id'] == linked['path']['id']
    assert again['active'] == linked['active']
    session = post(client, 'path', {})['active']
    first = action(client, session, 'move', item['line'][0])
    assert not first['done'], 'Correct first move is not full calculation success'
    session = first
    for move in item['line'][2::2]:
        if session['done']: break
        session = action(client, session, 'move', move)
    assert session['done'] and session['outcome']['success']
    assert session['outcome']['independent_kind'] is None
    saved = state_from(db)
    assert saved['cards'][session['card_id']]['successes'] == 0
    assert saved['attempts'][0]['assessment_scope'] == 'full_line'
    assert saved['attempts'][0]['diagnosis']['report_id'] == report['id']
    assert legacy == {'games': [], 'puzzle_results': [], 'completed_lessons': ['old']}
    concept = post(client, 'path', {})
    assert concept['active'] is None and concept['path']['concept_position']['fen'] == item['fen']
    assert client.get('/api/learning/dashboard').json()['active'] is None


def test_bridge_rejects_unrelated_unfinished_path_and_invalid_snapshot(setup):
    client, ns, _, db = setup
    report, item = report_fixture(ns)
    post(client, 'path', {})
    before = state_from(db)
    other = {**item, 'id': 'item-2'}
    report['items'].append(other)
    assert client.post('/api/learning/from-diagnosis', json={'report_id': report['id'], 'item_id': other['id']}).status_code == 409
    assert state_from(db) == before
    assert client.post('/api/learning/from-diagnosis', json={'report_id': 'missing', 'item_id': item['id']}).status_code == 404
    assert client.post('/api/learning/from-diagnosis', headers={'Authorization':'B'}, json={'report_id':report['id'],'item_id':item['id']}).status_code == 404


def test_bridge_invalid_snapshot_does_not_write_card(setup):
    client, ns, _, db = setup
    report, item = report_fixture(ns)
    item['line'] = ['a1a8', 'h8h1']
    assert client.post('/api/learning/from-diagnosis', json={'report_id':report['id'],'item_id':item['id']}).status_code == 409
    assert client.get('/api/learning/dashboard').json()['cards'] == []


def test_today_path_uses_diagnosis_and_excludes_ids_positions_from_transfer(setup, monkeypatch):
    client, ns, _, db = setup
    report, item = report_fixture(ns)
    route = post(client, 'path', {})
    assert route['path']['diagnosis']['item_id'] == item['id']
    assert not route['path']['fresh']
    # All corpus positions have already appeared in the assessment. No fallback is allowed.
    ns['journey_seen'] = lambda _: set(learning.LIB)
    denied = client.post('/api/learning/start', json={'fresh': True, 'mode': 'verify'})
    assert denied.status_code == 409
    assert state_from(db)['active']['id'] == route['active']['session_id']
    # Position-level exclusion also catches a duplicated puzzle under another ID.
    original = next(p for p in learning.LIB.values() if p['id'] == item['puzzle_id'])
    duplicate = {**original, 'id': 'duplicate-puzzle'}
    monkeypatch.setattr(learning, 'LIB', {'duplicate-puzzle': duplicate})
    ns['journey_seen'] = lambda _: {item['puzzle_id']}
    assert client.post('/api/learning/start', json={'fresh': True}).status_code == 409


def test_diagnostic_exposure_cannot_become_mastery_after_delayed_repeat(setup, monkeypatch):
    from datetime import timedelta
    client, ns, _, db = setup
    report, item = report_fixture(ns)
    linked = post(client, 'from-diagnosis', {'report_id':report['id'],'item_id':item['id']})
    s = post(client, 'start', {'card_id':linked['path']['source_card']})
    s = action(client, s, 'hint')
    for uci in item['line'][::2]:
        if s['done']: break
        s = action(client, s, 'move', uci)
    future = learning.now() + timedelta(days=8)
    monkeypatch.setattr(learning,'now',lambda:future)
    s = post(client, 'start', {'card_id':s['card_id'],'mode':'verify'})
    for uci in item['line'][::2]:
        if s['done']: break
        s = action(client, s, 'move', uci)
    assert s['outcome']['independent_kind'] is None
    assert state_from(db)['cards'][s['card_id']]['successes'] == 0


from test_qa_browser import site, open_page
from test_learning_browser import route_page
from playwright.sync_api import expect


@pytest.mark.parametrize('width,height', [(1366,768),(390,844)])
def test_concept_uses_real_source_and_locks_pending_transition(route_page,site,width,height):
    page = route_page
    page.set_viewport_size({'width':width,'height':height})
    open_page(page,site)
    initial = page.evaluate("api('/learning/path','POST',{})")
    session = initial['active']
    move = learning.LIB[session['card_id'].removeprefix('puzzle-')]['moves'][1]
    page.evaluate("x=>api('/learning/action','POST',x)", {'session_id':session['session_id'],'revision':session['revision'],'action':'move','move':move})
    concept = page.evaluate("api('/learning/path','POST',{})")
    page.evaluate("tab('training')")
    expect(page.locator('#learningTitle')).to_have_text('개념 확인 · 진단과 같은 원리')
    expect(page.locator('#learningMode')).to_have_text('읽기 전용 · 개념')
    expect(page.locator('#learningConcept')).to_have_text(concept['path']['concept'])
    assert page.locator('#learningBoard button:enabled').count() == 0
    # Verify displayed contents against the persisted source FEN, not an initial chessboard.
    expected = chess.Board(concept['path']['concept_position']['fen'])
    assert page.locator('#learningBoard .sq.white-piece, #learningBoard .sq.black-piece').count() == len(expected.piece_map())
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.screenshot(path=f'/tmp/learning-concept-v2-{width}.png',full_page=True)
    pending=[]
    page.route('**/api/learning/path',lambda route:pending.append(route))
    page.get_by_role('button',name='개념 읽기 확인',exact=True).click()
    expect(page.locator('#learningFresh')).to_be_disabled()
    expect(page.get_by_role('button',name='개념 읽기 확인',exact=True)).to_be_disabled()
    assert len(pending) == 1
    pending[0].continue_()
    expect(page.get_by_role('button',name='경로 시작 · 이어가기',exact=True)).to_be_enabled()


def test_previous_pending_diagnosis_path_opens_same_source_without_duplicate(setup):
    client,ns,legacy,db=setup
    report,item=report_fixture(ns)
    linked=post(client,'from-diagnosis',{'report_id':report['id'],'item_id':item['id']})
    state=state_from(db)
    state['active']=None
    state['path']['steps'][0]['status']='pending'
    state['path']['steps'][0].pop('session',None)
    with sqlite3.connect(db) as conn:
        conn.execute('UPDATE learning_progress SET state=? WHERE code=?',(json.dumps(state),'A'))
    restored=post(client,'from-diagnosis',{'report_id':report['id'],'item_id':item['id']})
    assert restored['path']['id']==linked['path']['id']
    assert restored['active']['fen']==item['fen']
    assert restored['path']['steps'][0]['status']=='active'
