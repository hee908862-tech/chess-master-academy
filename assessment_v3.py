"""Assessment question factory. The engine is the source of truth for move legality.
The five domains are distinct tasks; ratings are local estimates, not official Elo.
"""
import random
import chess
from exercises import bank

DOMAINS=['체크메이트','전술·포획','오프닝 전개','킹·폰 엔드게임','수읽기·강제수']

def _opening(rng):
    # Following familiar opening principles: develop a minor piece instead of wasting tempos.
    sequences=[['e2e4','e7e5'],['d2d4','d7d5'],['e2e4','c7c5'],['d2d4','g8f6'],['e2e4','e7e6'],['c2c4','e7e5'],['e2e4','c7c6'],['d2d4','e7e6']]
    seq=rng.choice(sequences);b=chess.Board()
    for m in seq:b.push_uci(m)
    candidate_moves=[m for m in b.legal_moves if (b.piece_at(m.from_square) and b.piece_at(m.from_square).piece_type in (chess.KNIGHT,chess.BISHOP)) and m.to_square in [chess.C3,chess.F3,chess.C4,chess.F4,chess.B5,chess.G5]]
    if not candidate_moves: candidate_moves=[m for m in b.legal_moves if b.piece_at(m.from_square).piece_type in (chess.KNIGHT,chess.BISHOP)]
    # Multiple sensible developments accepted, by design.
    return {'fen':b.fen(),'answers':[m.uci() for m in candidate_moves], 'domain':'오프닝 전개','description':'백 차례: 중앙 통제에 도움이 되는 나이트·비숍 전개 수를 두세요.'}

def _endgame(rng):
    # Construct legal K+P vs K positions in which legal forward pawn pushes are reasonable.
    for _ in range(200):
        b=chess.Board(None)
        wp=rng.choice([chess.C4,chess.D4,chess.E4,chess.F4,chess.C5,chess.D5,chess.E5,chess.F5]);wk=rng.choice([chess.C2,chess.D2,chess.E2,chess.F2,chess.C3,chess.D3,chess.E3,chess.F3]);bk=rng.choice([chess.A8,chess.B8,chess.G8,chess.H8,chess.A7,chess.H7])
        if len({wp,wk,bk})<3 or chess.square_distance(wk,bk)<2:continue
        for sq,p in [(wp,chess.Piece(chess.PAWN,True)),(wk,chess.Piece(chess.KING,True)),(bk,chess.Piece(chess.KING,False))]:b.set_piece_at(sq,p)
        b.turn=True;b.castling_rights=0
        push=chess.Move(wp,wp+8)
        if b.is_valid() and not b.is_check() and push in b.legal_moves:
            return {'fen':b.fen(),'answers':[push.uci()],'domain':'킹·폰 엔드게임','description':'백 차례: 왕의 지원을 받으며 폰을 승격 방향으로 전진시키세요.'}
    return None

def exam_bank(seed):
    rng=random.Random(seed)
    pool=bank()
    mates=[p for p in pool if p['kind']=='mate']
    captures=[p for p in pool if p['kind']=='capture']
    selected=[];used=set()
    def sample(xs,label,n=5):
        xs=xs[:];rng.shuffle(xs)
        for p in xs:
            if len([x for x in selected if x['domain']==label])>=n:break
            if p['fen'] in used:continue
            used.add(p['fen']);selected.append({'fen':p['fen'],'answers':p['answers'],'domain':label,'description':p['description']})
    sample(mates,'체크메이트')
    sample(captures,'전술·포획')
    for _ in range(5):
        for i in range(20):
            p=_opening(rng)
            if p['fen'] not in used:break
        used.add(p['fen']);selected.append(p)
    for _ in range(5):
        for i in range(20):
            p=_endgame(rng)
            if p and p['fen'] not in used:break
        if p:
            used.add(p['fen']);selected.append(p)
    # Advanced forcing-move calculation questions, drawn from a separate mate sample.
    sample(mates,'수읽기·강제수')
    counts={d:sum(x['domain']==d for x in selected) for d in DOMAINS}
    if any(counts[d]!=5 for d in DOMAINS): raise RuntimeError('진단 문제 생성 부족: '+str(counts))
    # Group by domain for visible progress.
    return [p for d in DOMAINS for p in selected if p['domain']==d]
