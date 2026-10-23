"""Authored introductory teaching overlays. Legacy course positions remain intact."""
import chess

INTRO_ID = 'rook-first-v1'
VERSION = 'beginner-understanding-v1'
BASE = '7k/8/8/8/8/8/8/R5K1 w - - 0 1'
TRANSFER = '7k/8/3P4/8/3R4/8/8/6K1 w - - 0 1'


def teaching(symbol, rule, prior, action):
    names={'R':'룩','B':'비숍','N':'나이트','Q':'퀸','P':'폰','K':'킹'}
    return dict(symbol=symbol,name=names[symbol.upper()],rule=rule,prior=prior,action=action)


ROOK_RULE='룩은 가로나 세로로 여러 칸 움직여요. 다른 말을 뛰어넘지는 못해요.'
INTRO = {'id':INTRO_ID,'title':'처음 시작 · 룩 알아보기','goal':'그림과 이름을 연결하고, 안내 없이 다른 자리에서도 움직여 봐요.', 'steps':[
 dict(id='recognise',kind='identify',phase='recognition',title='이 말은 룩이에요',text='큰 그림과 같은 밝은색 룩을 체스판에서 눌러 보세요.',fen=BASE,answer='a1',reason='룩을 찾았어요. 이제 이 말이 어떻게 움직이는지 볼까요?',teaching=teaching('R','이 말의 이름은 룩이에요. 성의 탑처럼 생긴 위쪽을 살펴보세요.','밝은색이 내 말, 어두운색이 상대 말이에요. 서로 한 번씩 움직여 상대 킹이 공격을 피할 수 없게 하는 게임이에요. 지금은 룩만 배워요.','큰 그림과 같은 내 룩을 눌러 보세요.')),
 dict(id='show-horizontal',kind='demo',phase='demonstration',title='룩은 가로로 움직여요',text='룩이 같은 가로줄을 따라 움직이는 모습을 보세요.',fen=BASE,line=['a1d1'],reason='가로로 이동하는 시범을 확인했어요. 아직 스스로 해결한 기록은 아니에요.',teaching=teaching('R','룩은 같은 가로줄의 빈 칸으로 움직일 수 있어요.','이번에는 보기만 해요. 다시 보기를 눌러 반복할 수 있어요.','움직임을 보고 다음 시범으로 넘어가세요.')),
 dict(id='show-vertical',kind='demo',phase='demonstration',title='룩은 세로로도 움직여요',text='룩이 같은 세로줄을 따라 움직이는 모습을 보세요.',fen=BASE,line=['a1a4'],reason='세로로 이동하는 시범을 확인했어요. 다음에는 직접 해볼 거예요.',teaching=teaching('R','룩은 같은 세로줄로도 움직여요. 비스듬한 칸으로는 갈 수 없어요.','가로와 세로 모두 가능해요. 한 번에 방향을 꺾지는 않아요.','움직임을 본 뒤 직접 연습해 보세요.')),
 dict(id='guided',kind='move',phase='guided',title='표시된 칸으로 옮겨요',text='내 룩을 누른 뒤 화살표 끝의 칸을 눌러 보세요.',fen=BASE,line=['a1a4'],reason='같은 세로줄의 빈 칸을 지나 도착했어요. 이번에는 안내를 따라 한 연습이에요.',teaching=teaching('R',ROOK_RULE,'말을 한 번 누르고, 갈 칸을 한 번 눌러요. 같은 말을 다시 누르면 선택이 취소돼요.','내 룩을 화살표 끝의 표시된 칸으로 옮겨 보세요.')),
 dict(id='independent',kind='move',phase='independent',title='안내 없이 한 번 해봐요',text='룩이 갈 수 있는 빈 칸을 스스로 골라 옮겨 보세요.',fen=BASE,line=[],source='a1',reason='룩의 가로·세로 규칙에 맞게 움직였어요. 갈 수 있는 칸은 여러 개이고, 한 곳만 정답인 것은 아니에요.',teaching=teaching('R',ROOK_RULE,'이번에는 목적지 화살표와 가능한 칸 표시가 없어요. 감점이나 시간제한은 없어요.','룩이 갈 수 있는 빈 칸을 스스로 골라 옮겨 보세요.')),
 dict(id='transfer',kind='move',phase='transfer',title='다른 자리에서도 해봐요',text='룩을 움직여 보세요. 앞에 있는 내 폰을 뛰어넘거나 잡을 수는 없어요.',fen=TRANSFER,line=[],source='d4',reason='새 배치에서도 룩의 규칙에 맞게 움직였어요. 내 말 앞에서는 멈춰야 해요. 이것은 이 두 배치의 확인이며 체스 실력 인증은 아니에요.',teaching=teaching('R',ROOK_RULE,'룩의 자리가 바뀌었어요. 세로줄 위의 작은 둥근 말은 내 폰이에요. 내 말이 있는 칸이나 그 너머로는 지나갈 수 없어요.','내 폰을 뛰어넘지 않고 룩을 움직일 수 있는 빈 칸을 골라 보세요.')),
]}

# One visible prerequisite and rule per existing exercise; no answer/history rewrites.
OVERLAYS = {
 'rook-bishop':[
 teaching('R',ROOK_RULE,'이 말은 룩이에요. 위쪽이 성의 탑처럼 생겼어요. 먼저 이름·움직임을 확인하고 싶으면 룩 첫 수업을 선택하세요.','룩을 누르고 화살표 끝의 칸을 누르세요. 좌표는 위치를 찾는 보조 표시에요.'),
 teaching('B','이 말은 비숍이에요. 비스듬한 줄을 따라 움직이고 다른 말을 뛰어넘지 못해요.','비스듬한 줄은 한 칸 위·옆으로 함께 이어지는 방향이에요. 비숍은 출발한 칸과 같은 색 칸만 다녀요.','비숍을 누르고 비스듬한 화살표 끝으로 옮겨 보세요.'),
 teaching('R','룩은 내 말을 뛰어넘거나 내 말이 있는 칸으로 갈 수 없어요.','룩 앞의 작은 둥근 말은 내 폰이에요. 폰은 지금 움직이지 않아요.','룩을 폰 바로 앞의 빈 칸으로 옮겨 보세요.')],
 'knight-queen':[
 teaching('N','이 말은 나이트예요. 말의 머리 모양이며 두 칸 간 뒤 옆으로 한 칸 꺾인 곳에 도착해요.','나이트만 중간 말을 뛰어넘을 수 있어요. 내 말이 있는 칸에 도착할 수는 없어요.','화살표가 시작하는 나이트를 골라 끝의 칸으로 옮겨 보세요.'),
 teaching('Q','이 말은 퀸이에요. 가로·세로·비스듬히 여러 칸 갈 수 있어요.','퀸도 중간 말을 뛰어넘지 못해요. 이번에는 비스듬한 방향만 연습해요.','퀸을 골라 비스듬한 화살표 끝으로 옮겨 보세요.')],
 'pawn-capture':[
 teaching('P','이 말은 폰이에요. 빈 앞칸으로 한 칸 가고 뒤로는 가지 못해요.','자기 시작 칸에 있는 폰은 앞 두 칸이 모두 비었을 때 두 칸도 갈 수 있어요. 지금 밝은 폰의 앞은 화면 위쪽이에요.','이번에는 표시된 폰을 두 칸 앞으로 옮겨 보세요.'),
 teaching('P','폰은 움직일 때는 앞으로, 상대 말을 잡을 때는 비스듬한 앞칸으로 가요.','잡기는 상대 말을 판에서 빼고 그 자리에 내 말을 놓는 것이에요. 내 말은 잡지 못해요.','내 폰을 비스듬한 앞칸의 어두운 폰 자리로 옮겨 잡아 보세요.'),
 teaching('R','룩은 가로·세로로 가다가 상대 말이 있는 칸에서 멈춰 그 말을 잡아요.','폰과 달리 룩은 이동할 때와 잡을 때의 방향이 같아요.','내 룩으로 같은 세로줄의 어두운 나이트를 잡아 보세요.')],
 'king-check':[
 teaching('K','이 말은 킹이에요. 지켜야 하는 말이며 안전한 주변 한 칸으로 움직여요.','상대 말이 잡을 수 있는 칸은 킹에게 안전하지 않아요. 두 킹도 서로 붙을 수 없어요.','내 킹을 표시된 안전한 한 칸으로 옮겨 보세요.'),
 teaching('K','상대 말이 내 킹을 공격하고 있으면 체크라고 해요. 반드시 공격에서 벗어나야 해요.','상대 룩의 공격선을 먼저 살펴보세요. 지금은 킹을 옮겨 피하는 방법을 배워요.','내 킹을 화살표 끝으로 옮겨 룩의 공격선에서 벗어나 보세요.'),
 teaching('B','체크를 피하는 다른 방법은 상대 공격길에 내 말을 놓아 막는 것이에요.','비숍은 비스듬히 움직여요. 룩처럼 길을 따라 오는 공격은 중간을 막을 수 있어요.','내 비숍을 표시된 칸에 놓아 킹으로 오는 공격길을 막아 보세요.'),
 teaching('K','체크하는 상대 말을 잡아도 킹을 지킬 수 있어요. 잡은 뒤에도 안전해야 해요.','상대 말이 지켜 주는 칸에는 내 킹을 둘 수 없어요.','내 킹으로 바로 앞의 상대 룩을 잡아 보세요.')],
 'mate-stalemate':[
 teaching('Q','체크를 당한 킹이 피하기·막기·잡기 어느 방법으로도 벗어나지 못하면 체크메이트예요.','퀸은 가로·세로·비스듬히 공격해요. 내 킹이 퀸을 지켜 주면 상대 킹이 함부로 잡지 못해요.','퀸을 표시된 칸으로 옮긴 뒤 공격과 보호 관계를 살펴보세요.'),
 teaching('K','먼저 킹이 공격받는지, 그다음 공격에서 벗어날 수 있는지 살펴요.','이 단계는 설명을 보며 상태 이름을 익히는 예시이며 독립 진단이 아니에요.','상대 킹의 공격선과 갈 수 있는 칸을 보고 상태를 고르세요.'),
 teaching('K','공격받지 않는 쪽이 둘 수 있는 수가 하나도 없으면 스테일메이트로 비겨요.','체크메이트와의 차이는 킹이 지금 공격받고 있는지예요. 갈 곳이 없다는 사실만으로 승패를 정하지 않아요.','어두운 킹이 공격받는지 살펴보고 상태 이름을 고르세요.')],
 'castling':[
 teaching('K','캐슬링은 킹과 룩을 한 번에 옮기는 특별한 수예요. 킹을 두 칸 옮기면 룩도 따라와요.','두 말이 아직 움직이지 않았고 사이가 비어 있어야 해요. 킹의 출발·통과·도착 칸도 안전해야 해요.','킹을 오른쪽 표시 칸으로 옮기고 룩이 따라오는 모습을 보세요.'),
 teaching('K','캐슬링은 반대편 룩과도 할 수 있어요. 킹은 이번에도 두 칸만 움직여요.','킹과 그 룩이 움직인 적 없고, 사이가 비며 킹의 길이 안전해야 해요.','킹을 왼쪽 표시 칸으로 옮기고 룩의 새 자리를 보세요.'),
 teaching('K','킹이 공격받는 칸을 통과하는 캐슬링은 할 수 없어요.','룩의 가로·세로 공격길을 먼저 살펴보세요. 킹이 지금 체크인 경우에도 캐슬링은 안 돼요.','상대 룩이 킹의 길을 공격하는지 보고 가능 여부를 고르세요.')],
 'promotion':[
 teaching('P','폰이 맨 끝줄에 도착하면 퀸·룩·비숍·나이트 중 하나로 바꿔요. 이것을 승격이라고 해요.','킹이나 폰으로는 바꿀 수 없어요. 선택 창에서 그림과 이름을 함께 볼 수 있어요.','폰을 표시된 끝줄로 옮긴 뒤 이번 예시에서는 퀸을 골라 보세요.'),
 teaching('P','승격할 때는 퀸 외의 말도 고를 수 있어요.','이번에는 말 머리 모양인 나이트를 골라 보는 안내 연습이에요. 다른 승격도 합법이지만 이 예시의 선택은 달라요.','폰을 끝줄로 옮긴 뒤 나이트를 골라 보세요.')],
 'en-passant':[
 teaching('P','폰은 보통 비스듬한 앞칸의 상대 말을 잡아요. 앙파상은 그 규칙의 특별한 경우예요.','옆의 상대 폰이 방금 두 칸 전진했을 때, 바로 다음 수에만 한 칸 왔다고 생각하고 잡을 수 있어요. 먼저 상대 움직임을 보세요.','상대 폰이 움직인 뒤 내 폰을 표시된 빈 칸으로 옮겨 잡아 보세요.'),
 teaching('P','앙파상 기회는 상대 폰의 두 칸 전진 바로 다음 수에만 있어요.','배치가 같아 보여도 이미 다른 수를 뒀다면 기회가 끝나요.','이번 배치는 그 기회가 지난 상태예요. 가능 여부를 골라 보세요.')],
 'value-protection':[
 teaching('R','내 말을 보호한다는 것은 상대가 잡으면 다시 잡을 수 있도록 다른 말을 놓는 것이에요.','룩은 가로·세로로 잡아요. 나이트는 말 머리 모양이에요. 기물 가치 숫자는 보호 관계를 익힌 뒤 참고해도 돼요.','룩을 표시된 칸에 두어 나이트가 있는 세로줄을 지켜 보세요.'),
 teaching('B','상대가 내 말을 잡으려 할 때는 안전한 곳으로 옮기는 방법이 있어요.','상대 룩은 세로줄로 공격하고 비숍은 비스듬히 이동해요.','내 비숍을 표시된 칸으로 옮겨 상대 룩의 공격길에서 벗어나 보세요.')],
 'opening-turns':[
 teaching('P','밝은색(백)이 먼저 두고, 어두운색(흑)과 한 번씩 번갈아 둬요.','처음 몇 수를 오프닝이라고 해요. 중앙을 쓰고 말을 꺼내며 킹을 안전하게 준비하는 단계예요. 이 순서는 한 가지 예시예요.','안내를 따라 폰, 나이트, 비숍을 차례로 옮기세요. 상대 수는 자동으로 보여 줘요.'),
 teaching('p','이번에는 내가 어두운색(흑)이에요. 보드도 내 쪽에서 보도록 돌렸어요.','폰은 자기 앞쪽으로 가요. 화면을 돌려도 각자의 전진 방향과 규칙은 그대로예요.','내 폰을 표시된 칸으로 옮겨 상대의 첫 수에 응답해 보세요.')]
}


def lesson_teaching(course_id,index,step,board):
    value=dict(step.get('teaching') or OVERLAYS[course_id][index])
    # An opening sequence changes the piece being introduced on each own turn.
    if course_id=='opening-turns' and index==0:
        piece=next((board.piece_at(chess.parse_square(u[:2])) for u in step['line'] if chess.Move.from_uci(u) in board.legal_moves),None)
        if piece and piece.piece_type in (chess.KNIGHT,chess.BISHOP):
            value=teaching(piece.symbol(), '나이트는 두 칸 뒤 옆 한 칸으로 뛰어요.' if piece.piece_type==chess.KNIGHT else '비숍은 비스듬한 줄로 움직여요.',value['prior'],'이 말을 처음 자리에서 활동할 곳으로 꺼내 보세요.')
    value['symbol']=value['symbol'].upper() if chess.Board(step['fen']).turn else value['symbol'].lower()
    return value


def validate_intro():
    for step in INTRO['steps']:
        board=chess.Board(step['fen']);assert board.is_valid()
        for u in step.get('line',[]):
            assert chess.Move.from_uci(u) in board.legal_moves
            board.push_uci(u)
        if step['kind']=='identify':assert chess.Board(step['fen']).piece_at(chess.parse_square(step['answer'])).piece_type==chess.ROOK
        if step.get('source'):assert any(m.from_square==chess.parse_square(step['source']) for m in board.legal_moves)
