"""Observed execution, explicit uncertainty and comparable assessment scopes."""
import copy
from datetime import datetime, timedelta, timezone
from competencies import COMPETENCIES, VERSION, position_key

JOURNEY_VERSION='journey-v3'
COVERAGE_POLICY='app-tracking-v1'
CUED='cued_execution'
UNCUED='uncued_execution'


def recheck_gate(learning, competency, current):
    cards=learning.get('cards',{});linked=[]
    for attempt in learning.get('attempts',[]):
        source=cards.get((attempt.get('selection') or {}).get('source_card'),{})
        if (source.get('diagnosis') and source.get('category')==competency
            and attempt.get('mode')=='verify' and attempt.get('fresh') and not attempt.get('helped')
            and attempt.get('assessment_scope')=='full_line'):
            linked.append(attempt)
    base={'competency':competency,'eligible':False,'ready_at':None,
          'practice_effect':'연결된 같은 과제를 다시 보면 그 마지막 노출부터 7일을 셉니다.',
          'while_waiting':'다른 영역의 새 문제나 자유 대국을 할 수 있습니다. 같은 과제 복습도 가능하지만 날짜가 늦춰집니다.'}
    if not linked:return {**base,'reason':'추천 5개 연습과 별개입니다. 진단에 연결된 미노출 전체 수순을 검증 모드에서 도움 없이 시도하면 7일 대기가 시작됩니다.'}
    sources={a['selection']['source_card'] for a in linked}
    related={cid for cid,card in cards.items() if cid in sources or (card.get('selection') or {}).get('source_card') in sources}
    def stamp(value):
        date=datetime.fromisoformat(value)
        return date if date.tzinfo else date.replace(tzinfo=timezone.utc)
    try:
        dates=[stamp(a['at']) for a in linked if a.get('at')]
        dates.extend(stamp(a['at']) for a in learning.get('attempts',[]) if a.get('card_id') in related and a.get('at'))
        for cid in related:
            for day,exposure in cards[cid].get('exposure',{}).items():
                dates.append(stamp(exposure['last_at']) if exposure.get('last_at') else stamp(day)+timedelta(days=1))
    except (ValueError,TypeError):
        return {**base,'reason':'과거 노출 시각을 해석하지 못해 재평가 날짜를 확인할 수 없습니다. 기존 기록은 유지됩니다.'}
    if not dates:return {**base,'reason':'노출 시각이 없어 재평가 날짜를 확인하지 못했습니다.'}
    ready=max(dates)+timedelta(days=7)
    return {**base,'eligible':current>=ready,'ready_at':ready.isoformat(),'last_exposure_at':max(dates).isoformat(),
            'reason':'새 국면으로 다시 확인할 수 있습니다.' if current>=ready else '연결된 훈련의 마지막 노출 후 7일을 기다립니다.'}


def additional_plan(reports, competency, measurement_scope):
    # No implicit legacy/cross-scope fallback: guidance and selection share this policy.
    compatible=(r for r in reversed(reports)
                if r.get('version')==JOURNEY_VERSION and r.get('competency_version')==VERSION
                and r.get('measurement_scope')==measurement_scope)
    area=next((a for r in compatible for a in r.get('areas',[])
               if a['id']==competency and a.get('count',0)>0),None)
    if not area:return {'band':[600,1200],'reason':'요청한 평가 조건·현재 버전에 맞는 관찰이 없어 기본 난도(600–1200)에서 시작합니다.'}
    completed=area.get('full_success',0)
    if completed>=2:return {'band':[1200,1800],'reason':'이번 수순 완주를 확인했습니다. 중간 난도의 다른 국면 3개로 적용 범위를 확인합니다.'}
    if completed:return {'band':[900,1500],'reason':'완주한 수순과 미완료 수순이 함께 있어 비슷한 부담의 다른 국면을 확인합니다.'}
    return {'band':[600,1200],'reason':'기초 범위의 다른 국면으로 수행을 더 관찰합니다. 표본 부족이나 미검증은 실력 부족 판정이 아닙니다.'}


def outcome(item):
    if item.get('outcome'):return item['outcome']
    if item.get('complete'):return 'completed'
    if item.get('skipped'):return 'partial_execution' if item.get('submitted') else 'not_answered'
    return 'legacy_unclassified' # Never reinterpret old nonmatching moves as verified errors.


def build_report(session, previous, current):
    items=session['items'];scope=session.get('measurement_scope','legacy_cued_execution')
    earlier=[i for r in previous if r['version']==session['version'] and r.get('measurement_scope')==scope for i in r['items']]
    accumulated=earlier+items;areas=[]
    for competency,spec in COMPETENCIES.items():
        rows=[i for i in items if i['competency']==competency]
        assessed=[i for i in rows if outcome(i) in ('completed','verified_non_mate')]
        tracked=[i for i in rows if i.get('app_new') and outcome(i) in ('completed','partial_execution','verified_non_mate')]
        known={position_key(i['fen']):i for i in accumulated if i['competency']==competency and i.get('app_new') and outcome(i) in ('completed','partial_execution','verified_non_mate')}
        evidence={'independent':sum(i.get('independent',False) for i in known.values()),'tracked':len(known),
                  'first_success':sum(i.get('first_correct',False) for i in known.values()),'full_success':sum(i.get('complete',False) for i in known.values()),
                  'version':session['version'],'measurement_scope':scope,'latest_at':max((i['completed_at'] for i in known.values()),default=None)}
        public_keys=('id','puzzle_id','fen','tags','submitted','expected','first_correct','complete','correct_plies','total_plies','reason','competency','rating','band','independent','shown_at','completed_at','helped','first_attempt','outcome','engine_evidence','app_new','prior_exposure_unknown')
        areas.append({'id':competency,'label':spec['label'],'count':len(rows),'evidence':evidence,
            'independent':sum(i.get('independent',False) for i in assessed),'app_new_attempts':len(tracked),
            'first_success':sum(i.get('first_correct',False) for i in rows),'full_success':sum(i.get('complete',False) for i in rows),
            'equivalent':sum(outcome(i)=='equivalent_alternative' for i in rows),
            'partial':sum(outcome(i)=='partial_execution' for i in rows),'unverified':sum(outcome(i)=='unverified_alternative' for i in rows),
            'unanswered':sum(outcome(i)=='not_answered' for i in rows),'verified_not_completed':sum(outcome(i)=='verified_non_mate' for i in rows),
            'assessed_denominator':len(assessed),'confidence':'관찰 범위를 더 넓혀 보세요.' if len(known)<5 else '앱 내 여러 국면에서 관찰했습니다. 실전·외부 실력과는 다릅니다.',
            'reason':spec['scope'],'items':[{k:copy.deepcopy(i[k]) for k in public_keys if k in i} for i in rows]})
    recommendations=[{'competency':i['competency'],'label':COMPETENCIES[i['competency']]['label'],'item_id':i['id'],'reason':i['reason'],'intent':'practice'} for i in items if outcome(i) in ('not_answered','partial_execution','verified_non_mate')]
    comparisons=[{'competency':i['competency'],'label':COMPETENCIES[i['competency']]['label'],'item_id':i['id'],'reason':'오답으로 판정하지 않았습니다. 내 수와 원본 수순을 비교하며 연습할 수 있습니다.','intent':'compare'} for i in items if outcome(i)=='unverified_alternative']
    completed=sum(i.get('complete',False) for i in items);unverified=sum(outcome(i)=='unverified_alternative' for i in items)
    return {'id':session['session_id'],'at':current.isoformat(),'version':session['version'],'competency_version':VERSION,
        'measurement_scope':scope,'coverage_policy':session.get('coverage_policy','legacy'), 'mode':session['mode'],
        'areas':areas,'items':copy.deepcopy(items),'recommendations':recommendations,'comparison_practice':comparisons,
        'summary':{'observed':f"{len(items)}문항에서 원본 또는 검증된 메이트 수순 {completed}개를 완주했습니다.",
            'uncertain':f"대안 {unverified}개는 판단을 보류했습니다. 적은 표본과 과거 노출 불명은 실력 부족을 뜻하지 않습니다.",
            'next': '완성하지 못한 수순 한 가지를 연습해 보세요.' if recommendations else '판단을 보류한 수를 비교해 보세요.' if comparisons else '다른 국면으로 적용 범위를 더 확인해 보세요.'},
        'limitations':['앱 안에서 새로 추적한 국면의 수행입니다. 앱 밖이나 구형 기록에 없는 노출 여부는 알 수 없습니다.',
            '상대 응수를 보면서 수순을 실행한 기록이며 머릿속 선계산이나 실전 탐지 능력을 직접 측정하지 않습니다.',
            '전략·장기 계획과 일반 종반 운영, 외부 Elo 및 교육 효과는 이 결과로 판단하지 않습니다.'],
        'comparison':'같은 버전·같은 안내 조건의 관찰만 묶습니다. 단서 제공 결과와 단서 비공개 결과를 비교 점수로 합치지 않습니다.'}
