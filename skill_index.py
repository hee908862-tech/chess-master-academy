"""Fixed-blueprint internal diagnosis, not calibrated population ability or Elo.

Weights are authored product assumptions. A line is one item. Missing outcomes
are bounds, not failures; repetitions and assisted work never add evidence.
"""
import math
from competencies import COMPETENCIES, VERSION as COMPETENCY_VERSION, line_positions

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

# Authored readiness rule, not statistical calibration. Bump the policy on change.
EVIDENCE_POLICY = {'version':'profile-evidence-v1','per_band':4,'per_area':8,'total':48}


def cumulative_evidence(reports, policy=None):
    policy=dict(policy or EVIDENCE_POLICY)
    measured={k:v for k,v in COMPETENCIES.items() if v['measured']}
    compatible=[r for r in reports if r.get('score_version')==VERSION
                and r.get('version')=='journey-v5' and r.get('measurement_scope')=='broad_area_execution_v1'
                and r.get('competency_version')==COMPETENCY_VERSION and r.get('corpus_sha256')
                and r.get('mode') in ('balanced','quick','domain')]
    latest=compatible[-1] if compatible else {}
    def group(r):return (r.get('version'),r.get('competency_version'),r.get('measurement_scope'),r.get('corpus_sha256'))
    compatible=[r for r in compatible if group(r)==group(latest)]
    counts={key:[0,0] for key in measured};seen_ids=set();seen_positions=set();excluded={}
    for report in compatible:
        for item in report.get('items',[]):
            reason=None
            try:positions=line_positions(item['fen'],item['line'])
            except (ValueError,KeyError,TypeError):positions=set()
            pid=item.get('puzzle_id');area=item.get('competency');band=tuple(item.get('band',[]))
            if not pid or not positions or area not in counts or band not in BANDS:reason='invalid_or_out_of_scope'
            elif pid in seen_ids or seen_positions.intersection(positions):reason='duplicate_position_or_line'
            elif not item.get('app_new') or item.get('first_attempt') is not True or item.get('helped'):reason='exposed_or_assisted'
            elif item.get('outcome') not in ('completed','verified_error','verified_non_mate'):reason='unresolved_or_incomplete'
            # Exposure even on skipped/failed/assisted items prevents later credit.
            seen_ids.add(pid);seen_positions.update(positions)
            if reason:excluded[reason]=excluded.get(reason,0)+1
            else:counts[area][BANDS.index(band)]+=1
    areas=[]
    for key,spec in measured.items():
        bands=counts[key];deficit=max(sum(max(0,policy['per_band']-n) for n in bands),policy['per_area']-sum(bands),0)
        areas.append({'id':key,'label':spec['label'],'band_counts':bands,'valid':sum(bands),'missing':deficit,'ready':deficit==0})
    total=sum(a['valid'] for a in areas);missing=max(sum(a['missing'] for a in areas),policy['total']-total,0)
    ready=all(a['ready'] for a in areas) and total>=policy['total']
    next_area=next((a for a in sorted(areas,key=lambda a:-a['missing']) if a['missing']),min(areas,key=lambda a:a['valid']) if missing else None)
    return {'policy':policy,'ready':ready,'valid':total,'missing':missing,'areas':areas,
            'areas_observed':sum(a['valid']>0 for a in areas),'areas_ready':sum(a['ready'] for a in areas),
            'excluded':excluded,'compatible_sessions':len(compatible),'other_sessions':len(reports)-len(compatible),
            'next_area':next_area['id'] if next_area else None,
            'minimum_comprehensive_sessions':math.ceil(missing/24) if missing else 0,
            'note':f"앱에서 평가하는 {len(areas)}분야의 근거 조건입니다. 분야별 기초·응용 각 {policy['per_band']}개, 분야별 {policy['per_area']}개, 전체 {policy['total']}개는 설계 가정이며 정확도를 보장하지 않습니다. 전략·일반 종반은 미측정입니다.",
            'limit':'중단 세션은 완료 전 제외. 반복·힌트·정답 확인·건너뛰기·부분 수행·엔진 미확정은 유효 근거에서 제외합니다. 앱 밖 과거 노출은 알 수 없습니다. 남은 회차는 유효 응답과 미노출 문제 확보에 따라 늘며 문제 부족 시 완료를 약속하지 않습니다. 기존 회차 점수는 다시 계산하지 않습니다.'}
