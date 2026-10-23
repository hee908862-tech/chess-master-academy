"""Bounded, read-only rules observations. Never a skill score or engine analysis."""
import hashlib
import chess
from assistance import review as assistance_review

VERSION = 'game-rules-observations-v1'
MAX_USER_MOVES = 80
MAX_OPERATIONS = 20000
MAX_PLIES = 400


class BudgetExceeded(Exception):
    pass


def observe_game(game, key, max_user_moves=MAX_USER_MOVES, max_operations=MAX_OPERATIONS):
    operations = 0

    def mate_moves(board):
        nonlocal operations
        result = []
        for move in list(board.legal_moves):
            if operations >= max_operations:
                raise BudgetExceeded
            operations += 1
            child = board.copy(stack=False)
            child.push(move)
            if child.is_checkmate():
                result.append(move.uci())
        return sorted(result)

    rows, seen, previous = [], {}, {}
    processed = 0
    reason = None
    moves = game.get('moves', [])
    side = game.get('color')
    expected = None
    try:
        board = chess.Board(game.get('initial_fen', chess.STARTING_FEN))
        if not board.is_valid() or side not in ('white', 'black') or not isinstance(moves, list):
            raise ValueError
        human = side == 'white'
        expected = sum((i % 2 == 0) == (board.turn == human) for i in range(len(moves)))
        for index, uci in enumerate(moves):
            if index >= MAX_PLIES:
                reason = 'ply_limit'
                break
            move = chess.Move.from_uci(uci)
            # A claimable draw is a player's option, not an automatic ending.
            if board.is_game_over(claim_draw=False) or move not in board.legal_moves:
                reason = 'invalid_or_terminated_sequence'
                break
            if board.turn != human:
                board.push(move)
                continue
            if processed >= max_user_moves:
                reason = 'user_move_limit'
                break
            before = board.fen()
            child = board.copy(stack=True)
            child.push(move)
            # Entire decision is committed only after its rule checks complete.
            own_mates = mate_moves(board)
            replies = [] if child.is_game_over(claim_draw=False) else mate_moves(child)
            safe = []
            if replies:
                # One witness proves immediate mate was avoidable; not a best-move claim.
                for alternative in board.legal_moves:
                    if alternative == move:
                        continue
                    candidate = board.copy(stack=True)
                    candidate.push(alternative)
                    if candidate.is_game_over(claim_draw=False) or not mate_moves(candidate):
                        safe.append(alternative.uci())
                        break
            facts = []
            if own_mates:
                facts.append(('mate_in_one', 'executed' if uci in own_mates else 'other_move', own_mates, []))
            if replies and safe:
                facts.append(('allows_mate_in_one', 'allowed', safe, replies))
            active_kinds = set()
            for kind, outcome, alternatives, opponent in facts:
                active_kinds.add(kind)
                position = ' '.join(before.split()[:4])
                signature = (kind, position)
                # Consecutive occurrences are one conservative episode, not independent samples.
                group = seen.get(signature) or previous.get(kind)
                counted = group is None
                row_id = hashlib.sha256(f'{VERSION}|{key}|{index+1}|{kind}'.encode()).hexdigest()[:24]
                group = group or row_id
                seen[signature] = group
                previous[kind] = group
                rows.append({'id': row_id, 'group_id': group, 'ply': index+1,
                    'before_fen': before, 'after_fen': child.fen(), 'played_uci': uci,
                    'kind': kind, 'outcome': outcome, 'alternatives': alternatives,
                    'alternatives_complete': kind == 'mate_in_one', 'opponent_mates': opponent,
                    'assistance': assistance_review(game, index+1, before, uci),
                    'counted': counted, 'source': 'legal_rules', 'pv': None})
            previous = {k: v for k, v in previous.items() if k in active_kinds}
            processed += 1
            board.push(move)
    except BudgetExceeded:
        reason = 'rule_operation_limit'
    except (ValueError, TypeError, KeyError, IndexError):
        reason = 'invalid_saved_sequence'
    counted = [r for r in rows if r['counted']]
    return {'version': VERSION, 'game_key': key,
        'status': 'complete' if reason is None else 'partial' if processed else 'unavailable',
        'source': 'legal_rules', 'rows': rows,
        'summary': {'opportunities': sum(r['kind'] == 'mate_in_one' for r in counted),
            'executed': sum(r['outcome'] == 'executed' for r in counted),
            'other_move': sum(r['outcome'] == 'other_move' for r in counted),
            'allowed': sum(r['outcome'] == 'allowed' for r in counted),
            'excluded_duplicates': len(rows)-len(counted)},
        'coverage': {'user_moves': expected, 'processed_user_moves': processed,
            'rule_operations': operations, 'limits': {'user_moves': max_user_moves,
                'rule_operations': max_operations, 'plies': MAX_PLIES}, 'reason': reason},
        'conditions': {'session_id': game.get('session_id'), 'color': side,
            'difficulty': game.get('difficulty'), 'time_mode': game.get('time_mode', 'unknown'),
            'termination': game.get('termination'), 'engine': game.get('engine'),
            'ai_execution': game.get('ai_execution'),
            'assistance_version': (game.get('assistance') or {}).get('version'),
            'assistance_complete': bool((game.get('assistance') or {}).get('complete'))},
        'unmeasured': ['fork', 'pin', 'material_gain', 'general_promotion', 'positional_play', 'time_pressure'],
        'note': '합법수로 확인한 한 수 메이트 장면만 관찰합니다. 다른 수는 당시 즉시 메이트를 선택하지 않았다는 뜻이며 패배 원인이나 실력 점수가 아닙니다. 연속·반복 위치는 한 기회 묶음으로 표시합니다. 도움 기록 없음은 도움을 안 받았다는 뜻이 아닙니다. 미등장 기술은 미측정입니다.'}
