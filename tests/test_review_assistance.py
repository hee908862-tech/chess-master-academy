"""Real SQLite + API provenance tests; no production accounts or databases."""
import copy
import json
import time
import chess
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from v7_server import attach_v7

@pytest.fixture
def api(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_URL','');monkeypatch.setenv('SQLITE_FILE',str(tmp_path/'initial.sqlite'))
    import server
    monkeypatch.setattr(server,'DATABASE_URL','')
    monkeypatch.setattr(server,'SQLITE_FILE',str(tmp_path/'game.sqlite'))
    monkeypatch.setattr(server,'STOCKFISH_PATH','')
    server.initdb()
    def choose(board,*args):
        wanted='e2e4' if board.turn else 'e7e5'
        m=chess.Move.from_uci(wanted)
        return m if m in board.legal_moves else next(iter(board.legal_moves),None)
    monkeypatch.setattr(server,'ai_move',choose)
    app=FastAPI()
    app.router.routes.extend(r for r in server.app.routes if getattr(r,'path','').startswith(('/api/game','/api/register')))
    attach_v7(app,dict(vars(server)))
    c=TestClient(app)
    token=c.post('/api/register',json={'code':'HELP-QA','pin':'local-help-qa42'}).json()['token']
    c.headers['Authorization']='Bearer '+token
    return c,server


def new(c,color='white'):
    r=c.post('/api/game/new',json={'color':color});assert r.status_code==200,r.text
    return r.json()


def play(c,u):
    r=c.post('/api/game/move',json={'from_sq':u[:2],'to_sq':u[2:4],'promotion':u[4:] or 'q'})
    assert r.status_code==200,r.text
    return r.json()


def end_review(c):
    assert c.post('/api/game/resign').status_code==200
    r=c.get('/api/games/review/0');assert r.status_code==200,r.text
    return r.json()


@pytest.mark.parametrize('hint,undo,move',[(True,False,'e2e4'),(False,True,'d2d4'),(True,True,'e2e4'),(True,False,'d2d4')])
def test_help_types_and_actual_adoption(api,hint,undo,move):
    c,server=api;new(c)
    if hint:assert c.get('/api/v7/game/hint').json()['move']=='e2e4'
    if undo:
        play(c,'e2e4');assert c.post('/api/v7/game/undo').status_code==200
    play(c,move)
    data=end_review(c);a=data['moves'][0]['assistance']
    assert a['hint_viewed']==hint and a['undo_replayed']==undo
    assert a['hint_adopted']==(hint and move=='e2e4')
    assert data['moves'][1]['assistance']['hint_viewed'] is None
    if undo:
        event=next(e for e in data['assistance_events'] if e['kind']=='undo')
        assert event['removed'][0]['move']=='e2e4' and event['removed'][0]['ply']==1
        assert event['removed'][0]['assistance']['id']!=a['move_id']
    assert server.get_state('HELP-QA')['games'][0]['assistance']['events']==data['assistance_events']


def test_multiple_undo_branch_does_not_relabel_same_ply(api):
    c,_=api;new(c);play(c,'e2e4')
    hint=c.get('/api/v7/game/hint').json();play(c,hint['move'])
    assert c.post('/api/v7/game/undo').status_code==200
    assert c.post('/api/v7/game/undo').status_code==200
    play(c,'d2d4')
    # ply 3 now has a different position: the earlier hint must not be attached here.
    b=c.get('/api/game').json()['board'];m=b['legal'][0]
    play(c,m['from']+m['to']+(m['promotion'] or ''))
    data=end_review(c)
    assert data['moves'][0]['assistance']['undo_replayed']
    assert data['moves'][2]['assistance']['hint_viewed'] is False
    assert data['moves'][2]['assistance']['undo_replayed'] is False
    assert len([e for e in data['assistance_events'] if e['kind']=='undo'])==2


def test_black_ply_and_restore(api):
    c,server=api;new(c,'black')
    # No black move yet: do not remove the only AI move or create false assistance.
    assert c.post('/api/v7/game/undo').status_code==409
    assert c.get('/api/v7/game/hint').json()['move']=='e7e5'
    saved=copy.deepcopy(server.get_state('HELP-QA'))
    server.save_state('HELP-QA',json.loads(json.dumps(saved)))
    restored=c.get('/api/game').json();assert restored['board']['ply']==1
    play(c,'e7e5');assert c.post('/api/v7/game/undo').status_code==200
    play(c,'e7e5')
    data=end_review(c)
    assert data['moves'][0]['assistance']['known'] is False
    a=data['moves'][1]['assistance'];assert a['hint_adopted'] and a['undo_replayed']
    assert data['moves'][1]['ply']==2


def test_illegal_stale_and_failed_ai_do_not_commit_events(api,monkeypatch):
    c,server=api;initial=new(c);c.get('/api/v7/game/hint')
    before=server.get_state('HELP-QA')
    assert c.post('/api/game/move',json={'from_sq':'e2','to_sq':'e5'}).status_code==400
    assert c.get('/api/v7/game/hint',params={'session_id':'wrong'}).status_code==409
    assert c.post('/api/v7/game/undo',json={'expected_fen':'wrong'}).status_code==409
    assert server.get_state('HELP-QA')==before
    monkeypatch.setattr(server,'ai_move',lambda *a:(_ for _ in ()).throw(RuntimeError('test engine failure')))
    with pytest.raises(RuntimeError):play(c,'e2e4')
    assert server.get_state('HELP-QA')==before


def test_legacy_missing_metadata_and_new_game_isolation(api):
    c,server=api;new(c);c.get('/api/v7/game/hint');play(c,'e2e4')
    new(c);play(c,'d2d4');data=end_review(c)
    assert not data['moves'][0]['assistance']['hint_viewed']
    state=server.get_state('HELP-QA');legacy=copy.deepcopy(state['games'][0]);legacy.pop('assistance');legacy['hint_plies']=[1]
    state['games'].append(legacy);server.save_state('HELP-QA',state)
    old=c.get('/api/games/review/1').json()
    assert old['moves'][0]['assistance']=={'known':False,'hint_viewed':None,'hint_adopted':None,'undo_replayed':None}


@pytest.mark.parametrize('end',['timeout','rules'])
def test_all_finish_paths_keep_ledger(api,end):
    c,server=api;new(c);c.get('/api/v7/game/hint');play(c,'e2e4')
    state=server.get_state('HELP-QA');events=copy.deepcopy(state['active_game']['assistance'])
    if end=='timeout':
        state['active_game'].update(time_mode='bullet',white_ms=0,black_ms=10000,turn_started_at=time.time()-2)
        server.save_state('HELP-QA',state)
        assert c.get('/api/v7/game/hint').status_code==409
        assert c.post('/api/v7/game/undo').status_code==409
        assert c.get('/api/game').json()['timeout']
    else:
        b=chess.Board();[b.push_uci(u) for u in ['f2f3','e7e5','g2g4','d8h4']]
        server.store_finished(state,b);server.save_state('HELP-QA',state)
    assert server.get_state('HELP-QA')['games'][0]['assistance']==events
    assert c.get('/api/v7/game/hint').status_code==409
    assert c.post('/api/v7/game/undo').status_code==409


def test_concurrent_hints_keep_both_events(api):
    from concurrent.futures import ThreadPoolExecutor
    c,server=api;new(c)
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies=list(pool.map(lambda _:c.get('/api/v7/game/hint'),range(2)))
    assert all(r.status_code==200 for r in replies)
    before=server.get_state('HELP-QA')['active_game']['assistance']['events']
    assert len(before)==2 and len({event['id'] for event in before})==2
    play(c,'e2e4');data=end_review(c)
    assert set(data['moves'][0]['assistance']['hint_ids'])=={event['id'] for event in before}


def test_actual_checkmate_api_preserves_hint(api,monkeypatch):
    c,server=api;new(c);c.get('/api/v7/game/hint')
    monkeypatch.setattr(server,'ai_move',lambda board,*args:chess.Move.from_uci('d8h4' if chess.Move.from_uci('d8h4') in board.legal_moves else 'e7e5'))
    play(c,'f2f3');finished=play(c,'g2g4');assert finished['finished']
    review=c.get('/api/games/review/0').json()
    assert review['moves'][0]['assistance']['hint_viewed']
    assert not review['moves'][0]['assistance']['hint_adopted']
    assert len(review['moves'])==4
