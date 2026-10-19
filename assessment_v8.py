"""Version 8 formative assessment. Uses python-chess validated tasks.
49 distinct positions across 7 specific domains. The score is a local educational index,
NOT FIDE/Chess.com/Lichess Elo. Moves are legality-checked; the educational ranking is not calibrated.
"""
import random, math
from functools import lru_cache
import chess
from exercises import bank
from assessment_v3 import _opening, _endgame

# V9: replace the old simple pawn-push / arbitrary-knight-development questions.
# Only curated Lichess positions with validated moves can be used for diagnosis.
from v9_server import LIB, BY_THEME
DOMAINS=[
 ('mate','체크메이트 계산','mate'),
 ('defense','위협 감지와 방어','defense'),
 ('calculation','다수 수순 계산','calculation'),
 ('capture','기물 손익과 전환','capture'),
 ('tactics','전술적 기회','tactics'),
 ('strategy','조용한 수와 전략','strategy'),
 ('endgame','실전 엔드게임·역전','endgame'),
]
DOMAIN_TAGS={
 'mate':['mateIn1','mateIn2','mateIn3','mateIn4','mateIn5'],
 'defense':['defensiveMove','equality','exposedKing'],
 'calculation':['fork','discoveredAttack','intermezzo','clearance'],
 'capture':['hangingPiece','trappedPiece','capturingDefender'],
 'tactics':['pin','skewer','deflection','overloading'],
 'strategy':['quietMove','advantage','interference','sacrifice'],
 'endgame':['endgame','zugzwang','promotion','underPromotion']}
# Ratings increase with each band; unlike the legacy version, item number does not define difficulty.
RATING_BANDS=[(600,950),(950,1200),(1200,1450),(1450,1700),(1700,1950),(1950,2250),(2250,2900)]
@lru_cache(maxsize=128)
def questions(seed):
    if not LIB:raise RuntimeError('검증된 체스 평가 데이터가 없습니다. Lichess 문제 데이터를 가져온 뒤 진단을 시작하세요.')
    rng=random.Random(seed);used=set();out=[]
    for i,(lo,hi) in enumerate(RATING_BANDS):
        for code,label,_ in DOMAINS:
            possible=set()
            for tag in DOMAIN_TAGS[code]:possible.update(BY_THEME.get(tag,[]))
            possible=[LIB[k] for k in possible if k not in used and lo<=LIB[k]['rating']<hi]
            if not possible:raise RuntimeError(f'평가 문제 데이터 부족: {label}, 레이팅 {lo}~{hi}. Lichess CSV를 추가로 선별하세요.')
            p=rng.choice(possible);used.add(p['id'])
            board=chess.Board(p['fen']);board.push_uci(p['moves'][0]);answer=p['moves'][1]
            if chess.Move.from_uci(answer) not in board.legal_moves:raise RuntimeError('평가 정답 수 검증 실패')
            out.append({'id':len(out),'domain':code,'domain_name':label,'difficulty':i+1,
                        'fen':board.fen(), 'description':f"{label}: 상대의 직전 수에서 발생한 기회를 계산하세요. (문제 레이팅 {p['rating']})",
                        'answers':[answer],'puzzle_id':p['id'],'rating':p['rating']})
    return out

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
