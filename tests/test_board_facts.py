import chess
from board_facts import learning_facts

def test_confirmed_position_attacks_and_protection_only():
    fen='6k1/8/8/8/n7/8/1P6/R5K1 w - - 0 1'
    b=chess.Board(fen);b.push_uci('a1a2')
    card={'fen':fen,'line':['a1a2']};s={'fen':b.fen(),'done':True,'outcome':{'success':True}}
    facts=learning_facts(card,s)
    assert {(a['to'],a['kind']) for a in facts['arrows']}=={('a4','attack'),('b2','protect')}
    assert '강제 손실' in facts['note']
    for a in facts['arrows']:
        assert chess.parse_square(a['to']) in b.attacks(chess.parse_square(a['from']))
    for change in [{'done':False},{'outcome':{'success':False}},{'fen':chess.STARTING_FEN}]:
        assert learning_facts(card,{**s,**change}) is None

def test_unrecorded_alternative_never_borrows_reference_relationship():
    b=chess.Board();b.push_uci('d2d4')
    assert learning_facts({'fen':chess.STARTING_FEN,'line':['e2e4']},{'fen':b.fen(),'done':True,'outcome':{'success':True}}) is None
