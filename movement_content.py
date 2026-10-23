"""Original movement playgrounds; not valid-game/engine or assessment positions."""
import chess
VERSION='interactive-basics-v1'
POLICY='board-learning-v1'
MAX_MOVES=128
NAMES={'R':'룩','B':'비숍','N':'나이트','Q':'퀸','K':'킹','P':'폰'}
RULES={'R':'룩은 가로나 세로로 움직여요.','B':'비숍은 비스듬히 움직여요.','N':'나이트는 두 칸 간 뒤 옆으로 한 칸 뛰어요.','Q':'퀸은 가로·세로·비스듬히 움직여요.','K':'킹은 주변 한 칸으로 움직여요.','P':'폰은 앞으로 가고, 비스듬한 앞칸의 상대 말을 잡아요.'}


def unit(id,symbol,source,targets=(),extras=None,mode='collect',guide=False,note=''):
    board=chess.Board(None);board.set_piece_at(chess.parse_square(source),chess.Piece.from_symbol(symbol))
    for square,piece in (extras or {}).items():board.set_piece_at(chess.parse_square(square),chess.Piece.from_symbol(piece))
    return dict(id=id,symbol=symbol,name=NAMES[symbol],rule=RULES[symbol],fen=board.fen(),source=source,targets=list(targets),mode=mode,guide=guide,note=note,
                goal='◆ 표시를 모두 모아 보세요.' if mode=='collect' else '표시 없이, 서로 다른 빈 칸 두 곳으로 움직여 보세요.',required_moves=2 if mode=='apply' else 0)


UNITS=[
 unit('rook-path','R','b2',['b5','f5','f3'],guide=True),
 unit('rook-block','R','c2',['c4','f4','f6'],{'c5':'P'},note='내 말은 뛰어넘을 수 없어요.'),
 unit('rook-apply','R','e3',extras={'e5':'P'},mode='apply'),
 unit('bishop-path','B','b2',['e5','h2','f4'],guide=True),
 unit('bishop-block','B','c1',['b2','a3','d6'],{'e3':'P'},note='내 말 앞에서는 멈춰요.'),
 unit('bishop-apply','B','f3',extras={'d5':'P'},mode='apply'),
 unit('queen-path','Q','d2',['d5','g5','e3'],guide=True),
 unit('queen-capture','Q','b2',['b5','e5','g3'],{'b5':'p','d4':'P'},note='상대 말은 잡고 그 자리에 서요.'),
 unit('queen-apply','Q','e4',extras={'e6':'P'},mode='apply'),
 unit('knight-path','N','b2',['c4','e5','g4'],guide=True),
 unit('knight-jump','N','d3',['f4','e6','c5'],{'e3':'P','d4':'P'},note='나이트는 중간 말을 뛰어넘어요.'),
 unit('knight-apply','N','f3',extras={'f4':'P'},mode='apply'),
 unit('king-path','K','c3',['c4','d5','e4'],guide=True,note='공격 없는 이동 연습이에요. 체크는 뒤에서 배워요.'),
 unit('king-apply','K','f3',extras={'f4':'P'},mode='apply',note='실제 대국에서는 공격받는 칸으로 갈 수 없어요.'),
 unit('pawn-forward','P','c2',['c4','c5','c6'],guide=True,note='폰은 뒤로 가지 못해요.'),
 unit('pawn-capture','P','d3',['e4','e5','e6'],{'e4':'p'},note='빈 앞칸으로 전진, 상대 말은 비스듬히 잡아요.'),
 unit('pawn-apply','P','f2',mode='apply'),
]
from basic_rules_content import RULE_UNITS, replay_rule
UNITS += RULE_UNITS
STAGES=['rook','bishop','queen','king','knight','pawn','capture','protection','combat','check1','outOfCheck','checkmate1','setup','castling','enpassant','stalemate','value','check2']
for u in UNITS:u.setdefault('stage',{'R':'rook','B':'bishop','Q':'queen','K':'king','N':'knight','P':'pawn'}[u['symbol'].upper()])
SHORT_TITLES={'rook-path':'가로·세로','rook-block':'막힌 길','rook-apply':'새 배치에서 직접','bishop-path':'비스듬한 길','bishop-block':'내 말 앞에서 멈추기','bishop-apply':'새 배치에서 직접','queen-path':'세 방향으로','queen-capture':'상대 말 잡기','queen-apply':'새 배치에서 직접','knight-path':'뛰어가는 길','knight-jump':'말 뛰어넘기','knight-apply':'새 배치에서 직접','king-path':'주변 한 칸','king-apply':'새 배치에서 직접','pawn-forward':'앞으로 한두 칸','pawn-capture':'비스듬히 잡기','pawn-apply':'새 배치에서 직접'}
for u in UNITS:u['short_title']=SHORT_TITLES.get(u['id'],u['name'])
UNITS.sort(key=lambda u:STAGES.index(u['stage']))
BY_ID={u['id']:u for u in UNITS}


def allowed(board,source):
    result=[]
    for m in board.generate_pseudo_legal_moves():
        if m.from_square!=chess.parse_square(source) or m.promotion or board.is_castling(m) or board.is_en_passant(m):continue
        target=board.piece_at(m.to_square)
        if target and target.piece_type==chess.KING:continue
        result.append(m.uci())
    return result


def replay(unit,moves):
    if unit['mode']=='rule':return replay_rule(unit,moves)
    board=chess.Board(unit['fen']);source=unit['source'];remaining=list(unit['targets']);visited=set();history=[]
    done=False
    for value in moves:
        if done:raise ValueError('완료한 연습에는 이동을 더할 수 없어요.')
        if value not in allowed(board,source):raise ValueError('이동 규칙이나 막힌 길을 다시 확인해 주세요.')
        move=chess.Move.from_uci(value);board.push(move);board.turn=chess.WHITE;board.ep_square=None;board.castling_rights=0
        source=value[2:4];history.append(value)
        if source in remaining:remaining.remove(source)
        if source!=unit['source']:visited.add(source)
        done=(not remaining if unit['mode']=='collect' else len(visited)>=unit['required_moves'])
    stuck = bool(not done and unit['symbol']=='P' and any(chess.square_rank(chess.parse_square(t)) <= chess.square_rank(chess.parse_square(source)) for t in remaining))
    return dict(stuck=stuck,fen=board.fen(),source=source,remaining=remaining,visited=sorted(visited),done=done,legal=allowed(board,source) if not done else [],moves=list(moves),move_count=len(moves))


def public_unit(u):
    return dict({k:v for k,v in u.items() if k not in ('example_actions','version','policy')},initial_fen=u['fen'],unit_policy=u.get('policy','same-piece-movement-v1'),version=VERSION,policy=POLICY,max_moves=MAX_MOVES)
