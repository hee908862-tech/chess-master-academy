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
