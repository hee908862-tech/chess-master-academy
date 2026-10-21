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
# Original, bounded teaching positions. These lessons assert rule-verifiable
# outcomes, never a general tablebase win from a short example response.
ROOK_START='7k/8/5K2/8/8/8/8/R7 w - - 0 1'
ROOK_AFTER=played(ROOK_START,'f6g6','h8g8')
ROOK_LOOSE='7R/7k/5K2/8/8/8/8/8 b - - 0 1'
ROOK_APPLY='1k6/8/1K6/8/8/8/8/7R w - - 0 1'
RACE='8/8/7k/8/4P3/8/8/K7 b - - 0 1'
RACE_AFTER=played(RACE,'h6g5','e4e5')
RACE_APPLY='8/8/8/3P4/5k2/8/8/K7 b - - 0 1'
ROOKPAWN='k7/P7/8/1K6/8/8/8/8 w - - 0 1'
DRAW50='7k/8/8/8/8/8/R7/K7 w - - 99 50'
DRAW150='7k/8/8/8/8/8/R7/K7 w - - 149 75'
NEW_LESSONS=[
lesson('ending-rook-finish','ending','킹과 룩의 협력 · 메이트까지',
 '킹의 제어 칸과 룩의 가로 공격을 연결합니다. 제시된 상대 응수의 짧은 수순을 완주하며, 모든 시작 위치의 강제 메이트 알고리즘은 아닙니다.', 'mate-stalemate',[
 step('concept','개념 · 킹이 막을 탈출 칸',ROOK_START,'square','킹을 g6으로 옮기면 h파일의 어떤 7랭크 칸을 통제하나요?',['h7'],'Kg6은 h7을 통제하여 상대 킹의 탈출 공간을 줄입니다.'),
 step('practice','실습 · 킹 먼저 협력',ROOK_START,'move','Kg6으로 킹을 협력시켜 보세요. 예시 상대 응수 ...Kg8을 이어 보여 줍니다.',['f6g6'],'킹이 7랭크의 f7·g7·h7을 통제합니다. ...Kg8은 합법 예시 응수입니다.',reply='h8g8'),
 step('finish','실습 · 룩으로 마무리',ROOK_AFTER,'move','Ra8로 8랭크를 공격해 메이트를 완성하세요.',['a1a8'],'룩이 8랭크, 킹이 탈출할 7랭크를 통제합니다. 최종 위치는 규칙으로 확인한 체크메이트입니다.'),
 step('mistake','흔한 실수 · 보호 없는 룩',ROOK_LOOSE,'move','비교 위치입니다. 흑 킹으로 보호받지 않는 h8 룩을 잡아 보세요.',['h7h8'],'룩을 킹 옆에 놓는 것만으로 메이트가 되지 않습니다. h8은 백 킹 f6의 보호 밖이어서 Kxh8이 합법입니다.'),
 step('why','이유 · 공격과 탈출 칸',ROOK_AFTER,'choice','메이트를 확인하려면 무엇을 함께 보나요?',['both'],'체크뿐 아니라 킹 이동·체크 기물 포획·막기를 포함한 모든 합법 대응이 없어야 합니다.',choices=[['check','체크만 확인한다'],['both','체크와 모든 합법 대응의 부재를 확인한다']]),
 step('apply','새 위치 적용 · 반대쪽 킹',ROOK_APPLY,'move','흑 킹은 b8, 백 킹은 b6입니다. h1 룩으로 한 수 메이트를 찾으세요.',['h1h8'],'Rh8은 8랭크를 공격하고 Kb6은 a7·b7·c7을 통제합니다. 새 위치에서도 킹과 룩이 협력합니다.')]),
lesson('ending-pawn-race','ending','통과폰 추격 · 차례와 거리',
 '폰의 승격 방향과 킹의 대각선 추격을 비교합니다. 표시된 예시 수순에서 포획 가능성을 직접 확인하며, 모든 폰 종반의 승패를 단정하지 않습니다.', 'promotion',[
 step('concept','개념 · 승격할 칸',RACE,'square','e4의 백 폰이 승격하는 칸을 선택하세요.',['e8'],'폰은 e8로 향합니다. 킹의 거리와 지금 움직일 차례를 함께 살펴야 합니다.'),
 step('practice','실습 · 대각선으로 접근',RACE,'move','흑 차례입니다. Kg5로 접근하면 예시 백 응수 e5를 보여 줍니다.',['h6g5'],'킹은 대각선으로도 한 칸 이동합니다. 백 폰이 전진하는 동안 킹도 접근합니다.',reply='e4e5'),
 step('catch','실습 · 폰을 잡기',RACE_AFTER,'move','현재 흑 킹으로 백 폰을 잡아 보세요.',['g5f5'],'먼저 Kf5로 접근합니다. 킹은 두 칸을 한 번에 뛰지 못합니다. 예시 e6 뒤 다음 칸에서 잡을 수 있습니다.',reply='e5e6'),
 step('capture','실습 · 추격 마무리',played(RACE_AFTER,'g5f5','e5e6'),'move','이제 흑 킹으로 폰을 잡으세요.',['f5e6'],'Kxe6은 합법입니다. 폰이 사라져 두 킹만 남았습니다.'),
 step('mistake','흔한 실수와 이유 · 배치만 보기',RACE,'choice','같은 기물 배치라면 차례가 달라도 항상 같은 추격 과정인가요?',['turn'],'한 템포가 접근 기회를 바꿉니다. 기물 배치와 함께 FEN의 차례를 보세요.',choices=[['same','차례는 관계없다'],['turn','차례가 접근 기회를 바꾼다']]),
 step('apply','새 위치 적용 · 직접 포획',RACE_APPLY,'move','흑 킹은 f4입니다. Ke5로 접근하면 예시 d6 뒤 폰을 잡을 수 있습니다.',['f4e5'],'대각선 접근으로 d6을 통제합니다. 상대의 예시 전진 뒤 Kxd6을 이어 확인하세요.',reply='d5d6'),
 step('apply-capture','새 위치 · 마무리',played(RACE_APPLY,'f4e5','d5d6'),'move','d6 폰을 잡아 새 위치의 추격을 마치세요.',['e5d6'],'Kxd6이 합법이고 두 킹만 남습니다.')]),
lesson('ending-rook-pawn','ending','룩폰과 코너 킹 · 무승부 경계',
 '룩폰 앞 코너에 있는 킹의 탈출 칸을 셉니다. 즉시 스테일메이트를 검증하는 단원이며 일반 K+P 대 K의 이론상 승패 전체를 다루지 않습니다.', 'mate-stalemate',[
 step('concept','개념 · 코너의 탈출 칸',ROOKPAWN,'square','a8 흑 킹 옆에서 a7 폰이 공격하는 빈 칸은 어디인가요?',['b8'],'a7 폰은 b8을 공격합니다. 킹은 공격받는 칸으로 이동할 수 없습니다.'),
 step('practice','실습 · 킹을 너무 가까이',ROOKPAWN,'move','비교를 위해 Kb6을 두고 흑의 합법 수를 살펴보세요.',['b5b6'],'Kb6 뒤 흑은 체크가 아니면서 합법 수가 없습니다. 즉시 스테일메이트입니다. 이 수는 승리 수업의 정답이 아니라 무승부 실수 관찰입니다.'),
 step('mistake','흔한 실수 · 자동 승리라고 생각',played(ROOKPAWN,'b5b6'),'choice','폰이 7랭크에 있으니 백의 승리인가요?',['draw'],'체크 없이 합법 수가 없으므로 스테일메이트입니다. 폰의 전진 정도만으로 승리를 판단하지 않습니다.',choices=[['win','승격이 가까우므로 승리'],['draw','현재는 스테일메이트 무승부']]),
 step('why','이유 · 체크와 합법 수',played(ROOKPAWN,'b5b6'),'choice','메이트와 무엇이 다른가요?',['no-check'],'흑 킹 a8이 체크 상태가 아니라는 점이 메이트와 다릅니다.',choices=[['no-check','흑 킹이 체크가 아니다'],['pawn','폰이라서 메이트가 불가능하다']]),
 step('apply','새 위치 적용 · h파일', '7k/7P/8/6K1/8/8/8/8 w - - 0 1','move','이번에는 h폰입니다. Kg6 뒤의 종료 상태를 확인하세요.',['g5g6'],'g8은 h7 폰이, h7은 g6 킹이 통제합니다. 흑은 체크가 아닌 채 합법 수가 없어 스테일메이트입니다.')]),
lesson('rules-draw-clock','ending','50수 청구와 75수 자동 종료',
 '반수 카운터와 무승부 청구 조건을 구분합니다. 반복 무승부는 FEN 한 장만으로 판정하지 않습니다.', 'mate-stalemate',[
 step('concept','개념 · 반수 카운터',DRAW50,'choice','FEN의 반수 카운터 99는 무엇을 세나요?',['plies'],'폰 이동이나 포획 이후 양쪽의 착수를 반수 단위로 셉니다. 100반수가 양쪽 각 50수입니다.',choices=[['plies','폰 이동·포획 이후의 반수'],['turns','백이 둔 수만']]),
 step('practice','실습 · 100반수 도달',DRAW50,'move','포획이 아닌 Ra3를 두어 100반수에 도달해 보세요.',['a2a3'],'이 예시에서는 50수 무승부를 청구할 조건이 됩니다. 75수의 자동 종료와 구별하세요.'),
 step('mistake','흔한 실수 · 즉시 자동 종료로 오해',played(DRAW50,'a2a3'),'choice','이 예시의 100반수만으로 자동 종료인가요?',['claim'],'50수 규칙은 청구 조건입니다. 실제 앱의 자동 청구 정책과 체스 규칙의 자동 종료는 구분합니다.',choices=[['auto','항상 자동 종료'],['claim','50수 무승부 청구 조건']]),
 step('why','이유 · 반복 이력',DRAW50,'choice','이 FEN만으로 3회 반복 여부를 알 수 있나요?',['history'],'FEN에는 이전 위치들의 반복 이력이 없습니다. 전체 기보와 차례·캐슬링·앙파상 조건을 함께 확인해야 합니다.',choices=[['fen','기물 배치만 보면 안다'],['history','이전 위치 이력이 필요하다']]),
 step('apply','새 위치 적용 · 150반수',DRAW150,'move','이번 반수 카운터는 149입니다. Ra3 뒤를 비교하세요.',['a2a3'],'이 위치에서는 150반수가 되어 75수 규칙의 자동 무승부 조건입니다. 마지막 수가 메이트이면 메이트가 우선합니다.')])]
for c in NEW_LESSONS:
    for step_ in c['steps']:step_['review_prompt']=step_['prompt']
LESSONS.extend(NEW_LESSONS)

BY_ID={c['id']:c for c in LESSONS}
VERSION=hashlib.sha256(json.dumps(LESSONS,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20]
