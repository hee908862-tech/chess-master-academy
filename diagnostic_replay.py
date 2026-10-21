"""Derive legal replay frames without writes, exposure events or grading."""
import chess


def replay_snapshot(item, played=None):
    try:
        fen = item['fen']
        if len(fen.split()) != 6:
            raise ValueError('incomplete FEN')
        board = chess.Board(fen)
        if not board.is_valid():
            raise ValueError('invalid position')
        line = item['line'] if played is None else played
        if not line:
            raise ValueError('missing line')
        frames = [{'fen': fen, 'move': None, 'san': '처음 · 정답 첫 수 이전'}]
        for uci in line:
            move = chess.Move.from_uci(uci)
            if move not in board.legal_moves:
                raise ValueError('illegal continuation')
            san = board.san(move)
            board.push(move)
            frames.append({'fen': board.fen(en_passant='fen'), 'move': uci, 'san': san})
        return {'available': True, 'side': 'white' if chess.Board(fen).turn else 'black',
                'frames': frames, 'basis': '실제 완료 수순' if played is not None else '저장된 기준 수순'}
    except (KeyError, TypeError, ValueError, IndexError):
        return {'available': False, 'frames': [], 'reason': '저장된 시작 위치 또는 수순이 불완전해 재생하지 않습니다. 기존 채점은 유지됩니다.'}
