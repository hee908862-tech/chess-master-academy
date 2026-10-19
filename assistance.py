"""Game-local assistance provenance. Never infer per-move help from legacy ply numbers."""
import copy
import secrets


def position_key(board):
    return ' '.join(board.fen().split()[:4])


def ledger(game, complete=False):
    return game.setdefault('assistance', {'version': 1, 'complete': complete,
        'events': [], 'positions': {}, 'moves': []})


def event(game, board, kind, **details):
    log = ledger(game)
    item = {'id': secrets.token_hex(12), 'kind': kind, 'ply': len(game['moves']) + 1,
            'fen': board.fen(), 'prefix': list(game['moves']), **details}
    log['events'].append(item)
    record = log['positions'].setdefault(position_key(board), {'hint': [], 'undo': []})
    record[kind].append(item['id'])
    return item


def record_move(game, board, move):
    log = ledger(game)
    while len(log['moves']) < len(game['moves']): log['moves'].append(None)
    known = log['positions'].get(position_key(board), {'hint': [], 'undo': []})
    events = {e['id']: e for e in log['events']}
    log['moves'].append({'id': secrets.token_hex(12), 'ply': len(game['moves']) + 1,
        'fen': board.fen(), 'move': move.uci(), 'hint_ids': list(known['hint']),
        'adopted_hint_ids': [i for i in known['hint'] if events[i]['recommended'] == move.uci()],
        'undo_ids': list(known['undo'])})


def record_undo(game, before_moves, before_board, restored_board):
    log = ledger(game)
    cut = len(game['moves'])
    removed = []
    b = restored_board.copy()
    for index, uci in enumerate(before_moves[cut:], cut):
        removed.append({'ply': index + 1, 'fen': b.fen(), 'move': uci,
                        'assistance': copy.deepcopy(log['moves'][index]) if index < len(log['moves']) else None})
        b.push_uci(uci)
    log['moves'] = log['moves'][:cut]
    event(game, restored_board, 'undo', from_fen=before_board.fen(), removed=removed)


def archive(game):
    return {'session_id': game.get('session_id'), 'assistance': copy.deepcopy(game['assistance'])} if 'assistance' in game else {}


def review(game, ply, fen, move):
    log = game.get('assistance') or {}
    rows = log.get('moves', [])
    row = rows[ply - 1] if ply <= len(rows) else None
    if not row or (row['ply'], row['fen'], row['move']) != (ply, fen, move):
        return {'known': False, 'hint_viewed': None, 'hint_adopted': None, 'undo_replayed': None}
    absent = False if log.get('complete') else None
    return {'known': bool(log.get('complete') or row['hint_ids'] or row['undo_ids']), 'hint_viewed': True if row['hint_ids'] else absent,
            'hint_adopted': bool(row['adopted_hint_ids']) if row['hint_ids'] else absent, 'undo_replayed': True if row['undo_ids'] else absent,
            'hint_ids': row['hint_ids'], 'undo_ids': row['undo_ids'], 'move_id': row['id']}
