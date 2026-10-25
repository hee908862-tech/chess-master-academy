"""Examples cannot mutate practice moves or count as independent performance."""
import copy
import chess
import pytest
from basic_clips import clip
from basic_rules_content import RULE_UNITS, BY_ID, replay_rule
from test_movement import movement, start, save
from test_onboarding import api


@pytest.mark.parametrize('unit', RULE_UNITS, ids=lambda u:u['id'])
def test_all_clips_start_at_initial_position_and_replay_legally(unit):
    frames=clip(unit)['frames']
    assert frames[0]['fen']==unit['fen']
    for previous,frame in zip(frames,frames[1:]):
        if frame['move']:
            board=chess.Board(previous['fen']);move=chess.Move.from_uci(frame['move'])
            assert move in board.legal_moves
            board.push(move)
            assert board.fen(en_passant='fen')==frame['fen']
    assert frames[-1]['fen']==replay_rule(unit,unit['example_actions'])['fen']


def test_three_reported_positions_and_explanations():
    frames=clip(BY_ID['rules-pawn-promotion'])['frames']
    assert [f['move'] for f in frames if f['move']]==['e7e8q','h8h7','e8e4']
    assert chess.Board(frames[1]['fen']).is_check()
    promotion=BY_ID['rules-pawn-promotion']
    assert not replay_rule(promotion,['e7e8q'])['done']
    assert replay_rule(promotion,['e7e8q','e8e4'])['done']
    shield=BY_ID['rules-shield-piece']
    assert not replay_rule(shield,['d2d3'])['done']
    assert replay_rule(shield,['d2d4'])['done']
    frames=clip(BY_ID['rules-make-stalemate'])['frames'];board=chess.Board(frames[-1]['fen'])
    assert board.turn==chess.BLACK and not board.is_check() and board.is_stalemate()
    for square in ['g8','g7','h7']:
        assert board.is_attacked_by(chess.WHITE,chess.parse_square(square))


def test_demo_exposure_is_durable_without_completion_or_other_state_writes(movement):
    client,server=movement;state=start(client,unit='rules-pawn-promotion')
    before=copy.deepcopy(dict(server.get_state('INTRO-QA')))
    request=dict(unit_id=state['active']['unit_id'],session_id=state['active']['session_id'],revision=state['revision'])
    r=client.post('/api/movement/demo',json=request);assert r.status_code==200
    previous=copy.deepcopy(state['active']);previous['helped']=True
    state=r.json()['dashboard'];assert state['active']==previous
    assert not state['active']['done'] and state['active']['moves']==[]
    after=dict(server.get_state('INTRO-QA'));after.pop('movement_v1');before.pop('movement_v1');assert after==before
    assert client.post('/api/movement/demo',json=request).status_code==409
    state=start(client,state,unit='rules-pawn-promotion',action='restart',request='restart-demo')
    assert state['active']['helped'] and not state['active']['done']
    state=save(client,state,['e7e8q','e8e4']);assert state['active']['helped'] and state['active']['done']


def test_previous_clip_keeps_current_session_and_unauthorized_requests_fail(movement):
    from fastapi.testclient import TestClient
    from movement_content import UNITS
    client,server=movement;state=start(client,unit='rules-pawn-promotion')
    idx=next(i for i,u in enumerate(UNITS) if u['id']==state['active']['unit_id'])
    prior=UNITS[idx-1]['id']
    request=dict(unit_id=prior,session_id=state['active']['session_id'],revision=state['revision'])
    assert TestClient(client.app).post('/api/movement/demo',json=request).status_code==401
    response=client.post('/api/movement/demo',json=request).json()
    assert response['clip']['unit_id']==prior
    assert response['dashboard']['active']==state['active']
    state=response['dashboard'];request.update(revision=state['revision'],unit_id='rules-make-stalemate')
    assert client.post('/api/movement/demo',json=request).status_code==400
    request.update(unit_id=prior,session_id='wrong-session')
    assert client.post('/api/movement/demo',json=request).status_code==409


@pytest.mark.parametrize('current,previous,move',[
    ('bishop-path','rules-two-rooks-right','b2e5'),
    ('queen-path','rules-two-bishops-dark','d2d5')])
def test_previous_rule_clip_from_movement_lesson_preserves_progress(movement,current,previous,move):
    client,_=movement;state=start(client,unit=previous)
    state=save(client,state,BY_ID[previous]['example_actions'])
    state=start(client,state,unit=current,action='next',request='boundary-next')
    assert state['active']['unit_id']==current
    state=save(client,state,[move]);before=copy.deepcopy(state['active'])
    response=client.post('/api/movement/demo',json=dict(unit_id=previous,
        session_id=before['session_id'],revision=state['revision']))
    assert response.status_code==200
    assert response.json()['clip']['unit_id']==previous
    assert response.json()['dashboard']['active']==before
    assert client.get('/api/movement').json()['active']==before
