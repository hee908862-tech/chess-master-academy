"""Finite authored observation plan; no rating calibration or historical writes."""
import copy
from competencies import COMPETENCIES, VERSION as COMPETENCY_VERSION, line_positions
from skill_index import VERSION as SCORE_VERSION, BANDS, score_areas, summary

VERSION='initial-profile-v1'
PER_BAND=4
REPLACEMENTS=24
CHUNK=8


def compatible(report,corpus):
    return (report.get('version')=='journey-v5' and report.get('measurement_scope')=='broad_area_execution_v1'
            and report.get('score_version',report.get('scoring_version'))==SCORE_VERSION
            and report.get('competency_version')==COMPETENCY_VERSION and report.get('corpus_sha256')==corpus
            and report.get('mode') in ('balanced','quick','domain'))


def collect(state,corpus,include_active=True):
    reports=list(state.get('results',[]));active=state.get('active')
    if include_active and active:reports.append({**active,'id':active['session_id']})
    slots={c:[[],[]] for c,spec in COMPETENCIES.items() if spec['measured']}
    ids=set();positions=set();excluded={};sources=[]
    for report in reports:
        if not compatible(report,corpus):continue
        for item in report.get('items',[]):
            if not item.get('outcome'):continue
            area=item.get('competency');band=tuple(item.get('band',[]));pid=item.get('puzzle_id')
            try:footprint=line_positions(item['fen'],item['line'])
            except (KeyError,ValueError,TypeError):footprint=set()
            reason=None
            if area not in slots or band not in BANDS or not pid or not footprint:reason='invalid'
            elif pid in ids or positions.intersection(footprint):reason='repeat'
            elif not item.get('app_new') or item.get('first_attempt') is not True or item.get('helped'):reason='assisted_or_exposed'
            elif item.get('outcome') not in ('completed','verified_error','verified_non_mate'):reason=item.get('outcome','unresolved')
            ids.add(pid);positions.update(footprint)
            if reason:excluded[reason]=excluded.get(reason,0)+1;continue
            group=slots[area][BANDS.index(band)]
            if len(group)>=PER_BAND:continue
            row=copy.deepcopy(item);row['source_report']=report['id'];group.append(row);sources.append(row)
    return slots,sources,excluded


def status(state,corpus=None):
    course=state.get('initial_profile') or {}
    if course.get('baseline'):
        return {**copy.deepcopy(course['baseline']),'reviewed':bool(course.get('reviewed_at')),'active':bool(state.get('active'))}
    corpus=course.get('corpus') or corpus or next((r.get('corpus_sha256') for r in reversed(state.get('results',[])) if r.get('version')=='journey-v5'),None)
    slots,rows,excluded=collect(state,corpus)
    areas=[]
    for area,groups in slots.items():
        counts=list(map(len,groups));missing=[max(0,PER_BAND-n) for n in counts]
        areas.append({'id':area,'label':COMPETENCIES[area]['label'],'counts':counts,'missing_bands':missing,'missing':sum(missing),'ready':not any(missing)})
    remaining=sum(a['missing'] for a in areas);assigned=course.get('assigned',0)
    maximum=course.get('maximum',remaining+REPLACEMENTS)
    state_name='ready' if remaining==0 else 'held' if course.get('held') or (assigned>=maximum and not state.get('active')) else 'in_progress' if course else 'not_started'
    # Missing blueprint slots remain unknown, never disappear from the denominator.
    scoring_rows=list(rows)
    for area in areas:
        for band,missing in zip(BANDS,area['missing_bands']):
            scoring_rows.extend({'competency':area['id'],'band':list(band),'outcome':'unobserved'} for _ in range(missing))
    scores=score_areas(scoring_rows)
    allocated=course.get('assigned_by_area',{})
    initial_missing=course.get('initial_missing_by_area',{})
    pending=sorted(areas,key=lambda a:(allocated.get(a['id'],0)>=initial_missing.get(a['id'],a['missing']),allocated.get(a['id'],0),-a['missing']))
    return {'version':VERSION,'score_version':SCORE_VERSION,'corpus':corpus,'state':state_name,'reviewed':False,
            'active':bool(state.get('active')),'valid':48-remaining,'required':48,'remaining':remaining,'areas':areas,
            'next_area':next((a['id'] for a in pending if a['missing']),None),
            'assigned':assigned,'maximum':maximum,'replacement_limit':REPLACEMENTS,'budget_left':max(0,maximum-assigned),
            'held_reason':course.get('held') or ('정해진 추가 확인 상한에 도달했습니다.' if state_name=='held' else None),
            'excluded':excluded,'performance':scores,'internal_skill':summary(scores),
            'sources':[{'report_id':r['source_report'],'item_id':r['id'],'competency':r['competency'],'band':r['band'],'rating':r.get('rating'),'outcome':r['outcome'],'fen':r['fen'],'line':r['line'],'submitted':r.get('submitted',[])} for r in rows],
            'scope':'전술·수순 실행 6분야 · 오프닝 이해, 전략·계획, 일반 종반 전체는 미측정',
            'note':'48문항은 설계한 관찰 범위입니다. 정답 개수가 아니라 분야·난도별 유효 관찰로 완료하며 정확도·완전 숙련을 보장하지 않습니다.',
            'replacement_note':'건너뛰기·도움·기출·부분 수행·엔진 미확정은 유효 관찰에서 제외합니다. 대체는 총 24문항까지이며 부족하면 판단 보류로 마칩니다.'}


def initialize(state,corpus):
    if state.get('initial_profile'):return
    preview=status(state,corpus)
    state['initial_profile']={'version':VERSION,'corpus':corpus,'assigned':0,'maximum':preview['remaining']+REPLACEMENTS,
                              'assigned_by_area':{},'initial_missing_by_area':{a['id']:a['missing'] for a in preview['areas']}}


def freeze(state,at,held_reason=None):
    course=state['initial_profile']
    if course.get('baseline'):return
    if held_reason:course['held']=held_reason
    view=status(state)
    if view['state'] not in ('ready','held'):raise ValueError('관찰이 진행 중입니다.')
    course['baseline']=copy.deepcopy(view);course['baseline']['baseline_version']='initial-baseline-v1'
    course['baseline']['frozen_at']=at
