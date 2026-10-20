"""Original mini lessons: legal-board facts, not an engine ranking or a mastery test."""
import hashlib
import json
import chess

def position(pieces,turn=True):
    b=chess.Board(None);b.turn=turn
    for token in pieces.split():b.set_piece_at(chess.parse_square(token[2:]),chess.Piece.from_symbol(token[1] if token[0]=='w' else token[1].lower()))
    assert b.is_valid(),b.fen()
    return b.fen()
def played(fen,*moves):
    b=chess.Board(fen)
    for u in moves:b.push_uci(u)
    return b.fen()
def step(id,title,fen,kind,prompt,answers,reason,**extra):
    return dict(id=id,title=title,fen=fen,kind=kind,prompt=prompt,answers=answers,reason=reason,**extra)

def lesson(id,group,title,intro,prerequisite,steps):
    return dict(id=id,group=group,title=title,intro=intro,prerequisite=prerequisite,steps=steps)

PRE=position('wKg1 wNc3 bKg8 bBf8',False)
LOOSE=played(PRE,'f8b4')
DEFENDED=position('wKg1 wNc3 wPa2 wPb2 bKg8 bBb4')
CAPTURED=played(DEFENDED,'a2a3','b4c3')
FILE=position('wKg1 wRa1 wPa2 wPb2 wPf2 wPg2 wPh2 bKg8 bPa7 bPb7 bPf7 bPg7 bPh7')
BISHOP=position('wKg1 wBc1 wPb2 wPd2 bKg8 bPh7')
OPPOSITION=position('wKe4 wPh2 bKe6 bPh7')
OPPOSITION_B=position('wKe4 wPh2 bKe6 bPh7',False)
PROMOTE=position('wKc1 wPg7 bKa1')
QUEEN=played(PROMOTE,'g7g8q')
ROOK=played(PROMOTE,'g7g8r')
LESSONS=[
lesson('threat-observe','threat','공격선 관찰과 피하기',
 '상대 직전 수에서 달라진 공격선을 확인합니다. 공격받는다는 사실만으로 다음 수에 반드시 잃는다고 단정하지 않습니다.', 'king-check',[
 step('target','상대 직전 수의 변화',LOOSE,'square','흑이 비숍을 f8에서 b4로 옮겼습니다. 이제 이 비숍이 공격하는 백 기물의 칸을 선택하세요.',['c3'],'b4 비숍의 대각선에 c3 나이트가 있습니다. 킹은 체크가 아닙니다. 공격받음은 확인했지만 강제 손실은 아직 입증하지 않았습니다.',prior_fen=PRE,prior_move='f8b4'),
 step('retreat','두 가지 합법적인 피하기',LOOSE,'move','나이트를 비숍의 현재 공격선 밖으로 옮겨 보세요. 이 수업에서는 a2 또는 e4로 피하는 계획을 비교합니다.',['c3a2','c3e4'],'선택한 칸은 b4 비숍의 공격선 밖입니다. 두 수 모두 이번 관찰 목표를 충족합니다. 모든 합법 수의 우열을 비교한 것은 아닙니다.'),
 step('meaning','확인한 사실의 범위',LOOSE,'choice','이 위치를 본 뒤 어떤 설명까지 할 수 있나요?',['attack-only'],'현재 공격선은 규칙으로 확인할 수 있습니다. 강제 손실을 주장하려면 대응과 후속 수순을 더 검증해야 합니다.',choices=[['attack-only','나이트가 공격받지만 강제 손실인지는 더 확인해야 한다'],['forced-loss','공격자가 있으므로 반드시 나이트를 잃는다']])]),
lesson('threat-defended','threat','방어된 기물과 되잡기 비교',
 '공격자 수를 세는 대신 실제로 잡고 되잡는 합법 수순을 확인합니다. 교환 가능성만으로 전체 위치의 유불리는 판정하지 않습니다.', 'value-protection',[
 step('defender','누가 c3를 지키나요?',DEFENDED,'square','b4 비숍이 c3 나이트를 공격합니다. c3를 지키는 백 폰의 칸을 선택하세요.',['b2'],'b2 폰은 대각선 c3를 공격합니다. 나이트가 잡혀도 되잡는 수가 가능한지 확인할 근거가 있습니다.'),
 step('challenge','상대의 예시 응수 관찰',DEFENDED,'move','a폰을 한 칸 전진해 비숍을 공격하는 계획을 봅니다. a3를 두면 흑의 예시 응수 ...Bxc3를 표시합니다.',['a2a3'],'a3 뒤 ...Bxc3는 합법적인 예시 응수입니다. 흑에게 이 응수가 강제라는 뜻은 아닙니다. 다음 비교 위치에서 되잡기를 확인하세요.',reply='b4c3'),
 step('recapture','다음 비교 위치: 되잡기',CAPTURED,'move','방금 예시 수순의 결과입니다. c3의 흑 비숍을 b폰으로 되잡아 보세요.',['b2c3'],'bxc3가 합법적이며 흑 비숍이 잡힙니다. 공격받던 나이트가 무조건 공짜로 사라지는 상황은 아닙니다. 교환 후 폰 배치가 바뀌며 전체 평가까지 증명한 수업은 아닙니다.')]),
lesson('plan-file','plan','열린 파일과 룩의 활동',
 '폰이 없는 파일이라는 객관적 사실과 그 파일을 쓰려는 계획 후보를 구분합니다. 파일을 차지했다고 침투나 승리가 보장되지는 않습니다.', 'rook-bishop',[
 step('file','폰 배치 관찰',FILE,'choice','a파일과 d파일 중 양쪽 폰이 없는 파일을 고르세요.',['d'],'d파일에는 양쪽 폰이 없습니다. a파일에는 a2와 a7 폰이 있어 이 비교에서는 d파일이 열린 파일입니다.',choices=[['a','a파일'],['d','d파일']]),
 step('rook','룩의 두 이동 후보',FILE,'move','a1 룩을 d1 또는 e1로 옮겨 열린 파일의 활동을 준비하세요. 두 파일 모두 폰이 없습니다.',['a1d1','a1e1'],'옮긴 룩은 해당 파일의 빈 칸으로 움직일 수 있습니다. 두 수 모두 이 수업에서 비교하는 합법 계획입니다. 유일한 최선 수를 판정하지 않습니다.'),
 step('limit','계획과 결과 구분',FILE,'choice','열린 파일을 찾았을 때 다음 판단은 무엇인가요?',['compare'],'상대의 제어 칸·교환·킹 안전을 더 확인해야 합니다. 열린 파일이라는 사실만으로 승리나 침투 성공을 확정하지 않습니다.',choices=[['win','열린 파일을 차지하면 반드시 이긴다'],['compare','침투 칸과 상대 대응을 더 비교한다']])]),
lesson('plan-piece','plan','막힌 비숍의 길 열기',
 '자기 폰이 막는 대각선을 관찰하고 길을 여는 여러 후보를 비교합니다. 기물 활동만 늘리면 언제나 좋은 수라는 규칙은 아닙니다.', 'rook-bishop',[
 step('blocker','자기 기물의 제약',BISHOP,'square','c1 비숍의 오른쪽 대각선 첫 칸을 막는 백 폰을 선택하세요.',['d2'],'d2 폰이 c1-d2-e3 방향을 막습니다. 반대 대각선에는 b2 폰도 있습니다. 이 위치에서 비숍 자체는 움직일 합법 수가 없습니다.'),
 step('release','길을 여는 후보 비교',BISHOP,'move','d3 또는 d4로 중앙 쪽 대각선을 열거나 b3로 반대쪽 길을 열어 보세요.',['d2d3','d2d4','b2b3'],'선택한 폰 이동으로 비숍의 한 대각선이 열립니다. 후보마다 폰이 지키는 칸도 달라집니다. 상대 위협이 있는 실전에서는 그 비용도 확인해야 합니다.'),
 step('limit','활동과 안전 함께 보기',BISHOP,'choice','비숍 길을 여는 수의 의미를 고르세요.',['candidate'],'이번에는 활동 제한을 줄이는 후보를 비교했습니다. 모든 위치에서 폰을 먼저 움직이라는 처방이나 유일 최선 판정은 아닙니다.',choices=[['always','비숍 앞 폰은 항상 즉시 움직여야 한다'],['candidate','활동을 늘리는 후보이며 상대 위협도 확인해야 한다']])]),
lesson('ending-opposition','ending','직접 오포지션과 차례',
 '두 킹 사이 한 칸과 차례의 관계만 관찰합니다. 이 위치의 최종 승패나 먼 오포지션 전체를 판정하지 않습니다.', 'king-check',[
 step('turn','같은 배치, 백 차례',OPPOSITION,'choice','e4와 e6 킹 사이에 한 칸이 있습니다. 백 차례인 지금 직접 오포지션을 가진 쪽은 누구인가요?',['black'],'직접 오포지션에서 움직이지 않아도 되는 쪽인 흑이 오포지션을 가집니다. 폰 이동·주변 칸에 따라 효과가 달라지므로 승리라는 뜻은 아닙니다.',choices=[['white','백'],['black','흑']]),
 step('blocked','킹이 갈 수 없는 칸',OPPOSITION,'square','백 킹과 흑 킹 사이에서 두 킹 모두 공격하는 빈 칸을 선택하세요.',['e5'],'e5는 두 킹이 모두 공격하는 칸입니다. 백 Ke5나 흑 Ke5는 상대 킹의 공격 안으로 들어가므로 합법적이지 않습니다.'),
 step('black-turn','새 비교 위치: 흑 차례',OPPOSITION_B,'move','같은 배치에서 이번에는 흑 차례입니다. 백이 직접 오포지션을 가집니다. 흑 킹을 d6 또는 f6으로 움직여 합법적인 측면 이동을 비교하세요.',['e6d6','e6f6'],'이동한 킹은 상대 킹과 인접하지 않습니다. 차례가 바뀌면 같은 배치의 오포지션 설명도 달라집니다. 여기서는 장기 승패를 단정하지 않습니다.')]),
lesson('ending-promotion','ending','승격 직후 무승부 경계 비교',
 '승격 방법 자체는 기존 기초에서 배웁니다. 여기서는 동일한 폰 위치에서 퀸 승격의 즉시 스테일메이트와 룩 승격 뒤 합법 수를 비교합니다. 룩 승격의 이론상 승리는 주장하지 않습니다.', 'promotion',[
 step('queen','퀸 승격 결과 관찰',PROMOTE,'move','g폰을 퀸으로 승격해 상대의 체크와 합법 수를 관찰하세요.',['g7g8q'],'흑 킹 a1은 체크가 아니지만 a2·b1·b2로 갈 수 없습니다. 규칙상 즉시 스테일메이트로 무승부입니다.'),
 step('judge','다음 비교 위치: 승격 직후',QUEEN,'choice','흑은 체크가 아니고 합법 수가 없습니다. 어떤 종료인가요?',['stalemate'],'체크가 없는 상태에서 합법 수가 없으므로 스테일메이트입니다. 짧은 엔진 점수가 아니라 규칙으로 확인한 즉시 결과입니다.',choices=[['mate','체크메이트'],['stalemate','스테일메이트']]),
 step('rook','원래 위치로 돌아가 룩과 비교',PROMOTE,'move','이번에는 같은 g폰을 룩으로 승격해 보세요.',['g7g8r'],'흑의 Ka2가 합법적이어서 즉시 스테일메이트가 아닙니다. 대국을 계속할 수 있다는 사실만 확인했으며 룩 쪽의 이론상 승리를 입증한 것은 아닙니다.')])]
REVIEW_PROMPTS={
 'threat-observe':['직전 ...Bb4 뒤 공격받는 백 기물을 선택하세요.','공격받는 나이트를 안전한 칸으로 옮기는 수업의 예시를 재현하세요.','관찰만으로 주장할 수 있는 범위를 고르세요.'],
 'threat-defended':['c3 나이트를 지키는 백 폰을 선택하세요.','비숍을 공격하는 수업의 폰 이동을 재현하세요.','흑 비숍을 되잡으세요.'],
 'plan-file':['a파일과 d파일 중 열린 파일을 고르세요.','룩을 열린 파일로 옮기는 수업의 계획을 재현하세요.','열린 파일을 찾은 다음 판단을 고르세요.'],
 'plan-piece':['비숍의 오른쪽 대각선을 막는 폰을 선택하세요.','비숍의 길을 여는 수업의 폰 이동을 재현하세요.','활동을 개선하는 후보의 의미를 고르세요.'],
 'ending-opposition':['백 차례입니다. 직접 오포지션을 가진 쪽을 고르세요.','두 킹 사이에서 모두 공격받는 빈 칸을 선택하세요.','흑 차례입니다. 수업에서 비교한 킹의 측면 이동을 재현하세요.'],
 'ending-promotion':['먼저 수업에서 비교한 퀸 승격을 재현하세요.','현재 종료 상태를 판별하세요.','이전 비교와 달리 즉시 스테일메이트가 아닌 승격 예시를 재현하세요.']}
for c in LESSONS:
    for s,p in zip(c['steps'],REVIEW_PROMPTS[c['id']]):s['review_prompt']=p
BY_ID={c['id']:c for c in LESSONS}
VERSION=hashlib.sha256(json.dumps(LESSONS,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20]
