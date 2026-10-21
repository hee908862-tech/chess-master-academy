"""Fixed-blueprint internal diagnosis, not calibrated population ability or Elo.

Weights are authored product assumptions. A line is one item. Missing outcomes
are bounds, not failures; repetitions and assisted work never add evidence.
"""
import math
from competencies import COMPETENCIES, line_positions

VERSION = 'skill-index-v1'
BANDS = ((600, 1200), (1200, 1800))
WEIGHTS = (.4, .6)


def scaled(value):
    return 1 + math.floor(2999 * max(0, min(1, value)) + .5)


def score_areas(items):
    seen_ids, seen_positions, valid = set(), set(), []
    for item in items:
        pid = item.get('puzzle_id')
        try:
            positions = line_positions(item['fen'], item['line'])
        except (KeyError, ValueError, TypeError):
            positions = set()
        fresh = bool(pid and positions and pid not in seen_ids and not seen_positions.intersection(positions))
        seen_ids.add(pid)
        seen_positions.update(positions)
        outcome = item.get('outcome')
        eligible = (fresh and item.get('app_new') and item.get('first_attempt') is True
                    and not item.get('helped') and outcome in ('completed', 'verified_error', 'verified_non_mate'))
        valid.append((item, (1 if outcome == 'completed' else 0) if eligible else None))
    result = {}
    for area in COMPETENCIES:
        groups = [[value for item, value in valid if item.get('competency') == area and tuple(item.get('band', [])) == band] for band in BANDS]
        counts = [sum(v is not None for v in group) for group in groups]
        assigned = [len(group) for group in groups]
        covered = all(assigned)
        complete = covered and counts == assigned
        low = sum(w * sum(v or 0 for v in group) / len(group) for w, group in zip(WEIGHTS, groups)) if covered else 0
        high = sum(w * sum(1 if v is None else v for v in group) / len(group) for w, group in zip(WEIGHTS, groups)) if covered else 1
        value = scaled(low) if complete else None
        # Conditional sample reference only; no claim of calibrated ability CI.
        margin = sum(w * min(1, math.sqrt(math.log(80) / (2*n))) for w, n in zip(WEIGHTS, counts)) if complete else None
        result[area] = {'score': value, 'observed': sum(counts), 'band_counts': counts,
            'assigned_counts': assigned, 'unresolved': sum(assigned)-sum(counts),
            'fraction': low if complete else None, 'fraction_bounds': [low, high],
            'scale_min': 1, 'scale_max': 3000, 'weights': list(WEIGHTS),
            'bounds': [scaled(low), scaled(high)] if covered else [1, 3000],
            'range': [scaled(low-margin), scaled(low+margin)] if complete else None,
            'comparable': complete and all(n >= 2 for n in counts),
            'confidence': '잠정 · 문항 수가 늘어도 교정된 실력 척도가 아닙니다.',
            'condition': '미노출·무도움 전체 수순 완주 · 기초 40% / 응용 60% (설계 가정)'}
    return result


def summary(areas):
    rows = [areas[c] for c, spec in COMPETENCIES.items() if spec['measured']]
    ready = all(r['score'] is not None for r in rows)
    value = scaled(sum(r['fraction'] for r in rows)/len(rows)) if ready else None
    return {'version': VERSION, 'score': value, 'scale_min': 1, 'scale_max': 3000,
            'observed': sum(r['observed'] for r in rows), 'unresolved': sum(r['unresolved'] for r in rows),
            'bounds': [scaled(sum(r['fraction_bounds'][i] for r in rows)/len(rows)) for i in (0,1)],
            'range': [math.floor(sum(r['range'][i] for r in rows)/len(rows)+.5) for i in (0,1)] if ready else None,
            'label': '내부 실력진단 지표 · 수순 수행 · 잠정',
            'note': '6분야 동일 비중, 기초 40%·응용 60%는 초기 설계 가정입니다. 전략·일반 종반·외부 Elo는 측정하지 않습니다. 1점 차이의 정밀도를 보장하지 않습니다.'}
