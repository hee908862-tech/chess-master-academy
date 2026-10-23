"""Finite authored observation plan; no rating calibration or historical writes."""
import copy
import hashlib
import json
from competencies import COMPETENCIES, VERSION as COMPETENCY_VERSION, line_positions
from skill_index import VERSION as SCORE_VERSION, BANDS, score_areas, summary

VERSION='initial-profile-v1'
PER_BAND=4
REPLACEMENTS=24
CHUNK=8
TECHNICAL_REPLACEMENTS=8
SUPPLEMENT_LIMIT=8
TECHNICAL_REASONS={'engine_unavailable','diagnosis_busy','busy','engine_busy','engine_failure'}


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
            elif item.get('helped'):reason='assisted'
            elif not item.get('app_new'):reason='previous_exposure'
            elif item.get('first_attempt') is not True:reason='repeat_attempt'
            elif item.get('outcome') not in ('completed','verified_error','verified_non_mate'):
                reason=item.get('outcome','unresolved')
                if reason=='unverified_alternative':
                    engine_reason=(item.get('engine_evidence') or {}).get('reason')
                    if engine_reason in TECHNICAL_REASONS:reason='technical_failure'
                    elif engine_reason in ('insufficient_depth','mate_proof_budget'):reason='analysis_limit'
            ids.add(pid);positions.update(footprint)
            if reason:excluded[reason]=excluded.get(reason,0)+1;continue
            group=slots[area][BANDS.index(band)]
            if len(group)>=PER_BAND:continue
            row=copy.deepcopy(item);row['source_report']=report['id'];row['answer_policy']=report.get('answer_policy','reference-line-v1');group.append(row);sources.append(row)
    return slots,sources,excluded


def technical_failures(state):
    """Only known execution failures, not search uncertainty or a wrong answer."""
    reports=list(state.get('results',[]))
    if state.get('active'):reports.append(state['active'])
    seen=set()
    for report in reports:
        if not report.get('initial_course'):continue
        if state.get('initial_profile',{}).get('corpus') and report.get('corpus_sha256')!=state['initial_profile']['corpus']:continue
        for item in report.get('items',[]):
            if item.get('outcome')=='unverified_alternative' and (item.get('engine_evidence') or {}).get('reason') in TECHNICAL_REASONS:
                seen.add(item.get('id'))
    return len(seen-{None})


def supplement_metadata(course, view):
    revisions=[]
    for record in course.get('history',[]):
        prior=record.get('baseline_view') or record.get('baseline') or {}
        revisions.append({'at':record.get('at'),'baseline_id':prior.get('baseline_id'),'valid':prior.get('valid'),
                          'remaining':prior.get('remaining'),'state':prior.get('state'),'score_version':prior.get('score_version'),
                          'score':(prior.get('internal_skill') or {}).get('score'),'reviewed_at':record.get('reviewed_at')})
    return {'previous_baselines':revisions,'supplement_available_to_check':view.get('state')=='held' and view.get('remaining',0)>0 and not course.get('supplement_used'),
            'supplement_limit':SUPPLEMENT_LIMIT,'supplement_used':bool(course.get('supplement_used')),
            'supplement_allocated':course.get('supplement_allocated',0),
            'previous_baseline_count':len(course.get('history',[]))}


def status(state,corpus=None):
    course=state.get('initial_profile') or {}
    if course.get('baseline'):
        baseline=copy.deepcopy(course['baseline'])
        identity=[baseline.get('baseline_version'),baseline.get('corpus'),baseline.get('frozen_at'),
                  [(s['report_id'],s['item_id']) for s in baseline.get('sources',[])]]
        baseline['baseline_id']=hashlib.sha256(json.dumps(identity,separators=(',',':')).encode()).hexdigest()
        sources=baseline.get('sources',[])
        source=next((s for s in sources if s['outcome']!='completed'),sources[0] if sources else None)
        baseline['recommended_source']={k:source[k] for k in ('report_id','item_id')} if source else None
        return {**baseline,**supplement_metadata(course,baseline),'reviewed':bool(course.get('reviewed_at')),'active':bool(state.get('active'))}
    corpus=course.get('corpus') or corpus or next((r.get('corpus_sha256') for r in reversed(state.get('results',[])) if r.get('version')=='journey-v5'),None)
    slots,rows,excluded=collect(state,corpus)
    areas=[]
    for area,groups in slots.items():
        counts=list(map(len,groups));missing=[max(0,PER_BAND-n) for n in counts]
        areas.append({'id':area,'label':COMPETENCIES[area]['label'],'counts':counts,'missing_bands':missing,'missing':sum(missing),'ready':not any(missing)})
    remaining=sum(a['missing'] for a in areas);assigned=course.get('assigned',0)
    technical=technical_failures(state)
    credit=min(technical,TECHNICAL_REPLACEMENTS) if course.get('budget_policy')=='separate-technical-v1' else 0
    maximum=course.get('maximum',remaining+REPLACEMENTS)+credit
    if course.get('supplement_cap') is not None:maximum=min(maximum,course['supplement_cap'])
    state_name='ready' if remaining==0 and not state.get('active') else 'held' if course.get('held') or (assigned>=maximum and not state.get('active')) else 'in_progress' if course else 'not_started'
    # Missing blueprint slots remain unknown, never disappear from the denominator.
    scoring_rows=list(rows)
    for area in areas:
        for band,missing in zip(BANDS,area['missing_bands']):
            scoring_rows.extend({'competency':area['id'],'band':list(band),'outcome':'unobserved'} for _ in range(missing))
    scores=score_areas(scoring_rows)
    mixed_policy=len({r.get('answer_policy','reference-line-v1') for r in rows})>1
    if mixed_policy:
        for score in scores.values():
            score['comparable']=False
            score['comparison_reason']='대체 수 검증 정책이 섞여 같은 조건의 성장 비교를 제공하지 않습니다.'
    allocated=course.get('assigned_by_area',{})
    initial_missing=course.get('initial_missing_by_area',{})
    pending=sorted(areas,key=lambda a:(allocated.get(a['id'],0)>=initial_missing.get(a['id'],a['missing']),allocated.get(a['id'],0),-a['missing']))
    return {'version':VERSION,'score_version':SCORE_VERSION,'corpus':corpus,'state':state_name,'reviewed':False,
            'active':bool(state.get('active')),'valid':48-remaining,'required':48,'remaining':remaining,'areas':areas,
            'next_area':next((a['id'] for a in pending if a['missing']),None),
            'assigned':assigned,'maximum':maximum,'replacement_limit':REPLACEMENTS,'budget_left':max(0,maximum-assigned),
            'held_reason':course.get('held') or ('정해진 추가 확인 상한에 도달했습니다.' if state_name=='held' else None),
            'technical_failures':technical,'technical_replacement_credit':credit,'technical_replacement_limit':TECHNICAL_REPLACEMENTS,
            **supplement_metadata(course,{'state':state_name,'remaining':remaining}),
            'answer_policies':sorted({r.get('answer_policy','reference-line-v1') for r in rows}),
            'answer_policy_note':'저장 수순 기준과 목표별 대체 수 검증 정책은 구분합니다. 이전 점수를 소급 재채점하지 않습니다.',
            'excluded':excluded,'performance':scores,'internal_skill':summary(scores),
            'mixed_answer_policy':len({r.get('answer_policy','reference-line-v1') for r in rows})>1,
            'comparison_allowed':len({r.get('answer_policy','reference-line-v1') for r in rows})<=1,
            'sources':[{'answer_policy':r.get('answer_policy','reference-line-v1'),'report_id':r['source_report'],'item_id':r['id'],'competency':r['competency'],'band':r['band'],'rating':r.get('rating'),'outcome':r['outcome'],'fen':r['fen'],'line':r['line'],'submitted':r.get('submitted',[])} for r in rows],
            'scope':'전술·수순 실행 6분야 · 오프닝 이해, 전략·계획, 일반 종반 전체는 미측정',
            'note':'48문항은 설계한 관찰 범위입니다. 정답 개수가 아니라 분야·난도별 유효 관찰로 완료하며 정확도·완전 숙련을 보장하지 않습니다.',
            'replacement_note':'건너뛰기·도움·기출·부분 수행·분석 미확정은 유효 관찰에서 제외합니다. 대체는 24문항까지입니다. 새 과정의 기술 실패는 별도 최대 8문항을 보충하며, 탐색 깊이 부족은 기술 실패와 구분합니다. 이 상한은 운영 설계이며 정확도 보장이 아닙니다.'}


def initialize(state,corpus):
    if state.get('initial_profile'):return
    preview=status(state,corpus)
    state['initial_profile']={'version':VERSION,'budget_policy':'separate-technical-v1','corpus':corpus,'assigned':0,'maximum':preview['remaining']+REPLACEMENTS,
                              'assigned_by_area':{},'initial_missing_by_area':{a['id']:a['missing'] for a in preview['areas']}}


def freeze(state,at,held_reason=None):
    course=state['initial_profile']
    if course.get('baseline'):return
    if held_reason:course['held']=held_reason
    view=status(state)
    if view['state'] not in ('ready','held'):raise ValueError('관찰이 진행 중입니다.')
    course['baseline']=copy.deepcopy(view);course['baseline']['baseline_version']='initial-baseline-v1'
    course['baseline']['frozen_at']=at
