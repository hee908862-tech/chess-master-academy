import copy
import chess
from foundation_content import COURSES,BY_ID
from foundation_server import visual_context,board_for


def test_all_guides_are_legal_and_judgements_do_not_disclose_answer():
    assert len(COURSES)==10 and sum(len(c['steps']) for c in COURSES)==26
    for c in COURSES:
        for i,s in enumerate(c['steps']):
            for ply in range(0,len(s.get('line',[])) or 1,2):
                p={'ply':ply};before=copy.deepcopy(p);b=board_for(s,p)
                v=visual_context(c['id'],i,s,p,b)
                assert v['fen']==b.fen() and p==before
                guides=[a for a in v['arrows'] if a['kind']=='guide']
                if s['kind']=='judge':assert not guides and v['ending'] is None
                else:
                    u=s['line'][ply];assert chess.Move.from_uci(u) in b.legal_moves
                    assert (guides[0]['from'],guides[0]['to'])==(u[:2],u[2:4])


def test_ep_demo_is_authored_legal_and_matches_current_position():
    s=BY_ID['en-passant']['steps'][0];b=board_for(s,{})
    demo=visual_context('en-passant',0,s,{},b)['demonstration']
    prior=chess.Board(demo['before_fen']);m=chess.Move.from_uci(demo['move'])
    assert m in prior.legal_moves;prior.push(m)
    assert prior.fen()==demo['after_fen']==b.fen()
    assert b.is_en_passant(chess.Move.from_uci('e5d6')) and '교육 예시' in demo['label']


def test_threat_and_protection_are_actual_attacks_not_move_guides():
    s=BY_ID['value-protection']['steps'][1];b=board_for(s,{})
    arrows=visual_context('value-protection',1,s,{},b)['arrows']
    assert {(a['kind'],a['from'],a['to']) for a in arrows}=={('guide','a4','b3'),('threat','a8','a4')}
    s=BY_ID['value-protection']['steps'][0];p={'ply':1,'solved':True};b=board_for(s,p)
    assert any(a['kind']=='protect' for a in visual_context('value-protection',0,s,p,b)['arrows'])


def test_pinned_attacker_still_checks_and_terminal_labels_are_distinct():
    b=chess.Board('4k3/8/8/8/8/8/2K1r3/4R3 w - - 0 1')
    assert b.is_pinned(chess.BLACK,chess.E2) and b.is_check()
    s={'kind':'judge'};v=visual_context('test',0,s,{},b)
    assert v['check_king']=='c2' and v['checkers']==['e2']
    for fen,ending in [('7k/6Q1/5K2/8/8/8/8/8 b - - 0 1','checkmate'),('7k/5Q2/6K1/8/8/8/8/8 b - - 0 1','stalemate')]:
        v=visual_context('test',0,s,{'solved':True},chess.Board(fen));assert v['ending']==ending
