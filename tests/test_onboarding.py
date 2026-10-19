"""Account-scoped persisted tutorial, additive real SQLite storage."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from onboarding_server import attach_onboarding


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', '')
    monkeypatch.setenv('SQLITE_FILE', str(tmp_path / 'initial.sqlite'))
    import server
    monkeypatch.setattr(server, 'DATABASE_URL', '')
    monkeypatch.setattr(server, 'SQLITE_FILE', str(tmp_path / 'onboard.sqlite'))
    server.initdb()
    app = FastAPI()
    app.router.routes.extend(r for r in server.app.routes if getattr(r, 'path', '') in ('/api/register', '/api/login'))
    # The isolated DB must include the additive journey schema now queried
    # by onboarding's active-session guard.
    from journey_server import attach_journey
    attach_journey(app, vars(server))
    attach_onboarding(app, dict(vars(server)))
    client = TestClient(app)
    token = client.post('/api/register', json={'code': 'INTRO-QA', 'pin': 'local-tutorial-42'}).json()['token']
    client.headers['Authorization'] = 'Bearer ' + token
    return client, server


def test_account_state_and_replay_preserves_records(api):
    c, server = api
    s = server.get_state('INTRO-QA')
    s['games'] = [{'existing': True}]
    s['assessment_v8_history'] = [{'legacy': 'keep'}]
    server.save_state('INTRO-QA', s)
    assert c.get('/api/onboarding').json()['status'] == 'not_started'
    assert c.post('/api/onboarding', json={'status': 'in_progress', 'step': 2}).status_code == 200
    # New authenticated client represents reload / second device.
    other = TestClient(c.app)
    t = other.post('/api/login', json={'code': 'INTRO-QA', 'pin': 'local-tutorial-42'}).json()['token']
    other.headers['Authorization'] = 'Bearer ' + t
    assert other.get('/api/onboarding').json()['step'] == 2
    assert other.post('/api/onboarding', json={'status': 'completed', 'step': 3}).json()['status'] == 'completed'
    assert c.post('/api/onboarding', json={'status': 'in_progress', 'step': 0}).json()['status'] == 'completed'
    persisted = server.get_state('INTRO-QA')
    assert persisted['games'] == [{'existing': True}]
    assert persisted['assessment_v8_history'] == [{'legacy': 'keep'}]


def test_skip_auth_validation_and_defer(api):
    c, server = api
    assert TestClient(c.app).get('/api/onboarding').status_code == 401
    assert c.post('/api/onboarding', json={'status': 'unknown', 'step': 0}).status_code == 422
    assert c.post('/api/onboarding', json={'status': 'in_progress', 'step': 4}).status_code == 422
    s = server.get_state('INTRO-QA'); s['active_game'] = {'moves': [], 'time_mode': 'blitz'}
    server.save_state('INTRO-QA', s)
    assert c.get('/api/onboarding').json()['defer_auto'] is True
    assert c.post('/api/onboarding', json={'status': 'skipped', 'step': 1}).json()['status'] == 'skipped'
    assert c.get('/api/onboarding').json()['status'] == 'skipped'
    second = TestClient(c.app)
    t = second.post('/api/register', json={'code': 'INTRO-OTHER', 'pin': 'local-tutorial-42'}).json()['token']
    second.headers['Authorization'] = 'Bearer ' + t
    assert second.get('/api/onboarding').json()['status'] == 'not_started'


def test_new_journey_dynamic_helper_defers_without_mutation(api):
    c, server = api
    namespace = dict(vars(server))
    app = FastAPI()
    attach_onboarding(app, namespace)
    client = TestClient(app)
    client.headers.update(c.headers)
    assert client.get('/api/onboarding').json()['defer_auto'] is False
    # Root attaches the helper after onboarding endpoints have been registered.
    namespace['journey_active'] = lambda code: code == 'INTRO-QA'
    before = dict(server.get_state('INTRO-QA'))
    assert client.get('/api/onboarding').json()['defer_auto'] is True
    assert dict(server.get_state('INTRO-QA')) == before
