"""Shared, explicitly scoped competency vocabulary; not a calibrated rating scale."""
VERSION = 'competency-v2'
COMPETENCIES = {
 'mate': {'label':'메이트 수순', 'scope':'합법적인 체크메이트 수순 실행', 'measured':True},
 'calculation': {'label':'다중 수 계산', 'scope':'상대 응수 뒤 원본 수순 계속하기', 'measured':True},
 'capture': {'label':'포획·교환 수순', 'scope':'포획 이후 검증된 전술 수순', 'measured':True},
 'defense': {'label':'방어 수순', 'scope':'defensiveMove 원본 전술 과제', 'measured':True},
 'promotion': {'label':'승격 수순', 'scope':'승격 기물 선택을 포함한 수순', 'measured':True},
 'endgame': {'label':'종반 전술 실행', 'scope':'적은 기물의 전술 수순; 종반 전체 숙련도 아님', 'measured':True},
 'strategy': {'label':'전략·계획', 'scope':'검증된 계획 선택 과제가 없어 미측정', 'measured':False},
}


def supports(competency, fen, line, tags):
    """Observable scope only; a generic shared tag does not prove transfer scope."""
    import chess
    try:
        initial=chess.Board(fen); board=initial.copy(); promoted=False
        if not line or len(line)%2!=1 or not initial.is_valid(): return False
        for i,uci in enumerate(line):
            move=chess.Move.from_uci(uci)
            if move not in board.legal_moves: return False
            promoted |= i%2==0 and bool(move.promotion)
            board.push(move)
        return {
            'mate':board.is_checkmate() and any(t.startswith('mateIn') for t in tags),
            'calculation':len(line)>=3,
            'capture':initial.is_capture(chess.Move.from_uci(line[0])),
            'defense':'defensiveMove' in tags,
            'promotion':promoted,
            'endgame':'endgame' in tags and len(initial.piece_map())<=10,
            'strategy':False,
        }.get(competency,False)
    except (ValueError,IndexError): return False
