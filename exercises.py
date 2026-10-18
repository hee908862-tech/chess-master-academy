"""Deterministic, legal-position verified chess learning exercise factory.
Produces varied mate-in-one questions and tactical captures; no answer leakage on GET.
Requires python-chess at runtime. Question correctness is server authoritative.
"""
import random
from functools import lru_cache
import chess

THEMES = ('mate','capture')

def _mate_candidates(rng, count, cap=14000):
    found={}
    tries=0
    while len(found)<count and tries<cap:
        tries+=1
        board=chess.Board(None)
        # white attacking; king/queen/rook vs black king, with occasional defender
        wk,bk=rng.sample(range(64),2)
        if chess.square_distance(wk,bk)<2:continue
        board.set_piece_at(wk,chess.Piece(chess.KING,True))
        board.set_piece_at(bk,chess.Piece(chess.KING,False))
        for typ in rng.sample([chess.QUEEN,chess.ROOK,chess.BISHOP,chess.KNIGHT],2):
            avail=[s for s in range(64) if board.piece_at(s) is None]
            sq=rng.choice(avail)
            board.set_piece_at(sq,chess.Piece(typ,True))
        if rng.random()<.36:
            avail=[s for s in range(64) if board.piece_at(s) is None]
            board.set_piece_at(rng.choice(avail),chess.Piece(rng.choice([chess.PAWN,chess.ROOK,chess.BISHOP]),False))
        board.turn=True
        board.castling_rights=0
        if not board.is_valid() or board.is_check() or board.is_game_over():continue
        mates=[]
        for m in board.legal_moves:
            board.push(m)
            if board.is_checkmate():mates.append(m.uci())
            board.pop()
            if len(mates)>1:break
        if len(mates)==1:
            fen=board.fen()
            found[fen]={'fen':fen,'answers':[mates[0]],'theme':'1수 체크메이트','difficulty':'중급','kind':'mate','description':'백 차례입니다. 단 한 수로 체크메이트하세요.','hint':'킹의 도주 칸을 확인한 뒤 체크하는 수를 찾아보세요.'}
    return list(found.values())

def _capture_candidates(rng, count, cap=9000):
    # position made from legal games; unique best immediate material win where at least 200cp gap
    found={}; tries=0
    val={chess.PAWN:100,chess.KNIGHT:310,chess.BISHOP:325,chess.ROOK:500,chess.QUEEN:900,chess.KING:0}
    while len(found)<count and tries<cap:
        tries+=1
        board=chess.Board()
        for i in range(rng.randrange(10,45)):
            ms=list(board.legal_moves)
            if not ms or board.is_game_over():break
            # Mix random and material-preserving gameplay
            captures=[m for m in ms if board.is_capture(m)]
            board.push(rng.choice(captures if captures and rng.random()<.28 else ms))
        if board.is_game_over() or board.is_check():continue
        if board.turn==False:
            board=board.mirror()
        scored=[]
        for move in board.legal_moves:
            if not board.is_capture(move):continue
            victim=board.piece_at(move.to_square)
            if victim is None:continue
            gain=val[victim.piece_type]
            board.push(move)
            # simple exchange safety: if can be recaptured devalue
            exposed=board.is_attacked_by(board.turn,move.to_square)
            board.pop()
            attacker=board.piece_at(move.from_square)
            if exposed: gain-=val[attacker.piece_type]
            scored.append((gain,move.uci()))
        if not scored:continue
        scored.sort(reverse=True)
        if scored[0][0]<300 or (len(scored)>1 and scored[0][0]-scored[1][0]<250):continue
        fen=board.fen()
        found[fen]={'fen':fen,'answers':[scored[0][1]],'theme':'기물 포획','difficulty':'초급','kind':'capture','description':'백 차례입니다. 가장 가치 있는 기물을 안전하게 잡으세요.','hint':'기물의 가치를 비교하고, 잡은 뒤 되잡히는지도 확인하세요.'}
    return list(found.values())

@lru_cache(maxsize=1)
def bank():
    rng=random.Random(20261019)
    mate=_mate_candidates(rng,50)
    capture=_capture_candidates(rng,50)
    return mate+capture

def public(exercise, identifier):
    return {'id':identifier,'fen':exercise['fen'],'theme':exercise['theme'],'difficulty':exercise['difficulty'],'kind':exercise['kind'],'description':exercise['description']}
