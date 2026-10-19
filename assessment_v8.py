"""Version 8 formative assessment. Uses python-chess validated tasks.
49 distinct positions across 7 specific domains. The score is a local educational index,
NOT FIDE/Chess.com/Lichess Elo. Moves are legality-checked; the educational ranking is not calibrated.
"""
import random, math
from functools import lru_cache
import chess
from exercises import bank
from assessment_v3 import _opening, _endgame

DOMAINS=[
 ('mate','체크메이트 패턴','mate'),
 ('king','킹 안전과 기물 보존','capture'),
 ('calculation','전술 계산','capture'),
 ('capture','기물 손익','capture'),
 ('tactics','기물 포획 전술','capture'),
 ('opening','오프닝 전개','opening'),
 ('endgame','킹·폰 엔드게임','endgame'),
]

DIFFICULTY_FACTORS=(0.85,0.9,0.95,1.0,1.05,1.10,1.15)

@lru_cache(maxsize=128)
def questions(seed):
    rng=random.Random(seed)
    pool=bank()
    mates=list({x['fen']:x for x in pool if x['kind']=='mate'}.values())
    captures=list({x['fen']:x for x in pool if x['kind']=='capture'}.values())
    rng.shuffle(mates);rng.shuffle(captures)
    if len(mates)<7 or len(captures)<28:
        raise RuntimeError(f'검증된 평가 문항 부족: 체크메이트 {len(mates)}, 기물 {len(captures)}')
    pools={'mate':mates,'capture':captures}
    used=set();out=[]
    for code,label,kind in DOMAINS:
        for i in range(7):
            if kind in pools:
                p=next((p for p in pools[kind] if p['fen'] not in used),None)
            else:
                p=None
                for _ in range(200):
                    q=_opening(rng) if kind=='opening' else _endgame(rng)
                    if q is not None and q['fen'] not in used:
                        p=q;break
            if p is None:raise RuntimeError('평가 문항 생성 실패: '+label)
            fen=p['fen'];used.add(fen)
            board=chess.Board(fen)
            if not board.is_valid():raise RuntimeError('유효하지 않은 평가 포지션')
            answers=[u for u in p['answers'] if chess.Move.from_uci(u) in board.legal_moves]
            if not answers:raise RuntimeError('합법 정답 없음')
            out.append({'id':len(out),'domain':code,'domain_name':label,'difficulty':i+1,
                        'fen':fen,'description':p['description'],'answers':answers})
    assert len(out)==49 and len(used)==49
    # Rotate domains within each difficulty band rather than showing long runs of one pattern.
    # Levels are instructional bands, NOT empirically normed chess ratings.
    rotated=[out[j*7+i] for i in range(7) for j in range(7)]
    for i,q in enumerate(rotated):q['id']=i
    return rotated

def public_question(q):
    b=chess.Board(q['fen'])
    return {k:q[k] for k in ('id','domain','domain_name','difficulty','fen','description')} | {
        'legal':[m.uci() for m in b.legal_moves]}

def points(correct,seconds,difficulty):
    if not correct:return 0.0
    # Time impacts at most 8%; only correct answers can earn points.
    # An intentional slow-but-correct solution is far better than a fast guess.
    target=70+15*difficulty
    return round(100*(0.92+0.08*min(1,target/max(.1,seconds))),2)

def finalize(question_log,game_losses,engine_supported,completed_games,previous=None):
    domain_scores={}
    for code,label,_ in DOMAINS:
        items=[a for a in question_log if a['domain']==code]
        domain_scores[code]={'label':label,'correct':sum(int(a['correct']) for a in items),
                             'total':len(items),
                             'score':round(sum(a['points']*(0.75+0.07*a['difficulty']) for a in items)/max(1,sum(0.75+0.07*a['difficulty'] for a in items)),1),
                             'median_seconds':round(sorted(a['seconds'] for a in items)[len(items)//2],1) if items else None}
    quizscore=round(sum(x['score'] for x in domain_scores.values())/7,1)
    game_score=None
    if engine_supported and game_losses:
        # Internal accuracy proxy from centipawn loss, not Chess.com's formula.
        # Errors >300 cp heavily penalized; wins/losses alone don't determine score.
        game_score=round(sum(100*math.exp(-max(0,loss)/180) for loss in game_losses)/len(game_losses),1)
    if game_score is None:
        overall=round(quizscore,1)
        status='문제 기반 예비 평가 · 엔진 정확도 미포함'
    else:
        overall=round(quizscore*.7+game_score*.3,1)
        status='49문항 70% + 엔진 기반 실전 정확도 30%'
    index=round(overall*10) # Internal 0-1000 only, NOT Elo
    grade=('입문자' if index<300 else '초급자' if index<550 else '중급자' if index<750 else '숙련자')
    sorted_domains=sorted(domain_scores.items(),key=lambda x:x[1]['score'])
    weaknesses=[v['label'] for _,v in sorted_domains[:3]]
    strengths=[v['label'] for _,v in sorted_domains[-3:][::-1]]
    prev_index=previous.get('index') if isinstance(previous,dict) else None
    delta=index-prev_index if isinstance(prev_index,(int,float)) else None
    return {'index':index,'stage':grade,'delta':delta,'previous_index':prev_index,
            'overall':overall,'quiz_score':quizscore,'game_score':game_score,
            'domains':domain_scores,'strengths':strengths,'weaknesses':weaknesses,
            'completed_game_plies':completed_games,'formula':status,'official_elo':False,
            'confidence':'문제은행에 난이도 표준화가 부족한 실험적 내부 지수입니다. 공식 레이팅이 아니며 동일 영역 반복 유형의 영향이 있습니다.'}
