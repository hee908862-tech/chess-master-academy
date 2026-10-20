"""Original position-specific prompts. Existing courses remain immutable."""
import hashlib
import json
import chess
from study_server import courses, key, note

CORE = ['london-core','london-qb6','london-g6','london-early-c5','jobava-exchange','jobava-a6','jobava-c5']
# At each pre-move ply: placement, opponent aim, plan, exception; not engine rankings.
NOTES = {
'london-core': {
 4: ('f4 비숍이 아직 e폰 사슬 밖에 있습니다.', '흑은 d5와 f6 나이트로 중앙을 지킵니다.', 'e3로 d4를 지지하고 f1 비숍의 길을 준비합니다.', '비숍 전개를 생략하고 같은 폰 배치만 반복하는 방식은 아닙니다.'),
 8: ('흑 c5 폰이 d4 폰을 공격하고 있습니다.', '흑은 중앙 교환으로 백의 지지 구조를 시험합니다.', 'c3로 d4를 지지하고 b1 나이트는 d2를 고려합니다.', 'c3는 b1 나이트의 c3 칸도 차지합니다. 조바바의 Nc3와 구분하세요.'),
 12: ('d6 비숍과 f4 비숍 사이의 e5 칸이 비어 있습니다.', '흑은 활동적인 백 비숍의 교환을 제안합니다.', 'Bg3로 보존하거나 이 레슨에서 허용한 Bxd6 교환을 선택할 수 있습니다.', '교환은 비숍을 잃는 실수가 아닙니다. Qxd6 뒤 흑 퀸 전개도 함께 봅니다.'),
},
'london-qb6': {
 10: ('b6 퀸에서 b2까지 b5·b4·b3이 비어 있습니다.', '흑 퀸은 b2를, c5 폰은 d4를 공격합니다. 퀸의 d4 대각선은 자기 c5 폰에 막혀 있습니다.', 'Qb3는 b2를 지키며 퀸 교환 가능성을 제시합니다.', '모든 Qb6에 기계적으로 Qb3를 두지 말고 퀸의 실제 공격선을 확인하세요.'),
 12: ('흑 c4 폰이 b3 퀸을 공격합니다.', '흑은 중앙 긴장을 닫는 대신 퀸을 움직이게 합니다.', 'Qc2로 퀸을 피하고 다음 전개를 준비합니다.', 'c4 이후에는 c5 폰의 d4 공격이 사라집니다. 같은 위협 설명을 반복하지 않습니다.'),
},
'london-g6': {
 4: ('흑 g6 폰은 f5와 h5를 공격합니다.', '흑은 g7 비숍 전개와 중앙 반격을 준비합니다.', 'Nf3와 e3로 전개한 뒤 킹 안전을 확보합니다.', 'g6가 d3 칸 자체를 공격하는 것은 아닙니다. Bd3가 항상 나쁜 수도 아닙니다.'),
 8: ('흑 g7 비숍의 대각선은 현재 f6 나이트에 막혀 있습니다.', '흑은 나이트 이동과 중앙 폰 전진으로 비숍의 활동을 늘릴 수 있습니다.', 'Be2는 캐슬링을 준비하는 차분한 선택입니다.', '비숍이 이미 d4를 직접 공격한다고 설명하지 않습니다. 막는 기물을 먼저 봅니다.'),
},
'london-early-c5': {
 4: ('흑 c5 폰이 백 d4 폰을 공격합니다.', '흑은 백이 평소 구조를 그대로 만들기 전에 중앙을 흔듭니다.', '이 예시는 d5로 공간을 얻어 다른 폰 구조로 전환합니다.', '전형적인 c3-e3 런던 배치를 강요하지 않습니다. d5가 모든 위치의 유일한 최선은 아닙니다.'),
 8: ('백 d5 폰과 c3 나이트가 전진한 중앙을 지지합니다.', '흑은 g7 비숍 전개와 중앙의 교환을 준비합니다.', 'e4로 중앙 공간을 넓힌 뒤 기물 전개를 마칩니다.', '공간 확보만으로 우세를 확정할 수 없습니다. 폰이 공격받으면 지지 수를 다시 계산하세요.'),
},
'jobava-exchange': {
 4: ('c3 나이트는 e4를 공격하며 c2 폰 앞에 있습니다.', '흑은 d5와 f6 나이트로 e4 전진에 대응합니다.', 'Bf4와 e3 뒤 e4 준비 가능성을 살펴봅니다.', 'Nc3 때문에 지금 c2-c3·c2-c4는 불가능합니다. 런던 c3 폰 배치와 동시에 할 수 없습니다.'),
 8: ('d6와 f4 비숍이 빈 e5를 사이에 두고 서로 봅니다.', '흑은 백 비숍의 활동을 줄이려 합니다.', 'Bxd6 Qxd6는 비숍 교환 뒤 흑 퀸이 d6로 나오는 예시입니다.', '교환이 의무는 아닙니다. 이 레슨에 등록하지 않은 비숍 후퇴도 자동으로 나쁜 수가 아닙니다.'),
},
'jobava-a6': {
 6: ('흑 a6 폰이 b5를 공격합니다.', '흑은 백 나이트의 b5 진입을 견제합니다.', 'e3와 Nf3로 전개하고 중앙 계획을 준비합니다.', 'Nb5로 언제나 c7을 얻는다고 가정하지 않습니다. 상대 예방 수를 반영하세요.'),
 10: ('흑 d6 비숍이 f4 비숍과 교환할 수 있는 선에 있습니다.', '흑은 비숍 교환과 캐슬링을 준비합니다.', '이 예시는 Bd3로 킹사이드 전개를 이어갑니다.', 'f4 비숍을 즉시 지켜야 하는 강제 문제는 아닙니다. 교환 뒤 되잡는 방법도 확인하세요.'),
},
'jobava-c5': {
 6: ('흑 c5 폰이 d4 폰을 공격하고 백 c3에는 나이트가 있습니다.', '흑은 백의 고정 공격 준비보다 중앙을 먼저 시험합니다.', 'e3로 d4를 지지하며 f1 비숍의 길을 엽니다.', 'c3 폰으로 지지하는 런던 수순은 현재 나이트 때문에 사용할 수 없습니다.'),
 10: ('양쪽 나이트가 전개됐고 중앙에는 d4·d5·c5 폰 긴장이 남습니다.', '흑은 중앙 교환과 킹 안전을 함께 준비합니다.', 'Be2로 캐슬링을 준비한 뒤 중앙 교환 여부를 살핍니다.', '곧바로 킹 공격을 시작하는 고정 순서가 아니라 중앙 상황에 맞춘 예시입니다.'),
}}

def lesson(course_id):
    c=courses()[course_id]
    branches={'main':c['moves']}
    if course_id=='london-core':
        b=chess.Board();alternate=[]
        for san in 'd4 d5 Bf4 Nf6 e3 e6 Nf3 c5 c3 Nc6 Nbd2 Bd6 Bxd6 Qxd6 Bd3'.split():
            m=b.parse_san(san);alternate.append(m.uci());b.push(m)
        branches['bishop-exchange']=alternate
    version=hashlib.sha256(json.dumps([c['version'],branches,NOTES.get(course_id), 'repertoire-content-v1'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20]
    return {'id':course_id,'title':c['title'],'version':version,'branches':branches}

def explanation(course_id,moves):
    c=courses()[course_id];b=chess.Board()
    for u in moves:b.push_uci(u)
    index=len(moves);own=c['moves'][:index]==moves
    authored=NOTES.get(course_id,{}).get(index) if own else None
    result={'placement':' · '.join(('백' if color else '흑')+' 폰 '+', '.join(chess.square_name(s) for s in b.pieces(chess.PAWN,color)) for color in [True,False]),
            'opponent':'상대의 체크·포획 가능성과 중앙 폰의 공격 대상을 먼저 확인하세요.',
            'plan':c['ending'] if index==len(c['moves']) and own else '전개와 킹 안전을 준비하며 중앙 교환 뒤의 배치를 확인하세요.',
            'exception':'선택한 예시의 학습이며 유일한 최선이나 완전한 오프닝 이론 판정이 아닙니다.'}
    if authored:result.update(zip(['placement','opponent','plan','exception'],authored))
    if own and index<len(c['moves']):result['move_note']=note(c,index)
    result['attacks']=[{'from':chess.square_name(s),'targets':[chess.square_name(t) for t in b.attacks(s) if b.piece_at(t) and b.color_at(t)!=b.color_at(s)]} for s in b.piece_map() if any(b.piece_at(t) and b.color_at(t)!=b.color_at(s) for t in b.attacks(s))]
    result['in_check']=b.is_check()
    return result
