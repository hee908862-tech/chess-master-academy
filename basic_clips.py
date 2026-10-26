"""Original lesson demonstrations, verified against the same legal lesson rules.

No engine evaluation or assessment writes. Frames always begin at the lesson's
initial position; opponent replies are educational examples, not best-play claims.
"""
import chess
from basic_rules_content import replay_rule


def clip(unit):
    result = replay_rule(unit, unit['example_actions'])
    if not result['done'] or result['failed']:
        raise ValueError('시연의 목표를 검증하지 못했어요.')
    board = chess.Board(unit['fen'])
    frames = []

    def frame(text, move=None, marks=()):
        frames.append(dict(fen=board.fen(en_passant='fen'), text=text,
                           move=move, marks=list(marks), turn='백' if board.turn else '흑'))

    frame(unit['goal'])
    if unit['kind'] == 'move':
        for value in result['played']:
            move = chess.Move.from_uci(value)
            if move not in board.legal_moves:
                raise ValueError('시연에 불법 수가 있어요.')
            side = '백' if board.turn else '흑'
            reply = board.turn != chess.Board(unit['fen']).turn
            san = board.san(move)
            promotion = move.promotion
            board.push(move)
            text = f'{side} {san} · ' + ('교육용 응수예요.' if reply else '목표를 향한 예시 수예요.')
            if promotion:
                text = f'{side} {san} · 폰이 {chess.piece_name(promotion)}으로 승격했어요.'
                text = text.replace('queen', '퀸').replace('rook', '룩').replace('bishop', '비숍').replace('knight', '나이트')
            if board.is_check():
                text += ' 체크메이트예요.' if board.is_checkmate() else ' 체크예요.'
            frame(text, value, [move.from_square, move.to_square])
            frames[-1]['marks'] = [chess.square_name(s) for s in frames[-1]['marks']]
    else:
        for index, action in enumerate(unit['example_actions'], 1):
            state = replay_rule(unit, unit['example_actions'][:index])
            board = chess.Board(state['fen'])
            frame('이 칸을 확인해요.' if unit['kind'] == 'square' else '말을 시작 칸에 놓아요.', marks=[action.split(':')[-1]])
    frame(unit.get('reason', '목표를 확인했어요. 이제 직접 해보세요.'))
    if unit['id'] == 'rules-pawn-promotion':
        frames[0]['text'] = '백 차례 · e7 폰을 끝줄로 보내고 승격할 말을 골라요. 예시는 퀸이에요.'
        frames[-2]['text'] = '백 Qe4 · 승격한 퀸은 이제 세로로도 움직일 수 있어요.'
    if unit['id'] == 'rules-shield-piece':
        frames[0].update(text='비숍 g7의 대각선 끝에 룩 a1이 있어요.', marks=['g7','f6','e5','d4','c3','b2','a1'])
        frames[1].update(text='백 d4 · 폰이 공격길 d4를 막아요. d3는 이 길 밖이에요.', marks=['g7','f6','e5','d4'])
    if unit['id'] == 'rules-make-stalemate':
        assert board.is_stalemate()
        frame('흑 차례 · h8의 킹은 지금 체크가 아니에요.', marks=['h8'])
        for square in ['g8', 'g7', 'h7']:
            attackers = board.attackers(chess.WHITE, chess.parse_square(square))
            assert attackers
            frame(f'{square}은 백의 공격을 받아 갈 수 없어요.', marks=[square] + [chess.square_name(s) for s in attackers])
        frame('체크는 아니지만 흑의 합법 수가 0개 · 스테일메이트, 무승부예요.', marks=['h8','g8','g7','h7'])
    if teaches_relationships(unit):
        frames = relationship_frames(unit, frames)
    return dict(unit_id=unit['id'], name=unit['name'], side=unit.get('side', 'white'),
                label='이 문제의 모범 예시 · 정답 도움 · 진단 점수와 별도', frames=frames)

# New sessions use this sequence; historical sessions keep their saved contract.
RELATION_STAGES = {'protection', 'combat', 'check1', 'outOfCheck', 'checkmate1', 'stalemate'}
RELATION_IDS = {'rules-castle-attacked', 'rules-value-safety', 'rules-value-legal-first', 'rules-check-plan'}
PIECE_NAMES = {chess.PAWN: '폰', chess.KNIGHT: '나이트', chess.BISHOP: '비숍',
               chess.ROOK: '룩', chess.QUEEN: '퀸', chess.KING: '킹'}


def teaches_relationships(unit):
    return unit.get('stage') in RELATION_STAGES or unit['id'] in RELATION_IDS


def piece_label(board, square):
    piece = board.piece_at(square)
    return ('백 ' if piece.color else '흑 ') + PIECE_NAMES[piece.piece_type] + ' ' + chess.square_name(square)


def attack_relation(board, source, target):
    """Geometric attack, including pinned pieces; never a legal-capture assertion."""
    if target not in board.attacks(source):
        raise ValueError('현재 보드에 없는 공격 관계')
    a, b = chess.square_name(source), chess.square_name(target)
    label = piece_label(board, source) + ' → ' + (piece_label(board, target) if board.piece_at(target) else b) + ' 공격'
    relation = {'from': a, 'to': b, 'kind': 'attack', 'label': label,
                'path': [a] + [chess.square_name(s) for s in chess.SquareSet(chess.between(source, target))] + [b]}
    if board.piece_type_at(source) == chess.KNIGHT:
        relation['via'] = b[0]+a[1] if abs(chess.square_file(source)-chess.square_file(target))==2 else a[0]+b[1]
        relation['label'] += ' · 중간 칸은 뛰어넘어요'
    return relation


def threats(board, side, target=None):
    targets = [chess.parse_square(target)] if target else sorted(board.pieces(chess.KING, side)) + [s for s,p in sorted(board.piece_map().items()) if p.color == side and p.piece_type != chess.KING]
    return [attack_relation(board, a, t) for t in targets for a in sorted(board.attackers(not side, t))]


def relationship_frames(unit, frames):
    """One relation per frame, recalculated at that exact position."""
    side = chess.Board(unit['fen']).turn
    output = []
    def add(fen, text, arrows=(), marks=(), move=None):
        b = chess.Board(fen)
        output.append(dict(fen=fen, text=text, arrows=list(arrows), marks=list(marks), move=move,
                           turn='백' if b.turn else '흑'))
    for i, frame in enumerate(frames):
        board = chess.Board(frame['fen'])
        output.append(frame)
        if i == 0 or frame.get('move'):
            relations = threats(board, board.turn if board.is_check() else side)
            if i == 0 and not relations:
                predicate = unit['predicate']['type']
                if predicate == 'attacked_squares':
                    target = chess.parse_square(unit['predicate']['squares'][0])
                    relations = [attack_relation(board,a,target) for a in sorted(board.attackers(not side,target))]
                elif predicate in ('mate','stalemate'):
                    king = board.king(not side)
                    candidates = [(a,t) for t in chess.SquareSet(chess.BB_KING_ATTACKS[king]) for a in sorted(board.attackers(side,t))]
                    candidates.sort(key=lambda pair: board.piece_at(pair[0]).piece_type != chess.KING)
                    relations = [attack_relation(board,a,t) for a,t in candidates[:1]]
                elif unit['kind']=='move':
                    move = chess.Move.from_uci(unit['example_actions'][0])
                    if board.is_capture(move):
                        relations = [attack_relation(board,move.from_square,move.to_square)]
            if i == 0 and relations:
                first = relations[0]
                output[-1] = dict(frame, text=first['label'] + (' · 화살촉 쪽 말이 공격받아요.' if board.piece_at(chess.parse_square(first['to'])) else ' · 공격받는 칸으로 킹은 갈 수 없어요.'), arrows=[first], marks=first['path'])
                relations = relations[1:]
            for relation in relations[:3]:
                add(frame['fen'], relation['label'] + ' · 화살촉 쪽 말이 공격받아요.', [relation], relation['path'])
    board = chess.Board(frames[-1]['fen'])
    if unit['predicate']['type'] == 'protect':
        target = chess.parse_square(unit['predicate']['target'])
        enemy = board.copy(); enemy.turn = not side
        captures = [m for m in enemy.legal_moves if m.to_square == target and enemy.is_capture(m)]
        for capture in captures:
            after = enemy.copy(); after.push(capture)
            replies = [m for m in after.legal_moves if m.to_square == target and after.is_capture(m)]
            if replies:
                reply = replies[0]
                add(after.fen(), '상대가 잡는 예시 · ' + piece_label(enemy, capture.from_square) + '이 나이트를 잡았어요.', move=capture.uci())
                relation = attack_relation(after, reply.from_square, target)
                add(after.fen(), '이제 ' + piece_label(after, reply.from_square) + '으로 되잡을 수 있어요. 합법 수로 확인했어요.', [relation], relation['path'])
                after.push(reply)
                add(after.fen(), '되잡기 예시 완료 · 보호는 잡힌 뒤 되잡을 준비예요.', move=reply.uci())
                add(board.fen(), '되잡기는 별도 예시였어요. 모범수 직후 위치로 돌아왔어요.')
                break
    if board.is_checkmate() or board.is_stalemate():
        king = board.king(board.turn)
        legal = list(board.legal_moves)
        assert not legal
        add(board.fen(), ('체크 중이에요.' if board.is_check() else '킹은 체크가 아니에요.') + ' 이제 가능한 대응을 확인해요.', marks=[chess.square_name(king)])
        for destination in sorted(chess.SquareSet(chess.BB_KING_ATTACKS[king])):
            occupant = board.piece_at(destination)
            if occupant and occupant.color == board.turn:
                reason = '내 말이 있어요.'
            else:
                hypothetical = board.copy()
                hypothetical.remove_piece_at(king)
                hypothetical.set_piece_at(destination, chess.Piece(chess.KING, board.turn))
                attackers = sorted(hypothetical.attackers(not board.turn, destination))
                assert attackers, 'Terminal lesson must explain every king destination'
                reason = piece_label(hypothetical, attackers[0]) + '의 공격을 받아요.'
            add(board.fen(), '킹이 ' + chess.square_name(destination) + '으로 가면 ' + reason, marks=[chess.square_name(king), chess.square_name(destination)])
        if board.is_checkmate():
            add(board.fen(), '체크하는 말을 잡아서 해결할 합법 수도 없어요.')
            add(board.fen(), '다른 말로 길을 막아 해결할 합법 수도 없어요.')
        add(board.fen(), '모든 말의 합법 수 0개 · ' + ('체크 중이므로 체크메이트예요.' if board.is_check() else '체크가 아니므로 스테일메이트예요.'))
    return output
