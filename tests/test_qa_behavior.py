"""Isolated API regressions: never opens the application/production database."""
import copy
from pathlib import Path
import sys
import time
import chess
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import v9_server
from v8_server import attach_v8

FEN = '6k1/3P1pp1/p6p/8/1p6/1P1Q3P/P5PK/2qq4 w - - 0 1'

@pytest.fixture
def api(monkeypatch):
    state = {}
    app = FastAPI()
    ns = {'auth': lambda _: 'QA', 'get_state': lambda _: copy.deepcopy(state),
          'save_state': lambda _, s: (state.clear(), state.update(copy.deepcopy(s)))}
    v9_server.attach_v9(app, ns)
    ns.update(serialize_board=lambda b: {'fen': b.fen()}, medium_move=lambda b: None,
              Path=Path, STOCKFISH_PATH='')
    attach_v8(app, ns)
    return TestClient(app), state


def seed(monkeypatch, state, moves):
    before = chess.Board(FEN)
    before.turn = chess.BLACK
    before.remove_piece_at(chess.C1)
    before.set_piece_at(chess.C2, chess.Piece(chess.QUEEN, chess.BLACK))
    p = {'id': 'fixture', 'fen': before.fen(), 'moves': ['c2c1'] + moves,
         'rating': 1400, 'themes': ['mateIn2']}
    monkeypatch.setattr(v9_server, 'LIB', {'fixture': p})
    state['v9_puzzle'] = {'type':'puzzle','theme':'mateIn2','level':'중급',
        'ids':['fixture'],'index':0,'offset':1,'correct_count':0,'attempted':False,
        'done':False,'awaiting_next':False}

@pytest.mark.parametrize('promotion', ['q', 'r'])
@pytest.mark.parametrize('line', [['d7d8q'], ['d7d8b', 'g8h8', 'd8f7']])
def test_original_d8_terminal_alternative(api, monkeypatch, promotion, line):
    client, state = api
    seed(monkeypatch, state, line)
    response = client.post('/api/v9/puzzle/move', json={'move':'d7d8'+promotion})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['solved'] and data['done'] and data['reply'] is None
    assert chess.Board(data['completed_fen']).is_checkmate()
    assert len(state['puzzle_results']) == 1
    assert client.post('/api/v9/puzzle/move', json={'move':'d7d8q'}).status_code == 409
    assert len(state['puzzle_results']) == 1


def test_wrong_hint_preserve_accuracy(api, monkeypatch):
    client, state = api
    seed(monkeypatch, state, ['d7d8q'])
    assert not client.post('/api/v9/puzzle/move', json={'move':'d7d8b'}).json()['correct']
    assert client.get('/api/v9/puzzle/hint').status_code == 200
    assert client.post('/api/v9/puzzle/move', json={'move':'d7d8r'}).json()['solved']
    result = state['puzzle_results'][0]
    assert result['first_try_correct'] is False
    assert result['hint_used'] and result['wrong_moves'] == 1


def test_missing_session_is_conflict(api):
    client, _ = api
    assert client.post('/api/v9/puzzle/move', json={'move':'e2e4'}).status_code == 409
    assert client.get('/api/v9/puzzle/hint').status_code == 409
    assert client.get('/api/v9/session/puzzle').json()['active'] is False


def test_assessment_timeout_rejects_later_move(api):
    client, state = api
    state['assessment_v8'] = {'phase':'game','moves':[],'losses':[],'engine_ok':False,
        'log':[], 'clock':{'white_ms':1,'black_ms':600000,'increment_ms':5000},
        'clock_started_at':time.time()-2}
    result = client.get('/api/v8/assessment/status').json()
    assert result['phase'] == 'results'
    assert client.post('/api/v8/assessment/game-move', json={'move':'e2e4'}).status_code == 409
    assert len(state['assessment_v8_history']) == 1
    assert client.get('/api/v8/assessment/status').json()['recent'] == result['result']

@pytest.fixture
def game_api(tmp_path, monkeypatch):
    # Import the real routes against a disposable SQLite database, then isolate state.
    monkeypatch.setenv('DATABASE_URL', '')
    monkeypatch.setenv('SQLITE_FILE', str(tmp_path/'game.sqlite3'))
    import server
    state = server.blank_state()
    monkeypatch.setattr(server, 'auth', lambda _: 'QA')
    monkeypatch.setattr(server, 'get_state', lambda _: copy.deepcopy(state))
    monkeypatch.setattr(server, 'save_state', lambda _,s: (state.clear(),state.update(copy.deepcopy(s))))
    return TestClient(server.app), state, server

@pytest.mark.parametrize('fen,reply,move', [
    ('4k3/8/8/8/3p4/8/4P3/4K3 w - - 0 1','d4e3',('e2','e4','q')),
    ('4k3/8/8/8/8/8/1p6/4K2R w - - 0 1','b2b1n',('h1','h2','q')),
])
def test_ai_en_passant_and_underpromotion(game_api, monkeypatch, fen, reply, move):
    client, state, server = game_api
    board=chess.Board(fen)
    state['active_game']={'moves':[],'color':'white','engine':'fallback','difficulty':1,
                          'time_mode':'unlimited','hint_used':False,'hint_plies':[]}
    monkeypatch.setattr(server, 'reconstruct', lambda _:board.copy())
    monkeypatch.setattr(server, 'ai_move', lambda *args:chess.Move.from_uci(reply))
    response=client.post('/api/game/move',json=dict(zip(['from_sq','to_sq','promotion'],move)))
    assert response.status_code==200,response.text
    result=response.json()
    assert result['ai_move']==reply
    squares=result['board']['squares']
    if reply=='d4e3': assert squares.get('e3')=='p' and 'e4' not in squares and 'd4' not in squares
    else: assert squares.get('b1')=='n' and 'b2' not in squares


def test_real_corpus_course_completes_once(api):
    client,state=api
    started=client.post('/api/v9/course/start',json={'theme':'mateIn1','level':'중급'})
    assert started.status_code==200,started.text
    assert len(set(state['v9_course']['ids']))==15
    for index in range(15):
        while True:
            task=state['v9_course']
            puzzle=v9_server.LIB[task['ids'][task['index']]]
            response=client.post('/api/v9/course/move',json={'move':puzzle['moves'][task['offset']]})
            assert response.status_code==200,response.text
            if response.json()['solved']:break
        if index<14:
            assert client.post('/api/v9/course/next').status_code==200
    assert state['v9_course']['done']
    assert len(state['puzzle_results'])==15
    assert len(state['v9_course_history'])==1
    assert state['v9_course_history'][0]['first_try']==15
    assert client.post('/api/v9/course/next').json()['done']
    assert len(state['v9_course_history'])==1
