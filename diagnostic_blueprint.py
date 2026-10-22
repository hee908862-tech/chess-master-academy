"""Selectable scope is not early exit. Blueprint v1 leaves old scores untouched."""
from competencies import COMPETENCIES
import threading
_catalog_lock=threading.Lock()
_cached_pool=None
_cached_result=None
VERSION = 'diagnostic-blueprint-v1'
TOPICS = {
 'mate': {'mateIn1':'한 수 메이트','mateIn2':'두 수 메이트','backRankMate':'백랭크 메이트'},
 'calculation': {'fork':'포크 수읽기','pin':'핀 수읽기','sacrifice':'희생 수읽기'},
 'capture': {'hangingPiece':'방치된 기물 포획','trappedPiece':'갇힌 기물','exchange':'교환'},
 'defense': {'defensiveMove':'방어 수 찾기'},
 'promotion': {'promotion':'승격','underPromotion':'언더프로모션'},
 'endgame': {'pawnEndgame':'폰 종반','rookEndgame':'룩 종반'},
}

def build_catalog(pools):
    areas=[]
    for key,spec in COMPETENCIES.items():
        pool=pools.get(key,[])
        topics=[]
        for tag,label in TOPICS.get(key,{}).items():
            counts=[sum(tag in p['tags'] and lo<=p['rating']<hi for p in pool) for lo,hi in [(600,1200),(1200,1800)]]
            topics.append({'id':tag,'label':label,'available':all(n>=2 for n in counts),'band_counts':counts})
        areas.append({'id':key,**spec,'topics':topics})
    return {'version':VERSION,'areas':areas,'levels':[
        {'id':'balanced','label':'종합 진단','questions':24,'bands':[12,12],'minutes':[30,60]},
        {'id':'domain','label':'분야별 진단','questions':8,'bands':[4,4],'minutes':[12,25]},
        {'id':'subskill','label':'분야별 부분 진단','questions':4,'bands':[2,2],'minutes':[6,15]}],
        'scoring':'내부 1–3000 수순 수행 지표. 기초 40%·응용 60%. 전체 수순 완료만 성공 근거이며 부분 수행은 따로 설명합니다. 힌트·미확정·미측정은 0점으로 바꾸지 않습니다.',
        'limits':'전략·계획과 일반 종반 전체는 측정 범위 밖입니다. 분야·주제 진단은 종합 점수를 만들지 않습니다. 예상 시간은 제한 시간이 아닙니다.'}


def catalog(pools):
    global _cached_pool, _cached_result
    with _catalog_lock:
        if _cached_pool is not pools:
            _cached_result=build_catalog(pools)
            _cached_pool=pools
        return _cached_result


def training_recommendations(report):
    """Only this scope's confirmed observations; uncertainty is not a deficit."""
    scope = report.get('diagnostic_scope') or {}
    allowed = set(TOPICS.get(scope.get('competency'), []))
    if scope.get('topic'): allowed &= {scope['topic']}
    observed = []
    for item in report.get('items', []):
        if item.get('competency') != scope.get('competency'): continue
        result = item.get('outcome')
        if result not in ('completed','verified_error','verified_non_mate','partial_execution'): continue
        if result == 'partial_execution' and not item.get('correct_plies', 0): continue
        topics = sorted(allowed.intersection(item.get('tags', [])))
        severity = 3 if result in ('verified_error','verified_non_mate') else 2 if result == 'partial_execution' else 1 if item.get('helped') else 0
        observed.append((item, topics, severity))
    weaknesses = sorted((row for row in observed if row[2]), key=lambda row: -row[2])
    source = weaknesses or observed
    tasks=[]; used=set()
    for item,topics,severity in source:
        for topic in topics:
            if topic in used: continue
            used.add(topic)
            reason = ('확정된 오답이 관찰되어 이 기술을 우선 연습합니다.' if severity == 3 else '수순 일부만 수행하여 이어지는 판단을 연습합니다.' if severity == 2 else '도움을 사용하여 도움 없는 수행을 연습합니다.' if severity == 1 else '관찰한 수순을 모두 성공하여 같은 기술의 새 문제로 수행을 유지합니다.')
            tasks.append({'item_id':item['id'],'topic':topic,'label':TOPICS[scope['competency']][topic],'intent':'weakness' if severity else 'maintenance','reason':reason})
            break
    insufficient = len(observed)<2
    if not weaknesses and insufficient: tasks=[]
    return {'tasks':tasks,'observed':len(observed),'needs_more':insufficient or len(observed)<len(report.get('items',[])),
            'message':'확정된 관찰이 부족합니다. 같은 범위의 추가 진단으로 확인하세요.' if not tasks else '관찰한 기술의 다른 문제를 우선 제공합니다. 후보가 없으면 원본 복습을 선택할 수 있습니다.'}
