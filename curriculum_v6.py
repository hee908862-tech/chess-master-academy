"""Curriculum exercise generator: server-side chess logic; verify every scenario at import.
No single-square fixed answer is accepted as a substitute for tactical objectives.
"""
import chess, random
COURSES={
 'fork':('포크','기초','나이트가 동시에 두 기물을 공격하지만, 나이트 자체가 안전한지 확인합니다.'),
 'pin':('핀','기초','왕 뒤의 기물을 선상으로 묶어 움직이지 못하도록 하는 전술입니다.'),
 'skewer':('스큐어','초급','왕처럼 중요한 기물을 먼저 공격해 뒤에 있는 기물의 손실을 노립니다.'),
 'discovered':('발견 공격','초급','앞을 막던 기물이 비켜 뒤의 룩이 체크하는 상황을 만듭니다.'),
 'double':('더블 어택','초급','한 기물의 이동으로 둘 이상의 상대 기물을 동시에 위협합니다.'),
 'safecheck':('합법적인 체크','입문','왕을 공격하면서 자신의 왕은 안전하게 유지하는 수를 찾아봅니다.'),
 'capture':('안전한 기물 포획','입문','상대 기물 포획 후 즉시 큰 손해를 보지 않는 수를 찾습니다.'),
 'mate':('체크메이트 기본','중급','체크와 체크메이트의 차이를 실제 수로 확인합니다.'),
 'opening':('전개와 중앙 장악','입문','중앙을 다투고 나이트와 비숍을 효율적으로 전개합니다.'),
 'endgame':('킹·폰 엔드게임','초급','승격을 위한 폰의 전진과 킹의 지원을 살펴봅니다.')}

def make(template,flip=False):
 b=chess.Board(None)
 for sq,piece in template['pieces'].items(): b.set_piece_at(chess.parse_square(sq),chess.Piece.from_symbol(piece))
 b.turn=chess.WHITE; b.clear_stack()
 move=chess.Move.from_uci(template['move'])
 if flip:
  b=b.transform(chess.flip_horizontal)
  move=chess.Move.from_uci(template['move'].translate(str.maketrans('abcdefgh','hgfedcba')))
 assert b.is_valid() and move in b.legal_moves,(template,b.fen(),move)
 return {'fen':b.fen(),'sample_move':move.uci(),'objective':template['objective'],'focus':template['focus'],'note':template['note'],'theme':template['theme']}

RAW=[
 # knight fork must survive enemy response, check if knight is defended by opponent next
 dict(theme='fork',pieces={'a1':'K','h8':'k','f3':'N','d7':'r','f7':'q'},move='f3e5',objective='fork',focus='N',note='e5의 나이트가 d7 룩과 f7 퀸을 동시에 공격합니다. 흑 왕과 다른 흑 기물이 즉시 잡을 수 있는지도 확인합니다.'),
 dict(theme='fork',pieces={'a1':'K','h8':'k','c3':'N','b6':'q','f6':'r'},move='c3d5',objective='fork',focus='N',note='d5의 나이트가 b6 퀸과 f6 룩을 동시에 노립니다. 단일 기물 이동으로 둘을 공격하는 전형적인 포크입니다.'),
 dict(theme='pin',pieces={'a2':'K','e8':'k','b1':'R','e7':'n'},move='b1e1',objective='pin',focus='R',note='e파일에 룩을 두어 e7의 나이트 뒤에 있는 킹까지 압박합니다. 나이트는 움직이면 체크를 허용합니다.'),
 dict(theme='pin',pieces={'a1':'K','e8':'k','a4':'B','c6':'n'},move='a4b5',objective='pin',focus='B',note='b5 비숍과 e8 킹 사이에 c6 나이트가 놓입니다. 핀은 상대 기물의 이동 자유를 제한합니다.'),
 dict(theme='skewer',pieces={'a1':'K','e6':'k','e8':'q','a4':'R'},move='a4e4',objective='skewer',focus='R',note='룩의 e4 체크 뒤에 왕과 퀸이 같은 파일에 있어, 왕이 비키면 퀸을 공격할 수 있습니다.'),
 dict(theme='skewer',pieces={'h1':'K','d6':'k','f6':'q','a5':'R'},move='a5a6',objective='skewer',focus='R',note='a6의 룩이 먼저 왕을 공격하고 그 뒤 같은 랭크의 퀸을 위협합니다.'),
 dict(theme='discovered',pieces={'a1':'K','e8':'k','e1':'R','e2':'B'},move='e2g4',objective='discovered',focus='B',note='비숍이 e파일에서 비키자 뒤의 룩이 흑 킹을 체크합니다.'),
 dict(theme='discovered',pieces={'a1':'K','d8':'k','d1':'R','d2':'B'},move='d2f4',objective='discovered',focus='B',note='d2의 비숍이 이동하면서 d파일 룩의 공격이 열립니다.'),
 dict(theme='double',pieces={'a1':'K','a8':'k','d2':'B','f2':'P','b6':'r','h6':'q'},move='d2e3',objective='double',focus='B',note='e3의 비숍이 b6의 룩과 h6의 퀸을 동시에 공격합니다. f2 폰이 비숍을 보호합니다.'),
 dict(theme='double',pieces={'h1':'K','h8':'k','e2':'B','c2':'P','a6':'q','g6':'r'},move='e2d3',objective='double',focus='B',note='d3 비숍이 a6 퀸과 g6 룩을 동시에 노립니다. c2 폰이 비숍을 보호합니다.'),
]
CATALOG={k:[] for k in COURSES}
for item in RAW:
 for flip in (False,True):
  try: CATALOG[item['theme']].append(make(item,flip))
  except AssertionError: pass
# Other learning areas use more broad objective-based validation on existing legal positions.
MORE=[
 ('safecheck',{'pieces':{'a1':'K','h8':'k','a2':'R'},'move':'a2h2','note':'체크의 조건은 왕이 현재 공격받는 것입니다.'}),
 ('safecheck',{'pieces':{'h1':'K','a8':'k','h2':'R'},'move':'h2a2','note':'다양한 합법 체크 중 하나를 찾아보세요.'}),
 ('capture',{'pieces':{'a1':'K','h8':'k','d1':'R','d5':'q'},'move':'d1d5','note':'같은 파일에 놓인 퀸을 룩으로 포획합니다.'}),
 ('capture',{'pieces':{'a1':'K','h8':'k','f3':'N','e5':'q'},'move':'f3e5','note':'나이트가 퀸을 포획하는 상황입니다.'}),
 ('opening',{'pieces':{'e1':'K','e8':'k','g1':'N','e4':'P','e5':'p'},'move':'g1f3','note':'나이트 전개는 중앙을 압박합니다.'}),
 ('opening',{'pieces':{'e1':'K','e8':'k','b1':'N','d4':'P','d5':'p'},'move':'b1c3','note':'중앙 폰을 지원하면서 경량 기물을 전개합니다.'}),
 ('endgame',{'pieces':{'e3':'K','h8':'k','d4':'P'},'move':'d4d5','note':'폰 전진 가능성과 킹 지원 관계를 확인하세요.'}),
 ('endgame',{'pieces':{'e3':'K','h8':'k','d5':'P'},'move':'d5d6','note':'승격 목표까지 남은 거리를 계산하세요.'}),
]
for key,item in MORE:
 template=dict(theme=key,objective=key,focus='-',pieces=item['pieces'],move=item['move'],note=item['note'])
 for flip in (False,True):
  try: CATALOG[key].append(make(template,flip))
  except AssertionError: pass

def classify(b,move,objective):
 """Evaluate outcomes against concept, not an arbitrary pixel destination."""
 if move not in b.legal_moves:return False,'합법적으로 이동할 수 없는 수입니다.'
 p=b.piece_at(move.from_square)
 new=b.copy(stack=False); capture=b.is_capture(move);new.push(move)
 if objective=='safecheck': return new.is_check(),'상대 킹이 공격받는지 확인하세요.'
 if objective=='capture':return capture and b.piece_at(move.to_square) and b.piece_at(move.to_square).piece_type>=chess.KNIGHT,'큰 기물의 안전한 포획을 찾아보세요.'
 if objective=='mate':return new.is_checkmate(),'체크메이트가 성립하는지 확인하세요.'
 if objective=='opening':return p and p.piece_type in (chess.KNIGHT,chess.BISHOP) and chess.square_rank(move.from_square) in (0,1),'중앙 전개 기물을 선택하세요.'
 if objective=='endgame':return p and p.piece_type==chess.PAWN and chess.square_rank(move.to_square)>chess.square_rank(move.from_square),'폰을 승격 방향으로 움직여 보세요.'
 opponent=chess.BLACK
 target=[]
 for sq in chess.SQUARES:
  enemy=new.piece_at(sq)
  if enemy and enemy.color==opponent and enemy.piece_type not in (chess.KING,chess.PAWN) and new.is_attacked_by(chess.WHITE,sq):target.append(sq)
 if objective in ('fork','double'):
  attacks=[sq for sq in target if new.is_attacked_by(chess.WHITE,sq) and new.piece_at(move.to_square) and sq in new.attacks(move.to_square)]
  if len(attacks)<2:return False,'한 기물로 동시에 중요한 기물 두 개 이상을 공격하세요.'
  if new.is_attacked_by(chess.BLACK,move.to_square):return False,'공격한 기물이 바로 잡힐 수 있습니다. 안전한 수를 찾아보세요.'
  if objective=='fork':return p and p.piece_type==chess.KNIGHT,'나이트의 안전한 포크를 만드세요.'
  return True,'두 가지 위협을 동시에 만들었습니다.'
 if objective=='pin':
  # Piece geometrically pinned to its king (chess.is_pinned), after move
  pinned=[sq for sq in chess.SQUARES if (q:=new.piece_at(sq)) and q.color==opponent and q.piece_type!=chess.KING and new.is_pinned(opponent,sq)]
  return bool(pinned),'왕 앞의 상대 기물을 핀으로 고정하세요.'
 if objective=='skewer':
  if not new.is_check():return False,'먼저 킹을 체크해야 합니다.'
  king=new.king(opponent)
  if king is None:return False,'킹 배치를 확인하세요.'
  def line_direction(a,b):
   dx=chess.square_file(b)-chess.square_file(a);dy=chess.square_rank(b)-chess.square_rank(a)
   if dx==0:return (0,1 if dy>0 else -1)
   if dy==0:return (1 if dx>0 else -1,0)
   if abs(dx)==abs(dy):return (1 if dx>0 else -1,1 if dy>0 else -1)
   return None
  direction=line_direction(move.to_square,king)
  if not direction:return False,'체크한 기물과 킹의 직선을 확인하세요.'
  x=chess.square_file(king)+direction[0];y=chess.square_rank(king)+direction[1]
  while 0<=x<8 and 0<=y<8:
   q=new.piece_at(chess.square(x,y))
   if q:return q.color==opponent and q.piece_type in (chess.QUEEN,chess.ROOK),'킹 뒤쪽의 고가치 기물을 노리세요.'
   x+=direction[0];y+=direction[1]
  return False,'킹 뒤의 기물을 노리세요.'
 if objective=='discovered':
  if not new.is_check():return False,'막고 있던 기물이 비켜난 뒤에 체크가 성립해야 합니다.'
  king=new.king(opponent)
  rook_attack=any((q:=new.piece_at(src)) and q.color==chess.WHITE and q.piece_type in (chess.ROOK,chess.QUEEN) for src in new.attackers(chess.WHITE,king))
  return bool(p and p.piece_type in (chess.BISHOP,chess.KNIGHT,chess.PAWN) and rook_attack),'막고 있던 기물이 비켜 룩의 체크를 열도록 해보세요.'
 return False,'목표 개념에 맞는 수를 찾아보세요.'
