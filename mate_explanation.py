"""Read-only checkmate evidence. Never mutates the training board or adjudicates answers."""
import chess


def explain_mate(board):
    b = board.copy(stack=False)
    if not b.is_valid() or not b.is_checkmate():
        return {'available': False, 'reason': '검증된 최종 체크메이트 위치가 아닙니다. 해설을 추측하지 않습니다.'}
    defender = b.turn
    king = b.king(defender)
    cells = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == dy == 0: continue
            x, y = chess.square_file(king)+dx, chess.square_rank(king)+dy
            if not (0 <= x < 8 and 0 <= y < 8):
                cells.append({'square': None, 'offset': [dx, dy], 'reasons': ['보드 밖'], 'attackers': []})
                continue
            square = chess.square(x,y); piece = b.piece_at(square)
            reasons = []
            if piece and piece.color == defender: reasons.append('수비 측 기물이 점유')
            # Hypothetical king relocation: remove origin and any captured occupant first.
            trial = b.copy(stack=False)
            trial.remove_piece_at(king); trial.remove_piece_at(square)
            trial.set_piece_at(square, chess.Piece(chess.KING, defender))
            attackers = sorted(trial.attackers(not defender, square))
            if attackers: reasons.append('공격 측 기물의 통제')
            if any(trial.piece_type_at(a)==chess.KING for a in attackers): reasons.append('상대 왕과 인접')
            legal = b.is_legal(chess.Move(king,square))
            cells.append({'square': chess.square_name(square), 'offset':[dx,dy], 'reasons':reasons,
                          'legal':legal, 'attackers':[{'square':chess.square_name(a),'piece':trial.piece_at(a).symbol()} for a in attackers]})
    return {'available':True, 'fen':b.fen(), 'king':chess.square_name(king),
            'defender':'white' if defender else 'black', 'checkers':[chess.square_name(s) for s in b.checkers()],
            'legal_replies':b.legal_moves.count(), 'cells':cells,
            'note':'체크 상태이며 합법 대응은 0개입니다. 왕 이동뿐 아니라 체크 기물 포획·차단을 포함해 검사했습니다. 통제 표시는 왕의 원래 칸을 비우고 목적지 기물을 제거한 뒤 계산합니다. 수비 측 점유 칸은 실제로 이동할 수 없는 가상 이동 분석입니다.'}


def finish_line(fen, line):
    b=chess.Board(fen)
    try:
        for move in line:
            b.push_uci(move)
            if b.is_checkmate():break
    except (ValueError, AssertionError):
        return {'available':False,'reason':'정답 수순으로 최종 메이트 위치를 검증하지 못했습니다.'}
    result=explain_mate(b)
    result['source']='정답 후 원본 수순의 최종 위치 · 현재 문항의 실제 진행 보드와 별개'
    return result
