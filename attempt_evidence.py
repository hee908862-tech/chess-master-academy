"""Pure original-attempt evidence and immutable, bounded revalidation proposals.

No DB access, score mutation, Elo estimate, confidence interval, or new 1–3000
formula. Callers supply reports in original assignment order, oldest first.
"""
import copy
import hashlib
import json
import math
import re
from collections import Counter

import chess
from competencies import line_positions
from growth_model import prove_mate_alternative
from diagnosis_timing import public_timing, timing_trend

VERSION = 'original-attempt-evidence-v1'
RESOLUTION_VERSION = 'original-attempt-resolution-v1'
LEGACY_POLICY = 'reference-line-v1'
WRONG = {'verified_error', 'verified_non_mate'}
UNFINISHED = {'not_answered', 'partial_execution'}
PENDING = {'unanswered', 'unobserved'}
TECHNICAL = {'engine_unavailable', 'engine_failure', 'engine_busy', 'diagnosis_busy', 'busy'}


def item_fingerprint(item):
    """Bind a proposal to the complete saved source, not a guessed question ID."""
    raw = json.dumps(item, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _board(fen):
    if not isinstance(fen, str) or len(fen.split()) != 6:
        raise ValueError('full_fen_required')
    b = chess.Board(fen)
    if not b.is_valid():
        raise ValueError('invalid_position')
    return b


def _source(item):
    b = _board(item['fen'])
    line = item['line']
    if not isinstance(line, list) or not line or len(line) % 2 != 1:
        raise ValueError('invalid_reference_line')
    for uci in line:
        move = chess.Move.from_uci(uci)
        if move not in b.legal_moves:
            raise ValueError('illegal_reference_line')
        b.push(move)
    return b


def _mate_bound(item):
    tags=item.get('tags',[])
    if not isinstance(tags,list):raise ValueError('unsupported_objective_or_mate_bound')
    values={int(t[6:]) for t in tags if isinstance(t,str) and re.fullmatch(r'mateIn[1-9][0-9]*',t)}
    required=(len(item.get('line',[]))+1)//2
    if values!={required} or not _source(item).is_checkmate():
        raise ValueError('unsupported_or_conflicting_mate_objective')
    return required


def _mismatch(item):
    """Reconstruct only an unchanged reference prefix; never guess old branches."""
    _source(item)
    submitted = item.get('submitted')
    if not isinstance(submitted, list) or not submitted:
        raise ValueError('no_saved_submission')
    if len(submitted) > (len(item['line']) + 1) // 2:
        raise ValueError('submission_longer_than_reference')
    responses = item.get('responses')
    if responses is not None and (not isinstance(responses, list) or len(responses) != len(submitted)):
        raise ValueError('incomplete_saved_responses')
    b = _board(item['fen'])
    for index, uci in enumerate(submitted):
        expected = item['line'][index * 2]
        if responses is not None:
            response = responses[index]
            if response.get('move') != uci:
                raise ValueError('response_submission_conflict')
            saved = _board(response.get('fen'))
            if saved.fen() != b.fen() or response.get('expected', expected) != expected:
                raise ValueError('nonreference_or_conflicting_prefix')
        move = chess.Move.from_uci(uci)
        if move not in b.legal_moves:
            raise ValueError('illegal_saved_submission')
        if uci != expected:
            if index != len(submitted) - 1:
                raise ValueError('unreconstructible_alternative_prefix')
            return {'response_index': index, 'fen': b.fen(en_passant='fen'), 'move': uci,
                    'expected': expected, 'source': 'saved_response' if responses is not None else 'reconstructed_reference_prefix'}
        b.push(move)
        if index < len(submitted) - 1:
            b.push_uci(item['line'][index * 2 + 1])
    raise ValueError('no_original_mismatch')


def resolve_attempt(item, report_policy=None, *, max_nodes=6000, seconds=.15):
    """Suggest a correction, without applying it or completing unplayed moves.

    Only original unresolved mismatches with a reconstructible reference prefix
    and a validated short mate objective are supported. Positive proof establishes
    the candidate, not the user's execution of its unplayed continuation.
    """
    source_policy = item.get('answer_policy') or report_policy or LEGACY_POLICY
    out = {'version': RESOLUTION_VERSION, 'item_fingerprint': item_fingerprint(item),
           'source_policy': source_policy, 'status': 'unknown', 'reason': None,
           'mismatch': None, 'proof': None, 'suggestion': None}
    if source_policy not in (LEGACY_POLICY, 'goal-alternatives-v1'):
        return {**out, 'reason': 'unsupported_source_policy'}
    if item.get('outcome') not in ('unverified_alternative', 'equivalent_alternative'):
        return {**out, 'reason': 'not_an_unresolved_original_mismatch'}
    try:
        mismatch = _mismatch(item)
        _mate_bound(item)
    except (KeyError, ValueError, TypeError, AttributeError, IndexError) as exc:
        reason = str(exc) if isinstance(exc, ValueError) else 'missing_or_invalid_source'
        return {**out, 'reason': reason}
    out['mismatch'] = mismatch
    try:
        proof = prove_mate_alternative(mismatch['fen'], mismatch['move'], item,
                                      mismatch['response_index'], max_nodes=max_nodes, seconds=seconds)
    except (KeyError, ValueError, TypeError, AttributeError, IndexError):
        return {**out, 'reason': 'invalid_or_unsupported_objective'}
    if not proof:
        return {**out, 'reason': 'unsupported_objective_or_mate_bound'}
    out['proof'] = copy.deepcopy(proof)
    if proof['status'] == 'verified_non_mate':
        return {**out, 'status': 'verified_non_mate', 'reason': proof['reason'],
                'suggestion': {'outcome': 'verified_non_mate', 'full_completion': False, 'final_verified': True}}
    if proof['status'] == 'verified_goal':
        board = _board(mismatch['fen']); board.push_uci(mismatch['move'])
        completed = board.is_checkmate()
        return {**out, 'status': 'verified_goal', 'reason': 'terminal_goal_proved' if completed else 'candidate_proved_continuation_unplayed',
                'suggestion': {'outcome': 'completed' if completed else 'verified_goal',
                               'full_completion': completed, 'final_verified': completed}}
    return {**out, 'reason': proof.get('reason', 'analysis_unknown')}


def _correction(item, report_id, corrections):
    if item.get('outcome') not in ('unverified_alternative','equivalent_alternative'): return None, None
    fingerprint = item_fingerprint(item)
    for record in reversed(corrections):
        resolution = record.get('resolution', record)
        if (record.get('report_id') != report_id or record.get('item_id') != item.get('id')
                or record.get('item_fingerprint', resolution.get('item_fingerprint')) != fingerprint
                or resolution.get('item_fingerprint') != fingerprint
                or resolution.get('version') != RESOLUTION_VERSION):
            continue
        suggestion = resolution.get('suggestion') or {}
        proof = resolution.get('proof') or {}
        if not suggestion.get('final_verified') or proof.get('policy') != 'goal-alternatives-v1':
            continue
        if (suggestion.get('outcome') == 'verified_non_mate' and resolution.get('status') == 'verified_non_mate'
                and proof.get('status') == 'verified_non_mate'):
            return 'verified_non_mate', resolution
        if (suggestion.get('outcome') == 'completed' and suggestion.get('full_completion')
                and resolution.get('status') == 'verified_goal' and proof.get('status') == 'verified_goal'):
            mismatch = resolution.get('mismatch') or {}
            try:
                b = _board(mismatch['fen']); b.push_uci(mismatch['move'])
                if b.is_checkmate(): return 'completed', resolution
            except (KeyError, ValueError, TypeError): pass
    return None, None


def execution_observation(item):
    """Legal-move count distinguishes forced from choice, never key-skill value."""
    result = {'confirmed_own_moves': None, 'required_own_moves': None, 'fraction': None,
              'forced_submissions': 0, 'choice_submissions': 0, 'unreconstructed_submissions': 0,
              'confirmed_forced': 0, 'confirmed_choice': 0,
              'note': '수순 실행 관찰이며 능력 점수나 수의 중요도 가중치가 아닙니다.'}
    try:
        _source(item)
        required = (len(item['line']) + 1) // 2
        confirmed = item.get('correct_plies')
        submitted = item.get('submitted', [])
        if isinstance(confirmed, int) and not isinstance(confirmed, bool) and 0 <= confirmed <= min(required, len(submitted)):
            result.update(confirmed_own_moves=confirmed, required_own_moves=required, fraction=confirmed / required)
        else: result['required_own_moves'] = required
        board = _board(item['fen']); reference_prefix = True
        responses = item.get('responses')
        for i, uci in enumerate(submitted):
            try:
                if responses is not None:
                    if responses[i].get('move') != uci: raise ValueError()
                    current = _board(responses[i]['fen'])
                    if current.turn != _board(item['fen']).turn: raise ValueError()
                elif reference_prefix: current = board.copy()
                else: raise ValueError()
                if chess.Move.from_uci(uci) not in current.legal_moves: raise ValueError()
                kind = 'forced' if current.legal_moves.count() == 1 else 'choice'
                result[kind + '_submissions'] += 1
                if result['confirmed_own_moves'] is not None and i < confirmed: result['confirmed_' + kind] += 1
            except (KeyError, ValueError, TypeError, AttributeError, IndexError):
                result['unreconstructed_submissions'] += 1
            if reference_prefix and 2 * i < len(item['line']) and uci == item['line'][2 * i]:
                board.push_uci(uci)
                if 2 * i + 1 < len(item['line']): board.push_uci(item['line'][2 * i + 1])
            else: reference_prefix = False
    except (KeyError, ValueError, TypeError, AttributeError, IndexError):
        result['unreconstructed_submissions'] = len(item.get('submitted', [])) if isinstance(item.get('submitted'), list) else 0
    return result


def _aggregate(rows):
    original = [r for r in rows if r['classification'] == 'original']
    n = len(original)
    success = sum(r['effective_outcome'] == 'completed' for r in original)
    wrong = sum(r['effective_outcome'] in WRONG for r in original)
    unfinished = sum(r['effective_outcome'] in UNFINISHED for r in original)
    partial = sum(r['effective_outcome']=='partial_execution' for r in original)
    skipped = sum(r['effective_outcome']=='not_answered' or r.get('skipped') for r in original)
    pending = sum(r['effective_outcome'] in PENDING for r in original)
    unresolved = n - success - wrong - unfinished - pending
    unknown = sum(r['eligibility_unknown'] for r in original)
    exclusions = Counter(r['classification'] for r in rows if r['classification'] != 'original')
    eligibility_reasons=Counter(reason for r in original for reason in r['eligibility_unknown_reasons'])
    ratings = sorted(r['rating'] for r in original if r['rating'] is not None)
    bands = sorted({tuple(r['band']) for r in original if r['band'] is not None})
    partial_rows = [r['execution'] for r in original if r['execution']['confirmed_own_moves'] is not None]
    confirmed = sum(r['confirmed_own_moves'] for r in partial_rows)
    required = sum(r['required_own_moves'] for r in partial_rows)
    return {'assigned': len(rows), 'original_attempts': n, 'eligible_original': n - unknown,
            'success': success, 'verified_wrong': wrong, 'unresolved': unresolved,
            'unfinished':unfinished,'skipped':skipped,'partial':partial,'pending':pending,
            'eligibility_unknown': unknown, 'eligibility_unknown_reasons':dict(eligibility_reasons), 'excluded': dict(exclusions),
            'completion_ratio': success / n if n else None,
            'logical_bounds': [success / n, (success + unresolved + pending) / n] if n else None,
            'confirmed_ratio': success / n if n and not unresolved and not pending and not unknown else None,
            'all_resolved': bool(n) and unresolved == 0 and pending == 0,
            'all_goals_completed':bool(n) and success==n,
            'independence_confirmed': bool(n) and unknown == 0,
            'bounds_kind': 'logical_completion_bounds_not_confidence',
            'external_difficulty': {'ratings': ratings, 'min': min(ratings) if ratings else None,
                                    'max': max(ratings) if ratings else None, 'bands': [list(b) for b in bands],
                                    'missing': n - len(ratings), 'calibrated_ability': False},
            'execution': {'confirmed_own_moves': confirmed, 'required_own_moves': required,
                          'fraction': confirmed / required if required else None, 'included_attempts': len(partial_rows),
                          'forced_submissions': sum(r['execution']['forced_submissions'] for r in original),
                          'choice_submissions': sum(r['execution']['choice_submissions'] for r in original),
                          'unreconstructed_submissions': sum(r['execution']['unreconstructed_submissions'] for r in original),
                          'is_ability_score': False}}


def summarize_attempts(reports, corrections=None, corpus=None):
    """Retain every assignment; unresolved attempts never vanish from denominator."""
    corrections = list(corrections or [])
    rows = []; timing_partitions = {}; seen_ids = set(); seen_positions = set(); policies = set(); scopes = set()
    for report in reports:
        if corpus is not None and report.get('corpus_sha256') != corpus: continue
        report_id = report.get('id', report.get('session_id'))
        scopes.add((report.get('version'), report.get('measurement_scope'), report.get('corpus_sha256'),report.get('competency_version'),report.get('score_version',report.get('scoring_version'))))
        for item in report.get('items', []):
            pid = item.get('puzzle_id'); positions = set()
            try: positions = line_positions(item['fen'], item['line'])
            except (KeyError, ValueError, TypeError): pass
            duplicate = bool(pid and pid in seen_ids or positions and seen_positions.intersection(positions))
            if pid: seen_ids.add(pid)
            seen_positions.update(positions)
            policy = item.get('answer_policy') or report.get('answer_policy') or LEGACY_POLICY
            helped=bool(item.get('helped') or item.get('revealed') or (isinstance(item.get('hint_level'),int) and item['hint_level']>0))
            classification = ('repeat' if duplicate or item.get('first_attempt') is False else 'help' if helped
                              else 'exposed' if item.get('app_new') is False else 'original')
            eligibility_reasons=[]
            if classification=='original':
                for condition,reason in [(item.get('app_new') is not True,'prior_exposure_unknown'),
                                         (item.get('first_attempt') is not True,'first_attempt_unknown'),
                                         (item.get('helped') is not False,'assistance_unknown'),
                                         (item.get('independent') is not True,'independence_not_established'),
                                         (not pid or not positions,'invalid_or_missing_source')]:
                    if condition:eligibility_reasons.append(reason)
            eligibility_unknown=bool(eligibility_reasons)
            original_outcome = item.get('outcome')
            corrected, resolution = _correction(item, report_id, corrections)
            outcome = corrected or original_outcome or 'unanswered'
            revalidatable = False; mismatch = None; revalidation_reason = 'not_an_unresolved_original_mismatch'
            if original_outcome in ('unverified_alternative', 'equivalent_alternative'):
                try:
                    mismatch = _mismatch(item)
                    revalidatable = (policy in (LEGACY_POLICY, 'goal-alternatives-v1')
                                     and 1 <= _mate_bound(item)-mismatch['response_index'] <= 3)
                    revalidation_reason = 'bounded_mate_revalidation_available' if revalidatable else 'unsupported_objective_or_policy'
                except (KeyError, ValueError, TypeError, AttributeError, IndexError) as exc:
                    revalidation_reason = str(exc) if isinstance(exc,ValueError) else 'missing_or_invalid_source'
            engine_reason = (item.get('engine_evidence') or {}).get('reason')
            unresolved_reason = ('technical_failure' if engine_reason in TECHNICAL else
                                 'analysis_limit' if engine_reason in ('insufficient_depth', 'mate_proof_budget') else outcome)
            rating = item.get('rating')
            rating = rating if isinstance(rating, (int, float)) and not isinstance(rating, bool) and math.isfinite(rating) else None
            band = item.get('band'); band = list(band) if isinstance(band, (list, tuple)) and len(band) == 2 and all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in band) and band[0]<band[1] else None
            timing=public_timing(item)
            if (item.get('solving_time') or {}).get('version')=='solving-time-v1':
                timing=copy.deepcopy(item['solving_time'])
                timing['availability']='observed' if type(timing.get('active_ms')) is int else 'unmeasured'
                timing['usable_for_trend']=False
            elapsed=timing.get('active_ms')
            elapsed=elapsed if timing.get('availability')=='observed' and type(elapsed) is int and elapsed>0 else None
            row = {'report_id': report_id, 'item_id': item.get('id'), 'puzzle_id': pid,
                   'item_fingerprint': item_fingerprint(item), 'competency': item.get('competency', 'unclassified'),
                   'classification': classification, 'eligibility_unknown': eligibility_unknown,
                   'eligibility_unknown_reasons':eligibility_reasons,'helped':helped,'repeated':duplicate or item.get('first_attempt') is False,
                   'original_outcome': original_outcome, 'effective_outcome': outcome, 'skipped':bool(item.get('skipped')),
                   'unresolved_reason': unresolved_reason if outcome not in WRONG | {'completed'} else None,
                   'source_policy': policy, 'corrected': corrected is not None,
                   'correction_policy': resolution.get('version') if resolution else None,
                   'revalidatable': revalidatable, 'revalidation_reason':revalidation_reason, 'mismatch': mismatch, 'rating': rating, 'band': band,
                   'execution': execution_observation(item), 'timing':timing,'elapsed_ms':elapsed}
            rows.append(row)
            if classification == 'original':
                policies.add(policy)
                if not eligibility_unknown and not corrected:
                    partition=(report.get('corpus_sha256'),report.get('version'),report.get('competency_version'))
                    timing_partitions.setdefault(partition,[]).append({**copy.deepcopy(item),
                        'answer_policy':policy,'measurement_scope':report.get('measurement_scope'),
                        'score_version':report.get('score_version',report.get('scoring_version'))})
    areas = {area: _aggregate([r for r in rows if r['competency'] == area]) for area in dict.fromkeys(r['competency'] for r in rows)}
    trends=timing_trend([])
    for (corpus_key,assessment_version,competency_version),members in timing_partitions.items():
        if not all((corpus_key,assessment_version,competency_version)):continue
        for group in timing_trend(members)['groups']:
            trends['groups'].append({**group,'corpus_sha256':corpus_key,'assessment_version':assessment_version,'competency_version':competency_version})
    trends['status']='available' if any(g['status']!='insufficient' for g in trends['groups']) else 'insufficient'
    return {'version': VERSION, 'timing_trends':trends, 'totals': _aggregate(rows), 'areas': areas, 'attempts': rows,
            'answer_policies': sorted(policies), 'mixed_policy': len(policies) > 1,
            'comparison_allowed': bool(scopes) and all(all(scope) for scope in scopes) and len(policies) <= 1 and len(scopes) <= 1 and not any(r['eligibility_unknown'] or r['corrected'] for r in rows),
            'preserves_original_score': True, 'new_skill_score': None,
            'note': '모든 원래 배정 시도의 수행 관찰입니다. 논리적 범위는 신뢰구간이 아니며 난이도 보정 능력이나 기존 1~3000점의 대체 산식이 아닙니다.'}
