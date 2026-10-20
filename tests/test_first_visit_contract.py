"""The local demo must remain aligned with the authored first foundation position."""
from pathlib import Path
import chess
from foundation_content import BY_ID

def test_trial_reuses_first_rook_position_and_legal_target():
    step=BY_ID['rook-bishop']['steps'][0]
    source=(Path(__file__).resolve().parents[1]/'public/first-visit.js').read_text()
    assert step['fen'] in source and step['line']==['a1a4']
    board=chess.Board(step['fen']);assert chess.Move.from_uci('a1a4') in board.legal_moves
    assert board.piece_at(chess.A1)==chess.Piece(chess.ROOK,chess.WHITE)
    assert all(board.piece_at(s) is None for s in (chess.A2,chess.A3,chess.A4))
