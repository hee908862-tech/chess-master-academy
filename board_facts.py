"""Read-only geometry after a confirmed learning move; never a best-move proof."""
import chess


def learning_facts(card, session):
    if not session.get('done') or not (session.get('outcome') or {}).get('success'):
        return None
    line = session.get('moves') or card.get('line', [])[:1]
    if not line:
        return None
    try:
        board = chess.Board(card['fen'])
        own = board.turn
        last = None
        for uci in line:
            move = chess.Move.from_uci(uci)
            if move not in board.legal_moves:
                return None
            if board.turn == own:
                last = move
            board.push(move)
        if board.fen() != session['fen'] or not last:
            return None
        piece = board.piece_at(last.to_square)
        if not piece or piece.color != own:
            return None
        arrows = []
        for target in sorted(board.attacks(last.to_square)):
            occupant = board.piece_at(target)
            if occupant:
                arrows.append({'from':chess.square_name(last.to_square), 'to':chess.square_name(target),
                               'kind':'protect' if occupant.color == own else 'attack'})
        arrows = arrows[:8]
        if not arrows:
            return None
        labels = [f"{a['from']} → {a['to']} {'보호' if a['kind']=='protect' else '공격'}" for a in arrows]
        return {'fen':board.fen(), 'arrows':arrows,
                'note':'현재 배치의 관계: '+', '.join(labels)+'. 실선은 공격, 점선은 보호입니다. 공격받음이 강제 손실이라는 뜻은 아니며 이 관계만으로 유일한 최선 수를 증명하지 않습니다.'}
    except (ValueError, KeyError, TypeError):
        return None
