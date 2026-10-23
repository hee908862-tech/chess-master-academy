"""Original curriculum goals, all alternatives use real chess legality."""
import copy
import chess
import pytest
from basic_rules_content import RULE_UNITS, BY_ID, replay_rule, validate_content
from movement_content import UNITS, STAGES
from test_movement import movement, start, save, body
from test_onboarding import api


def test_entire_curriculum_has_every_registered_topic():
    validate_content()
    assert set(u['stage'] for u in UNITS)==set(STAGES)
    assert len(STAGES)==18
    assert len({u['id'] for u in UNITS})==len(UNITS)

@pytest.mark.parametrize('u',RULE_UNITS,ids=lambda u:u['id'])
def test_each_original_scene_is_solvable_and_terminal(u):
    result=replay_rule(u,u['example_actions'])
    assert result['done'] and not result['failed']
    with pytest.raises(ValueError):replay_rule(u,u['example_actions']+[u['example_actions'][-1]])


def test_check_all_legal_alternatives_not_exact_line():
    u=BY_ID['rules-give-check'];b=chess.Board(u['fen']);checks=[]
    for m in b.legal_moves:
        result=replay_rule(u,[m.uci()]);after=b.copy();after.push(m)
        assert result['done']==after.is_check()
        if result['done']:checks.append(m.uci())
    assert len(checks)>1


def test_goal_failure_is_not_illegality_or_success():
    u=BY_ID['rules-give-check'];b=chess.Board(u['fen'])
    alternative=next(m for m in b.legal_moves if not b.gives_check(m))
    r=replay_rule(u,[alternative.uci()]);assert r['failed'] and not r['done']
    assert r['moves']==[alternative.uci()] and not r['legal']
    with pytest.raises(ValueError):replay_rule(u,['b2b3','b3b8'])
    with pytest.raises(ValueError):replay_rule(u,['b2c3'])


def test_mate_stalemate_distinct_and_no_king_capture():
    for key,method in [('rules-mate-queen','is_checkmate'),('rules-make-stalemate','is_stalemate')]:
        u=BY_ID[key];r=replay_rule(u,u['example_actions']);assert getattr(chess.Board(r['fen']),method)()
        assert chess.popcount(chess.Board(r['fen']).kings)==2


def test_ep_actual_prelude_and_expired_rights():
    u=BY_ID['rules-ep-now'];p=u['prelude'];b=chess.Board(p['before_fen'])
    for m in p['moves']:assert chess.Move.from_uci(m) in b.legal_moves;b.push_uci(m)
    assert b.fen(en_passant='fen')==u['fen'] and b.has_legal_en_passant()
    r=replay_rule(u,u['example_actions']);after=chess.Board(r['fen'])
    assert after.piece_at(chess.C5) is None and after.piece_at(chess.C6)==chess.Piece(chess.PAWN,chess.WHITE)
    expired=BY_ID['rules-ep-expired'];assert not chess.Board(expired['fen']).has_legal_en_passant()


def test_all_rule_saves_reload_and_preserve_old_state(movement):
    c,server=movement;before=copy.deepcopy(dict(server.get_state('INTRO-QA')))
    for i,u in enumerate(RULE_UNITS):
        s=start(c,unit=u['id'],request='rules-start-'+str(i))
        assert 'example_actions' not in s['active']
        assert s['active']['initial_fen']==u['fen']
        s=save(c,s,u['example_actions']);assert s['active']['done']
        assert s['active']['result']=='rule_applied'
        assert c.get('/api/movement').json()==s
    after=dict(server.get_state('INTRO-QA'));after.pop('movement_v1');assert after==before


def test_rule_failed_run_preserved_on_explicit_restart(movement):
    c,server=movement;s=start(c,unit='rules-give-check')
    s=save(c,s,['b2b3']);assert s['active']['failed'] and not s['active']['done']
    assert s['summary']['completed']==0
    assert c.post('/api/movement/save',json=body(s,['b2b3','b3b8'])).status_code==400
    s=start(c,s,unit='rules-give-check',action='restart',request='restart-rules')
    assert server.get_state('INTRO-QA')['movement_v1']['history'][0]['moves']==['b2b3']
    s=save(c,s,['b2b8']);assert s['active']['done']

def test_failed_preparation_records_actual_move_without_invented_reply():
    u=BY_ID['rules-check-plan'];r=replay_rule(u,['b2b8'])
    b=chess.Board(u['fen']);b.push_uci('b2b8')
    assert r['failed'] and not r['done']
    assert r['fen']==b.fen(en_passant='fen') and r['played']==['b2b8']
    assert not r['opponent_example']
