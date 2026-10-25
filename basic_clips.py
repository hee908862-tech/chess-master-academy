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
    return dict(unit_id=unit['id'], name=unit['name'], side=unit.get('side', 'white'),
                label='이 문제의 모범 예시 · 정답 도움 · 진단 점수와 별도', frames=frames)
