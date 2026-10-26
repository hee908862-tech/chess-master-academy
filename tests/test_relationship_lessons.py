"""Introduction and guided practice cannot stand in for independent performance."""
import copy
import chess
import pytest
from basic_clips import teaches_relationships, clip, attack_relation
from movement_content import UNITS, BY_ID
from test_movement import movement, start, save, body
from test_onboarding import api
from test_runtime_isolation import runtime


def act(c,s,action,move=''):
    r=c.post('/api/movement/lesson',json=dict(session_id=s['active']['session_id'],revision=s['revision'],action=action,move=move))
    assert r.status_code==200,r.text
    return r.json()


@pytest.mark.parametrize('unit',[u for u in UNITS if teaches_relationships(u)],ids=lambda u:u['id'])
def test_all_relationship_lessons_separate_guided_and_independent(movement,unit):
    c,server=movement
    before=copy.deepcopy(dict(server.get_state('INTRO-QA')))
    s=start(c,unit=unit['id'],independent=False)
    assert s['active']['teaching']['phase']=='explain'
    assert c.post('/api/movement/save',json=body(s,unit['example_actions'])).status_code==409
    s=act(c,s,'guided')
    for action in unit['example_actions']:
        s=act(c,s,'step',action)
        assert s['active']['moves']==[] and not s['active']['done']
        assert s['active']['result'] is None
    assert s['active']['teaching']['guide_done']
    s=act(c,s,'independent')
    assert s['active']['fen']==unit['fen']
    assert 'next_action' not in s['active']['teaching']
    assert 'clip' not in s['active']['teaching']
    s=save(c,s,unit['example_actions'])
    assert s['active']['practice_result']=='independent_application_after_intro'
    assert s['active']['helped'] and s['active']['done']
    after=dict(server.get_state('INTRO-QA'));after.pop('movement_v1');before.pop('movement_v1',None)
    assert after==before


def test_skips_exposure_conflicts_and_legacy_preservation(movement):
    c,server=movement;s=start(c,unit='rules-protect-piece',independent=False)
    old=copy.deepcopy(s)
    s=act(c,s,'skip')
    assert s['active']['teaching']['skipped']
    assert c.post('/api/movement/lesson',json=dict(session_id=old['active']['session_id'],revision=old['revision'],action='guided')).status_code==409
    s=c.post('/api/movement/demo',json=dict(unit_id=s['active']['unit_id'],session_id=s['active']['session_id'],revision=s['revision'])).json()['dashboard']
    s=save(c,s,['a1c1']);assert s['active']['practice_result']=='assisted_application'
    state=server.get_state('INTRO-QA');row=state['movement_v1']['units'][s['active']['unit_id']]
    row.pop('teaching');row.pop('practice_result');server.save_state('INTRO-QA',state)
    before=copy.deepcopy(dict(server.get_state('INTRO-QA')))
    assert c.get('/api/movement').json()['active']['done']
    assert 'teaching' not in c.get('/api/movement').json()['active']
    assert dict(server.get_state('INTRO-QA'))==before


def test_geometry_is_not_legal_capture_and_pawn_forward_is_not_attack():
    # Pinned rook still controls king destinations but cannot legally leave its file.
    b=chess.Board('4k3/4r3/8/8/8/8/4R3/6K1 b - - 0 1')
    assert b.is_pinned(chess.BLACK,chess.E7)
    assert attack_relation(b,chess.E7,chess.F7)['to']=='f7'
    assert chess.Move.from_uci('e7f7') not in b.legal_moves
    b=chess.Board('7k/8/8/8/3P4/8/8/K7 w - - 0 1')
    with pytest.raises(ValueError):attack_relation(b,chess.D4,chess.D5)
    assert attack_relation(b,chess.D4,chess.C5)
    b=chess.Board('7k/8/8/8/3P4/8/3R4/K7 w - - 0 1')
    with pytest.raises(ValueError):attack_relation(b,chess.D2,chess.D6)


def test_each_arrow_belongs_to_its_exact_frame_and_mate_is_all_legal_moves():
    for u in UNITS:
        if not teaches_relationships(u):continue
        frames=clip(u)['frames']
        for f in frames:
            b=chess.Board(f['fen'])
            for a in f.get('arrows',[]):
                assert chess.parse_square(a['to']) in b.attacks(chess.parse_square(a['from']))
        if u['predicate']['type'] in ('mate','stalemate'):
            b=chess.Board(frames[-1]['fen'])
            assert not list(b.legal_moves)
            assert b.is_check()==(u['predicate']['type']=='mate')


def test_pinned_defender_and_king_capture_are_recomputed():
    from basic_rules_content import _protected
    # The white rook geometrically guards c2, but moving off the e-file exposes its king.
    b=chess.Board('4r2k/8/8/8/8/2r5/2N1R3/4K3 b - - 0 1')
    assert chess.C2 in b.attacks(chess.E2)
    assert not _protected(b,chess.C2)
    # Removing the captured rook and moving the king reveals the bishop's attack.
    b=chess.Board('7k/8/8/8/6b1/8/4r3/4K3 w - - 0 1')
    assert chess.Move.from_uci('e1e2') not in b.legal_moves
    after=b.copy();after.remove_piece_at(chess.E1);after.set_piece_at(chess.E2,chess.Piece(chess.KING,chess.WHITE))
    assert after.is_attacked_by(chess.BLACK,chess.E2)


def test_lesson_wrong_account_stale_duplicate_and_out_of_order(movement):
    from fastapi.testclient import TestClient
    c,server=movement;s=start(c,unit='rules-shield-piece',independent=False)
    req=dict(session_id=s['active']['session_id'],revision=s['revision'],action='guided')
    assert TestClient(c.app).post('/api/movement/lesson',json=req).status_code==401
    other=TestClient(c.app);token=other.post('/api/register',json={'code':'RELATION-OTHER','pin':'relation-test-pin'}).json()['token'];other.headers['Authorization']='Bearer '+token
    assert other.post('/api/movement/lesson',json=req).status_code==409
    assert c.post('/api/movement/lesson',json=dict(req,action='independent')).status_code==409
    s=act(c,s,'guided')
    assert c.post('/api/movement/lesson',json=req).status_code==409
    before=copy.deepcopy(dict(server.get_state('INTRO-QA')))
    assert c.post('/api/movement/lesson',json=dict(req,revision=s['revision'],action='step',move='d2d3')).status_code==400
    assert dict(server.get_state('INTRO-QA'))==before


def test_older_client_start_keeps_legacy_contract(movement):
    c,_=movement
    d=c.get('/api/movement').json()
    r=c.post('/api/movement/start',json=dict(unit_id='rules-shield-piece',revision=d['revision'],request_id='legacy-client-start'))
    assert r.status_code==200
    s=r.json();assert 'teaching' not in s['active']
    s=save(c,s,['d2d4']);assert s['active']['done']
    restarted=start(c,s,unit='rules-shield-piece',action='restart',request='new-client-restart',independent=False)
    assert restarted['active']['teaching']['phase']=='explain'
    assert restarted['active']['session_id']!=s['active']['session_id']


def test_linked_guest_keeps_guided_state_and_owner_records(runtime):
    from fastapi.testclient import TestClient
    server,(owner,other)=runtime
    guest=TestClient(server.app)
    credentials=guest.post('/api/guest/start').json()
    guest.headers['Authorization']='Bearer '+credentials['token']
    s=start(guest,unit='rules-shield-piece',independent=False)
    s=act(guest,s,'guided');s=act(guest,s,'step','d2d4')
    before=copy.deepcopy(dict(server.get_state(credentials['code'])))
    account_before=owner.get('/api/movement').json()
    assert owner.post('/api/guest/link',json={'guest_token':credentials['token']}).status_code==200
    assert guest.get('/api/movement').status_code==401
    assert other.post('/api/guest/resume',json={'id':credentials['code']}).status_code==404
    delegated=owner.post('/api/guest/resume',json={'id':credentials['code']}).json()
    resumed=TestClient(server.app,headers={'Authorization':'Bearer '+delegated['token']})
    assert resumed.get('/api/movement').json()==s
    assert owner.get('/api/movement').json()==account_before
    assert dict(server.get_state(credentials['code']))==before
