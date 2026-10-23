"""Authored solving-performance score, separate from preserved ability indicators.

Pure functions; no persistence, retroactive rescore, engine calls, or inferred goal
types. Time changes a bounded performance bonus, never the correctness verdict.
"""
import copy
from decimal import Decimal, ROUND_HALF_UP
import math

import chess
from competencies import line_positions

VERSION = 'solving-performance-v1'
TIMING_VERSION = 'solving-time-v1'
TARGET_POLICY_VERSION = 'authored-target-v1'
TYPE_FACTORS = {'mate': Decimal('1'), 'capture': Decimal('1.1'),
                'defense': Decimal('1.2'), 'calculation': Decimal('1.2'),
                'promotion': Decimal('1.3'), 'endgame': Decimal('1.3')}
FAILURES = {'verified_error', 'verified_non_mate', 'not_answered', 'partial_execution', 'skipped'}
NOTE = ('정답 수행과 제한된 시간 가산을 합친 별도 수행 점수입니다. 계수·목표 시간은 저자 설계이며 '
        '교정된 능력·Elo·검증된 난이도 보정이 아닙니다. 기존 점수와 기록은 보존합니다.')


def _clamp(value, low, high):
    return min(high, max(low, value))


def _rounded(value):
    return int(value.quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _points(a, b=Decimal(0)):
    return 1 + _rounded(Decimal(2849) * a + Decimal(150) * b)


def _board(fen):
    if not isinstance(fen, str) or len(fen.split()) != 6:
        raise ValueError('full_fen_required')
    board = chess.Board(fen)
    if not board.is_valid(): raise ValueError('invalid_fen')
    return board


def _source(item):
    board = _board(item.get('fen')); line = item.get('line')
    if not isinstance(line, list) or not line or len(line) % 2 != 1:
        raise ValueError('invalid_original_line')
    own = []
    for i, uci in enumerate(line):
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves: raise ValueError('illegal_original_line')
        if i % 2 == 0:
            count = board.legal_moves.count()
            own.append({'fen': board.fen(), 'move': uci, 'legal_count': count, 'forced': count == 1})
        board.push(move)
    return own


def target(item):
    """Source rating and dominant broad competency only; never infer from tags."""
    rating = item.get('rating'); goal = item.get('competency')
    if not isinstance(goal, str): goal = None
    result = {'version': TARGET_POLICY_VERSION, 'available': False, 'rating': rating if type(rating) in (int, float) and math.isfinite(rating) else None,
              'goal_type': goal, 'choice_count': None, 'forced_count': None,
              'type_factor': float(TYPE_FACTORS[goal]) if goal in TYPE_FACTORS else None,
              'target_seconds': None, 'reason': None, 'authored_assumption': True,
              'formula': 'clamp(30*(1+clamp(rating-600,0,1800)/1200)*(1+0.5*max(choice-1,0)+0.15*forced)*typeFactor,15,300)'}
    try: own = _source(item)
    except (ValueError, TypeError, AttributeError, IndexError): return {**result, 'reason': 'invalid_source_position_or_line'}
    choices = sum(not row['forced'] for row in own); forced = len(own) - choices
    result.update(choice_count=choices, forced_count=forced)
    if result['rating'] is None or result['rating'] <= 0: return {**result, 'reason': 'missing_or_invalid_source_rating'}
    if goal not in TYPE_FACTORS: return {**result, 'reason': 'unsupported_goal_type'}
    r = Decimal(str(rating)); c = Decimal(choices); f = Decimal(forced)
    seconds = Decimal(30) * (1 + _clamp(r - 600, Decimal(0), Decimal(1800)) / 1200)
    seconds *= 1 + Decimal('.5') * max(c - 1, 0) + Decimal('.15') * f
    seconds *= TYPE_FACTORS[goal]
    seconds = _clamp(seconds, Decimal(15), Decimal(300))
    return {**result, 'available': True, 'target_seconds': float(seconds)}


def _prefix(item, own):
    """Count only saved confirmed moves whose original prefix can be checked."""
    confirmed = item.get('correct_plies')
    submitted = item.get('submitted')
    if confirmed is None and item.get('outcome') in ('not_answered', 'skipped') and not submitted:
        confirmed = 0; submitted = []
    if (type(confirmed) is not int or confirmed < 0 or confirmed > len(own)
            or not isinstance(submitted, list) or len(submitted) < confirmed):
        raise ValueError('confirmed_prefix_missing')
    responses = item.get('responses')
    if responses is not None and not isinstance(responses, list): raise ValueError('invalid_saved_responses')
    choices = 0; forced = 0
    for i in range(confirmed):
        row = own[i]
        if submitted[i] != row['move']: raise ValueError('alternative_prefix_not_reconstructed')
        if responses is not None:
            if i >= len(responses): raise ValueError('confirmed_prefix_missing')
            response = responses[i]
            if (response.get('move') != submitted[i] or _board(response.get('fen')).fen() != row['fen']
                    or response.get('expected', row['move']) != row['move']):
                raise ValueError('saved_prefix_conflict')
        if row['forced']: forced += 1
        else: choices += 1
    return {'confirmed_own_moves': confirmed, 'confirmed_choices': choices, 'confirmed_forced': forced}


def _independence(item):
    reasons = []
    if item.get('helped') or item.get('revealed') or (type(item.get('hint_level')) is int and item['hint_level'] > 0):
        reasons.append('assisted')
    elif item.get('helped') is not False: reasons.append('assistance_unknown')
    if item.get('app_new') is False: reasons.append('previously_exposed')
    elif item.get('app_new') is not True: reasons.append('exposure_unknown')
    if item.get('first_attempt') is False: reasons.append('repeated_attempt')
    elif item.get('first_attempt') is not True: reasons.append('attempt_order_unknown')
    if item.get('independent') is not True: reasons.append('independence_unconfirmed')
    return reasons


def _time_bonus(item, tgt, independent, source_ok):
    value = item.get('solving_time')
    measured = value if isinstance(value, dict) and value.get('version') == TIMING_VERSION else {}
    duration = measured.get('active_ms')
    result = {'status': 'not_eligible', 'active_ms': duration if type(duration) is int and duration >= 0 else None,
              'measurement_status': measured.get('status', 'unmeasured'),
              'flags': measured.get('flags', []) if isinstance(measured.get('flags', []), list) else [],
              'reason': None, 'B': Decimal(0)}
    # Wrong/unfinished or assisted work cannot gain points by being fast.
    if item.get('outcome') != 'completed': return {**result, 'reason': 'goal_not_completed'}
    if not independent: return {**result, 'reason': 'not_independent'}
    if source_ok and tgt['choice_count'] == 0: return {**result, 'reason': 'all_moves_forced'}
    if not isinstance(value, dict) or value.get('version') != TIMING_VERSION:
        return {**result, 'status': 'unmeasured', 'reason': 'solving_time_unmeasured', 'B': None}
    status = value.get('status'); duration = value.get('active_ms'); flags = value.get('flags', [])
    if not isinstance(flags, list) or any(not isinstance(flag, str) for flag in flags):
        return {**result, 'status': 'uncertain', 'reason': 'invalid_time_flags', 'B': None}
    if duration is not None and (type(duration) is not int or duration < 0):
        return {**result, 'status': 'uncertain', 'reason': 'invalid_active_time', 'B': None}
    result['active_ms'] = duration
    if status == 'interrupted':
        return {**result, 'status': 'interrupted', 'reason': 'explicit_interruption_no_time_bonus'}
    if status in ('uncertain', 'unmeasured'):
        return {**result, 'status': status, 'reason': 'solving_time_' + status, 'B': None}
    if status == 'valid' and duration == 0:
        return {**result, 'status': 'uncertain', 'reason': 'zero_duration_below_resolution', 'B': None}
    if status != 'valid' or duration is None or duration <= 0 or flags:
        return {**result, 'status': 'uncertain', 'reason': 'invalid_or_flagged_valid_time', 'B': None}
    if not tgt['available']:
        return {**result, 'status': 'uncertain', 'reason': 'target_time_unavailable', 'B': None}
    seconds = Decimal(duration) / 1000; deadline = Decimal(str(tgt['target_seconds']))
    bonus = _clamp(Decimal(2) - seconds / deadline, Decimal(0), Decimal(1))
    return {**result, 'status': 'valid', 'reason': None, 'B': bonus}


def _calculate(item):
    tgt = target(item); reasons = []; outcome = item.get('outcome')
    independent_reasons = _independence(item); independent = not independent_reasons
    execution = {'original_choices': tgt['choice_count'], 'original_forced': tgt['forced_count'],
                 'confirmed_own_moves': None, 'confirmed_choices': None, 'confirmed_forced': None,
                 'partial_fraction': None, 'is_key_skill_estimate': False}
    own = None
    try: own = _source(item)
    except (ValueError, TypeError, AttributeError, IndexError): pass
    a = None
    if outcome == 'completed':
        if item.get('complete') is False: reasons.append('conflicting_completion_record')
        else: a = Decimal(1)
    elif outcome in FAILURES:
        if own is None: reasons.append('confirmed_prefix_unavailable')
        else:
            try:
                prefix = _prefix(item, own); execution.update(prefix)
                count = tgt['choice_count']
                fraction = Decimal(prefix['confirmed_choices']) / count if count else Decimal(0)
                execution['partial_fraction'] = float(fraction)
                a = min(Decimal('.5'), Decimal('.5') * fraction)
            except (ValueError, TypeError, AttributeError, IndexError) as exc:
                reasons.append(str(exc) if isinstance(exc, ValueError) else 'invalid_confirmed_prefix')
    else: reasons.append('outcome_unresolved')
    if own is not None and outcome == 'completed':
        try: execution.update(_prefix(item, own))
        except (ValueError, TypeError, AttributeError, IndexError): pass
    time = _time_bonus(item, tgt, independent, own is not None)
    b = time.pop('B')
    if a is None: b = None
    if not tgt['available']: reasons.append(tgt['reason'])
    reasons.extend(independent_reasons)
    if b is None and time.get('reason'): reasons.append(time['reason'])
    final = _points(a, b) if a is not None and b is not None and not reasons else None
    base = _points(a) if a is not None else None
    status = 'final' if final is not None else 'practice' if independent_reasons and a is not None else 'held'
    public = {'version': VERSION, 'timing_version': TIMING_VERSION, 'target_policy_version': TARGET_POLICY_VERSION, 'status': status,
              'outcome': outcome, 'A': float(a) if a is not None else None, 'B': float(b) if b is not None else None,
              'base_points': base, 'time_adjustment': final - base if final is not None else None,
              'final_score': final, 'independent': independent, 'target': tgt, 'execution': execution,
              'time': time, 'reasons': list(dict.fromkeys(reasons)), 'rounding': 'ROUND_HALF_UP_combined',
              'accuracy_weight': 2849, 'time_weight': 150, 'authored_assumption': True,
              'preserves_original_score': True, 'note': NOTE}
    return public, a, b


def item_score(item):
    return _calculate(item)[0]


def report_score(report):
    """Every assigned item once, equal weights; never drop unknowns optimistically."""
    unique = []; seen_assignment = {}; duplicate_assignments = 0; conflicts = False
    for index, item in enumerate(report.get('items', [])):
        identity = item.get('id')
        if identity is not None and identity in seen_assignment:
            duplicate_assignments += 1
            if seen_assignment[identity] != item: conflicts = True
            continue
        if identity is not None: seen_assignment[identity] = copy.deepcopy(item)
        unique.append((index, item))
    rows = []; values_a = []; values_b = []; seen_puzzles = set(); seen_positions = set()
    reasons = ['conflicting_duplicate_assignment'] if conflicts else []
    for index, item in unique:
        value, a, b = _calculate(item)
        pid = item.get('puzzle_id'); positions = set()
        try: positions = line_positions(item['fen'], item['line'])
        except (ValueError, TypeError, KeyError): pass
        repeated = bool(pid and pid in seen_puzzles or positions and positions.intersection(seen_positions))
        if pid: seen_puzzles.add(pid)
        seen_positions.update(positions)
        if repeated:
            value.update(independent=False, status='practice', final_score=None, time_adjustment=None)
            value['reasons'].append('repeated_position_in_report')
            value['B']=0 if a is not None else None; b=Decimal(0) if a is not None else None
        rows.append({'item_id': item.get('id'), 'assignment_index': index, **value})
        values_a.append(a); values_b.append(b)
        if value['final_score'] is None: reasons.append('item_not_final')
    n = len(rows)
    mean_a = sum(values_a, Decimal(0)) / n if n and all(v is not None for v in values_a) else None
    mean_b = sum(values_b, Decimal(0)) / n if n and all(v is not None for v in values_b) else None
    if not n: reasons.append('no_assigned_items')
    final = _points(mean_a, mean_b) if mean_a is not None and mean_b is not None and not reasons else None
    base = _points(mean_a) if mean_a is not None else None
    return {'version': VERSION, 'timing_version': TIMING_VERSION, 'target_policy_version': TARGET_POLICY_VERSION, 'status': 'final' if final is not None else 'held',
            'assigned_count': len(report.get('items', [])), 'item_count': n, 'duplicate_assignments': duplicate_assignments,
            'A': float(mean_a) if mean_a is not None else None, 'B': float(mean_b) if mean_b is not None else None,
            'base_points': base, 'time_adjustment': final-base if final is not None else None, 'final_score': final,
            'items': rows, 'reasons': list(dict.fromkeys(reasons)), 'aggregation': 'equal_weight_original_assignments',
            'accuracy_weight':2849,'time_weight':150,'rounding':'ROUND_HALF_UP_combined',
            'authored_assumption': True, 'preserves_original_score': True, 'note': NOTE}
