"""Original board-action lessons covering the twelve non-piece basic topics.

Only the topic outline was consulted at Lichess; no source wording, positions,
illustrations, or implementation is copied. All ordinary move scenes use full
legal chess positions. The explicitly labelled setup scene uses placement, not
chess moves. This module is pure and never writes scores or account records.
"""
import chess

VERSION = 'basic-rules-v1'
POLICY = 'legal-board-goals-v1'
VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
          chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
SOURCES = {key: 'https://github.com/lichess-org/lila/blob/master/ui/learn/src/stage/' + key + '.ts'
           for key in ('rook', 'bishop', 'queen', 'king', 'knight', 'pawn',
                       'capture', 'protection', 'combat', 'check1', 'outOfCheck',
                       'checkmate1', 'setup', 'castling', 'enpassant', 'stalemate', 'value', 'check2')}


def position(pieces, turn='w', rights='-', ep='-'):
    """Build our own compositions from square/piece placements."""
    board = chess.Board(None)
    for entry in pieces.split():
        square, symbol = entry.split(':')
        board.set_piece_at(chess.parse_square(square), chess.Piece.from_symbol(symbol))
    board.turn = turn == 'w'
    board.set_castling_fen(rights)
    board.ep_square = None if ep == '-' else chess.parse_square(ep)
    return board.fen(en_passant='fen')


def scene(id, stage, name, symbol, rule, goal, fen, predicate, example_actions, **extra):
    return dict(id='rules-' + id, stage=stage, name=name, symbol=symbol,
                rule=rule, goal=goal, fen=fen, mode='rule', kind='move',
                predicate=dict(type=predicate) if isinstance(predicate, str) else predicate,
                example_actions=example_actions, version=VERSION, policy=POLICY,
                scope='규칙을 직접 확인하는 연습 · 점수와 숙련 인증 없음', **extra)


def ep_scene(id, source, before, reply, example, predicate='en_passant', **extra):
    board = chess.Board(before); board.push_uci(reply)
    return scene(id, 'enpassant', '앙파상', 'P',
                 '상대 폰이 두 칸 와서 내 폰 옆에 섰다면, 바로 다음 수에만 지나온 칸에서 잡을 수 있어요.',
                 '상대의 두 칸 전진을 본 뒤, 내 폰으로 특별한 잡기를 해보세요.',
                 board.fen(en_passant='fen'), predicate, [example],
                 prelude={'before_fen': before, 'moves': [reply],
                          'after_fen': board.fen(en_passant='fen'),
                          'label': '교육용 상대 응수 · 이 이동을 본 뒤 내가 둡니다'},
                 source_hint=source, **extra)


_SETUP = chess.Board()
_WHITE_SETUP = {chess.square_name(s): p.symbol() for s, p in sorted(_SETUP.piece_map().items()) if p.color}
_SETUP_BOARD = chess.Board()
for _s, _p in list(_SETUP_BOARD.piece_map().items()):
    if _p.color: _SETUP_BOARD.remove_piece_at(_s)
_SETUP_BOARD.castling_rights = 0

RULE_UNITS = [
    scene('capture-rook', 'capture', '상대 말 잡기', 'R',
          '상대 말이 있는 칸으로 가면 그 말을 치우고 내 말이 그 자리를 차지해요.',
          '룩으로 상대 폰을 잡아보세요.', position('g1:K b2:R g8:k b5:p'),
          'capture', ['b2b5'], reason='상대 폰 대신 내 룩이 그 칸에 놓였어요. 내 말은 잡을 수 없어요.'),
    scene('capture-pawn', 'capture', '폰으로 잡기', 'P',
          '폰은 빈 앞칸으로 가지만, 잡을 때는 비스듬한 앞칸으로 가요.',
          '내 폰으로 상대 폰을 잡아보세요.', position('g1:K d4:P h8:k c5:p'),
          'capture', ['d4c5'], reason='전진 방향과 잡는 방향이 다르다는 것을 확인했어요.'),
    scene('avoid-loss', 'protection', '공격에서 피하기', 'B',
          '내 말이 공격받으면 상대가 바로 잡을 수 없는 곳으로 옮길 수 있어요.',
          '공격받는 비숍을 상대가 다음 수에 잡을 수 없는 칸으로 옮겨보세요.',
          position('g1:K c4:B h8:k a4:r'), {'type': 'safe_move', 'source': 'c4'}, ['c4d3'],
          reason='이 배치에서는 상대가 그 비숍을 바로 잡는 합법 수가 없어요. 이후까지 항상 안전하다는 뜻은 아니에요.'),
    scene('protect-piece', 'protection', '다시 잡을 준비', 'R',
          '내 말을 보호한다는 것은 상대가 잡았을 때 다시 잡을 수 있도록 준비하는 것이에요.',
          '나이트는 그대로 두고 룩을 옮겨 나이트를 보호해보세요.',
          position('g1:K a1:R c4:N h8:k c8:r'), {'type': 'protect', 'target': 'c4'}, ['a1c1'],
          reason='상대 룩이 나이트를 잡으면 내 말로 그 룩을 다시 잡을 수 있어요. 보호가 모든 교환을 유리하게 만들지는 않아요.'),
    scene('capture-safely', 'combat', '잡기와 안전 함께', 'Q',
          '잡을 수 있다는 것만 보지 말고, 잡은 내 말이 바로 되잡히는지도 살펴요.',
          '퀸으로 상대 말을 잡되, 그 퀸이 다음 수에 바로 잡히지 않게 해보세요.',
          position('g1:K d3:Q g8:k d8:r d6:p f5:n'), {'type': 'capture', 'safe': True}, ['d3f5'],
          reason='잡기와 즉시 되잡힘을 함께 확인했어요. 이 한 수 검사만으로 장기적인 최선수를 보장하지는 않아요.'),
    scene('give-check', 'check1', '체크 만들기', 'R',
          '킹을 실제로 잡지 않고 공격하는 것을 체크라고 해요.',
          '한 수로 상대 킹을 체크해보세요.',
          position('g1:K b2:R g8:k'), 'check', ['b2b8'],
          reason='이동 후 상대 킹이 공격받고 있어요. 상대는 반드시 체크에서 벗어나야 해요.'),
    scene('escape-king', 'outOfCheck', '킹으로 체크 피하기', 'K',
          '체크일 때 킹을 공격받지 않는 칸으로 옮겨 피할 수 있어요.',
          '내 킹을 안전한 칸으로 옮겨 체크에서 벗어나보세요.',
          position('f1:K a8:k f8:r'), {'type': 'escape', 'method': 'king'}, ['f1g1'],
          reason='킹이 공격선에서 벗어났어요. 공격받는 칸으로 가는 수는 허용되지 않아요.'),
    scene('escape-block', 'outOfCheck', '공격길 막기', 'B',
          '길을 따라 오는 체크는 중간에 내 말을 놓아 막을 수도 있어요.',
          '킹을 움직이지 말고 비숍으로 룩의 공격길을 막아보세요.',
          position('e1:K c1:B a8:k e8:r'), {'type': 'escape', 'method': 'block'}, ['c1e3'],
          reason='비숍이 룩의 공격길을 막았어요. 나이트의 체크는 중간을 막아 해결할 수 없어요.'),
    scene('escape-capture', 'outOfCheck', '체크하는 말 잡기', 'K',
          '체크하는 말을 잡아도 괜찮지만, 잡은 뒤 내 킹이 안전해야 해요.',
          '체크하는 룩을 잡아 내 킹을 지켜보세요.',
          position('e1:K a8:k e2:r'), {'type': 'escape', 'method': 'capture'}, ['e1e2'],
          reason='체크하던 말을 잡았고 다른 공격에도 노출되지 않았어요.'),
    scene('mate-queen', 'checkmate1', '체크메이트', 'Q',
          '체크를 피하기·막기·잡기 어느 방법으로도 해결하지 못하면 체크메이트예요.',
          '한 수로 체크메이트를 만들어보세요.',
          position('f6:K g5:Q h8:k'), 'mate', ['g5g7'],
          reason='상대는 체크이고, 체크를 해결할 합법 수가 하나도 없어요.'),
    scene('mate-rook', 'checkmate1', '다른 말로 메이트', 'R',
          '내 킹도 상대 킹의 도망갈 칸을 막는 데 도움을 줘요.',
          '룩과 킹이 함께 한 수 메이트를 만들어보세요.',
          position('g6:K f1:R h8:k'), 'mate', ['f1f8'],
          reason='룩이 체크하고 내 킹이 가까운 탈출 칸을 막고 있어요.'),
    scene('setup-orientation', 'setup', '보드 방향', 'K',
          '밝은색 쪽에서 본 내 오른쪽 아래 모서리는 밝은 칸이에요.',
          '내 쪽 오른쪽 아래의 밝은 모서리 칸을 눌러보세요.', chess.STARTING_FEN,
          {'type': 'squares', 'squares': ['h1']}, ['square:h1'], kind_override='square',
          reason='보드 방향부터 맞추면 양쪽의 초기 배치도 맞출 수 있어요.'),
    scene('setup-place', 'setup', '처음 자리 놓기', 'Q',
          '룩·나이트·비숍을 양쪽에 놓고 퀸은 자기 색 칸, 킹은 옆칸, 폰은 앞줄이에요.',
          '지금 보여주는 말을 알맞은 시작 칸에 놓아 밝은색 진영을 완성해보세요.',
          _SETUP_BOARD.fen(), {'type': 'placement', 'pieces': _WHITE_SETUP},
          ['place:' + symbol + ':' + square for square, symbol in _WHITE_SETUP.items()], kind_override='place',
          placement_order=['R','N','B','Q','K','P'],
          reason='퀸은 자기 색 칸에 놓아 밝은색 퀸은 d1, 킹은 e1이에요. 이것은 배치 연습이며 대국 중 말을 이렇게 옮길 수 있다는 뜻은 아니에요.'),
    scene('castle-right', 'castling', '킹사이드 캐슬링', 'K',
          '킹사이드 캐슬링은 킹이 킹사이드 룩 쪽으로 두 칸 가는 수예요.',
          '킹사이드 캐슬링을 해보세요.', position('e1:K a1:R h1:R d2:P e2:P f2:P e8:k d7:p e7:p f7:p', rights='KQ'),
          {'type': 'castle', 'side': 'king'}, ['e1g1'], reason='킹은 g1, 룩은 f1로 함께 움직였어요.'),
    scene('castle-left', 'castling', '퀸사이드 캐슬링', 'K',
          '퀸사이드 캐슬링도 킹이 퀸사이드 룩 쪽으로 두 칸 가요.',
          '퀸사이드 캐슬링을 해보세요.', position('e1:K a1:R h1:R d2:P e2:P f2:P e8:k d7:p e7:p f7:p', rights='KQ'),
          {'type': 'castle', 'side': 'queen'}, ['e1c1'], reason='킹은 c1, 룩은 d1로 함께 움직였어요.'),
    scene('castle-blocked', 'castling', '먼저 길 확인', 'N',
          '킹과 룩 사이에 내 말이 있으면 캐슬링할 수 없어요.',
          '킹과 킹사이드 룩 사이를 막는 내 말을 눌러보세요.', position('e1:K h1:R g1:N e8:k', rights='K'),
          {'type': 'squares', 'squares': ['g1']}, ['square:g1'], kind_override='square',
          reason='나이트가 있는 동안에는 길이 비어 있지 않아요. 실제 대국에서는 차례에 맞춰 먼저 나이트를 옮겨야 해요.'),
    scene('castle-attacked', 'castling', '공격받는 길', 'K',
          '킹이 체크인 때, 또는 지나가거나 도착할 칸이 공격받으면 캐슬링할 수 없어요.',
          '킹이 지나갈 칸 중 상대 룩이 공격하는 칸을 눌러보세요.', position('e1:K h1:R a8:k f8:r', rights='K'),
          {'type': 'attacked_squares', 'squares': ['f1'], 'by': 'black'}, ['square:f1'], kind_override='square',
          reason='지나갈 f1이 공격받으므로 킹사이드 캐슬링은 불가능해요.'),
    scene('castle-right-lost', 'castling', '돌아와도 권리는 복구되지 않아요', 'K',
          '이 예시의 킹은 움직였다 돌아와서 캐슬링 권리가 없어요.',
          '캐슬링 대신 킹을 안전한 주변 한 칸으로 옮겨보세요.', position('e1:K h1:R e8:k'),
          {'type': 'king_step'}, ['e1f1'], reason='현재 배치뿐 아니라 이동 이력도 캐슬링 가능 여부에 영향을 줘요.'),
    ep_scene('ep-now', 'b5', position('g1:K b5:P h8:k c7:p', turn='b'), 'c7c5', 'b5c6',
             reason='내 폰은 c6에 놓이고 상대 폰은 지나온 c5에서 사라져요.'),
    scene('ep-expired', 'enpassant', '앙파상은 바로 다음 수에만', 'P',
          '두 칸 전진 직후가 아닌 이 배치에서는 앙파상 기회가 지났어요.',
          '지금 앙파상으로 잡을 수 없는 상대 폰을 눌러보세요.', position('g1:K b5:P h8:k c5:p'),
          {'type': 'no_ep_square', 'squares': ['c5']}, ['square:c5'], kind_override='square',
          reason='모양이 같아도 앙파상 권리가 없으면 빈 c6으로 잡을 수 없어요.'),
    ep_scene('ep-rank', 'b6', position('g1:K b6:P h8:k c7:p', turn='b'), 'c7c5', 'b6b7',
             predicate={'type': 'pawn_forward'},
             reason='내 폰이 더 앞줄에 있어 상대 폰의 지나온 칸을 잡을 수 없어요. 이번에는 빈 앞칸으로 전진했어요.'),
    scene('make-stalemate', 'stalemate', '공격 없이 움직일 곳이 없으면', 'Q',
          '체크 없이 둘 수 있는 수가 하나도 없으면 비겨요.',
          '비기는 규칙을 직접 확인하도록, 이번에는 일부러 스테일메이트를 만들어보세요.',
          position('f7:K e6:Q h8:k'), 'stalemate', ['e6g6'],
          reason='상대는 체크가 아니지만 합법 수가 없어요. 체크메이트와 달리 무승부예요.'),
    scene('avoid-stalemate', 'stalemate', '메이트와 구분하기', 'Q',
          '이기려면 움직일 곳만 막는 것이 아니라, 킹도 공격해야 해요.',
          '같은 배치에서 이번에는 스테일메이트 대신 체크메이트를 만들어보세요.',
          position('f7:K e6:Q h8:k'), 'mate', ['e6h6'],
          reason='상대 킹이 공격받으며 합법 수가 없으므로 이번에는 체크메이트예요.'),
    scene('value-capture', 'value', '말의 대략적인 가치', 'P',
          '대략 폰 1, 나이트·비숍 3, 룩 5, 퀸 9로 비교해요.',
          '내 폰이 합법적으로 잡을 수 있는 말 중 대략적인 가치가 더 큰 말을 잡아보세요.',
          position('h1:K d4:P g8:k c5:q e5:n'), {'type': 'capture', 'max_value': True}, ['d4c5'],
          reason='가치는 승리 점수가 아니라 비교 기준이에요. 비싼 말이라도 내 킹을 위험하게 하며 잡는 수는 둘 수 없어요.'),
    scene('value-safety', 'value', '숫자보다 먼저 안전', 'Q',
          '상대 비숍 하나를 잡고 내 퀸을 잃으면 단순한 가치 비교로도 손해일 수 있어요.',
          '내 퀸이 바로 되잡히지 않는 잡기 중 가치가 가장 큰 상대 말을 골라보세요.',
          position('g1:K d3:Q g8:k d8:r d6:b f5:n'), {'type': 'capture', 'safe': True, 'max_value': True}, ['d3f5'],
          reason='즉시 되잡히는 선택을 피하고 나이트를 잡았어요. 이것은 짧은 교환 확인이며 엔진의 최선수 평가가 아니에요.'),
    scene('check-plan', 'check2', '두 번의 내 수를 연결하기', 'R',
          '당장 체크하지 않고 먼저 자리를 옮긴 뒤, 상대의 예시 응수를 보고 체크할 수도 있어요.',
          '첫 수에 체크 없이 준비한 뒤, 상대 응수 후 두 번째 내 수로 체크해보세요.',
          position('a1:K b2:R h8:k'), {'type': 'check_plan'}, ['b2b5', 'b5g5'],
          reply={'preferred': ['h8g8'], 'fallback': 'first_legal_move_uci_order', 'label': '합법적인 교육 예시 응수 · 상대 최선 방어나 강제 체크를 증명하지 않습니다'},
          reason='상대의 이번 응수에 맞춰 두 번째 내 수로 체크했어요. 다른 응수에도 항상 성립한다는 뜻은 아니에요.'),
]

# Additional piece objectives absent from the first movement playgrounds.
RULE_UNITS.extend([
    scene('two-rooks-left', 'rook', '두 룩 중 골라 움직이기', 'R',
          '같은 종류의 말도 놓인 자리에 따라 한 번에 갈 수 있는 칸이 달라요.',
          '두 룩 중 알맞은 룩으로 표시된 a5 칸에 도착해보세요.',
          position('e1:K b2:R h5:R e8:k'), {'type': 'arrive', 'piece': 'R', 'target': 'a5'}, ['h5a5'],
          target_squares=['a5'], reason='가로줄이 같은 룩을 골랐어요.'),
    scene('two-rooks-right', 'rook', '다른 룩도 활용하기', 'R',
          '목표가 바뀌면 더 가까운 방향의 룩을 고를 수 있어요.',
          '이번에는 알맞은 룩으로 표시된 b6 칸에 도착해보세요.',
          position('e1:K b2:R h5:R e8:k'), {'type': 'arrive', 'piece': 'R', 'target': 'b6'}, ['b2b6'],
          target_squares=['b6'], reason='세로줄이 같은 다른 룩을 골랐어요.'),
    scene('two-bishops-light', 'bishop', '두 비숍의 다른 길', 'B',
          '비숍은 출발한 칸과 같은 색 칸만 다닐 수 있어요.',
          '표시된 g5 칸에 도착할 수 있는 비숍을 골라 옮겨보세요.',
          position('g1:K c1:B f1:B h8:k'), {'type': 'arrive', 'piece': 'B', 'target': 'g5'}, ['c1g5'],
          target_squares=['g5'], reason='이 칸은 c1에서 출발한 비숍의 색이에요.'),
    scene('two-bishops-dark', 'bishop', '다른 색 칸은 다른 비숍', 'B',
          '반대 색 칸으로 가려면 다른 색에서 출발한 비숍이 필요해요.',
          '이번에는 표시된 b5 칸으로 갈 비숍을 골라 옮겨보세요.',
          position('g1:K c1:B f1:B h8:k'), {'type': 'arrive', 'piece': 'B', 'target': 'b5'}, ['f1b5'],
          target_squares=['b5'], reason='f1에서 출발한 비숍으로 다른 색 칸에 도착했어요.'),
    scene('pawn-choice', 'pawn', '여러 폰 중 고르기', 'P',
          '폰마다 자기 앞칸으로 움직여요.',
          '표시된 e4 칸으로 갈 수 있는 폰을 골라 옮겨보세요.',
          position('g1:K b3:P e3:P h3:P g8:k'), {'type': 'arrive', 'piece': 'P', 'target': 'e4'}, ['e3e4'],
          target_squares=['e4'], reason='그 칸 바로 뒤에 있는 폰을 골랐어요.'),
    scene('pawn-two', 'pawn', '시작 줄에서 두 칸', 'P',
          '시작 줄의 폰은 앞 두 칸이 모두 비었으면 두 칸도 갈 수 있어요.',
          '표시된 d4 칸까지 폰을 두 칸 옮겨보세요.',
          position('g1:K d2:P g8:k'), {'type': 'arrive', 'piece': 'P', 'target': 'd4'}, ['d2d4'],
          target_squares=['d4'], reason='시작 줄에서만 가능한 두 칸 전진이에요.'),
    scene('pawn-black', 'pawn', '어두운색 폰의 앞쪽', 'p',
          '어두운색 폰은 밝은색 폰과 반대 방향으로 전진해요.',
          '내 쪽에서 본 어두운색 폰을 표시된 f5 칸으로 옮겨보세요.',
          position('g1:K g8:k f7:p', turn='b'), {'type': 'arrive', 'piece': 'P', 'target': 'f5'}, ['f7f5'],
          target_squares=['f5'], side='black', reason='보드를 돌려 보아도 각 폰의 전진 방향은 바뀌지 않아요.'),
    scene('pawn-promotion', 'pawn', '승격하고 바뀐 말 움직이기', 'P',
          '끝줄에 도착한 폰은 퀸·룩·비숍·나이트 중 하나로 바뀌어요.',
          '폰을 승격시킨 뒤, 상대 응수를 보고 바뀐 말을 한 번 움직여보세요.',
          position('g1:K e7:P h8:k'), {'type': 'promotion_followup'}, ['e7e8q', 'e8e4'],
          reply={'preferred': ['h8h7'], 'fallback': 'first_legal_move_uci_order', 'label': '교육용 합법 응수'},
          reason='승격 이후에는 선택한 말의 움직임을 사용해요.'),
    scene('pawn-capture-promote', 'pawn', '잡으면서 승격하기', 'P',
          '상대 말을 잡으며 끝줄에 도착해도 승격해요.',
          '상대 룩을 잡고 원하는 말로 승격해보세요.',
          position('g1:K e7:P h8:k d8:r'), {'type': 'promotion', 'capture': True}, ['e7d8n'],
          reason='잡기와 승격이 한 수에서 함께 일어났어요.')
])

RULE_UNITS.extend([
    scene('escape-knight', 'outOfCheck', '나이트 체크는 길을 막지 못해요', 'K',
          '뛰어오는 나이트의 체크는 중간을 막을 수 없어요.',
          '킹을 피하거나 체크하는 나이트를 잡아 체크를 해결해보세요.',
          position('e1:K d1:Q a8:k f3:n'), {'type': 'escape', 'method': 'any'}, ['d1f3'],
          reason='이번에는 체크하는 나이트를 없애거나 킹을 피해야 해요.'),
    scene('castle-prepare', 'castling', '길을 비운 다음 캐슬링', 'N',
          '내 말이 길을 막는다면 먼저 옮기고 나중 차례에 캐슬링해요.',
          '나이트를 옮겨 길을 비운 뒤, 상대 응수 후 킹사이드 캐슬링을 해보세요.',
          position('e1:K h1:R g1:N e8:k', rights='K'), {'type': 'castle_plan'}, ['g1f3', 'e1g1'],
          reply={'preferred': ['e8d7'], 'fallback': 'first_legal_move_uci_order', 'label': '교육용 합법 응수'},
          reason='길을 비우는 수와 캐슬링은 서로 다른 내 차례에 이루어져요.'),
    scene('value-legal-first', 'value', '가치보다 먼저 내 킹', 'P',
          '아무리 큰 말을 잡더라도 내 킹이 공격받게 되는 수는 둘 수 없어요.',
          '내 킹을 안전하게 둔 채 폰으로 상대 말을 잡아보세요.',
          position('g1:K d4:P g8:k c5:q e5:n'), {'type': 'capture'}, ['d4c5'],
          reason='나이트를 잡으면 퀸의 공격길이 킹까지 열려요. 퀸을 잡는 수는 합법이에요.')
])

_EP_CHAIN_BEFORE = position('g1:K b5:P d5:P f5:P h8:k a7:p c7:p e7:p', turn='b')
_EP_CHAIN_BOARD = chess.Board(_EP_CHAIN_BEFORE)
_EP_CHAIN_BOARD.push_uci('a7a5')
RULE_UNITS.extend([
    scene('shield-piece', 'protection', '공격길을 막아 지키기', 'P',
          '공격받는 말 대신 다른 말을 그 공격길에 놓아 지킬 수도 있어요.',
          '룩은 그대로 두고 폰으로 상대 비숍의 공격길을 막아보세요.',
          position('g1:K a1:R d2:P h8:k g7:b'), {'type': 'shield', 'target': 'a1'}, ['d2d4'],
          reason='폰이 비숍과 룩 사이를 막아 룩이 바로 잡히지 않아요.'),
    scene('setup-first-turn', 'setup', '밝은색 말부터 시작해요', 'P',
          '처음 배치가 끝나면 밝은색(백)이 먼저 두고 번갈아 한 수씩 둬요.',
          '밝은색 말로 대국의 첫 수를 직접 골라 두어보세요.', chess.STARTING_FEN,
          'legal_move', ['d2d4'], reason='이제 어두운색 차례예요. 폰이나 나이트로 시작하는 여러 합법 수가 있어요.'),
    scene('ep-repeat', 'enpassant', '새 기회마다 확인하기', 'P',
          '앙파상은 매번 바로 직전에 두 칸 온 폰에 대해서만 가능해요.',
          '상대의 예시 응수마다 새로 생긴 앙파상 기회를 찾아 세 번 잡아보세요.',
          _EP_CHAIN_BOARD.fen(en_passant='fen'), {'type': 'ep_chain', 'required': 3},
          ['b5a6', 'd5c6', 'f5e6'],
          prelude={'before_fen': _EP_CHAIN_BEFORE, 'moves': ['a7a5'], 'after_fen': _EP_CHAIN_BOARD.fen(en_passant='fen'), 'label': '교육용 상대 두 칸 전진'},
          replies=['c7c5', 'e7e5'], reason='새로운 상대 두 칸 전진마다 즉시 잡기를 확인했어요.')
])

# Explicitly separate the forbidden castling conditions and blocked-pawn rule.
# Each uses an existing action/predicate; no new client grading contract.
RULE_UNITS.extend([
    scene('castle-in-check', 'castling', '체크 중에는 캐슬링할 수 없어요', 'K',
          '지금 킹이 체크라면 캐슬링으로 피할 수 없어요.',
          '상대 룩에게 공격받고 있는 내 킹의 칸을 눌러보세요.',
          position('e1:K h1:R a8:k e8:r', rights='K'),
          {'type': 'attacked_squares', 'squares': ['e1'], 'by': 'black'}, ['square:e1'], kind_override='square',
          reason='출발 칸의 킹이 이미 체크라서 캐슬링할 수 없어요. 먼저 다른 합법 수로 체크를 해결해야 해요.'),
    scene('castle-destination-attacked', 'castling', '도착 칸도 안전해야 해요', 'K',
          '지나갈 길이 안전해도 도착할 칸이 공격받으면 캐슬링할 수 없어요.',
          '킹사이드 캐슬링의 도착 칸 중 상대 룩이 공격하는 칸을 눌러보세요.',
          position('e1:K h1:R a8:k g8:r', rights='K'),
          {'type': 'attacked_squares', 'squares': ['g1'], 'by': 'black'}, ['square:g1'], kind_override='square',
          reason='출발 e1과 통과 f1은 안전하지만 도착 g1이 공격받으므로 킹사이드 캐슬링은 불가능해요.'),
    scene('castle-rook-right-lost', 'castling', '룩의 이동 이력도 중요해요', 'K',
          '이 예시의 킹사이드 룩은 움직였다 돌아왔으므로 그쪽 캐슬링 권리가 없어요.',
          '움직인 적 없는 반대쪽 룩과 가능한 캐슬링을 해보세요.',
          position('e1:K a1:R h1:R d2:P e2:P f2:P e8:k d7:p e7:p f7:p', rights='Q'),
          {'type': 'castle', 'side': 'queen'}, ['e1c1'],
          reason='킹이 움직인 적 없고 퀸사이드 룩의 권리는 남아 있어 퀸사이드 캐슬링은 가능해요.'),
    scene('pawn-blocked-front', 'pawn', '앞에 있는 말은 잡지 못해요', 'P',
          '폰 앞에 말이 있으면 전진할 수 없고, 잡기는 비스듬한 앞칸에서만 해요.',
          '막힌 앞칸 대신 비스듬한 앞칸의 상대 폰을 잡아보세요.',
          position('g1:K d4:P g8:k d5:p e5:p'), 'capture', ['d4e5'],
          reason='바로 앞 d5의 폰은 잡지 못하고, e5의 폰만 비스듬히 잡을 수 있어요.')
])

for _unit in RULE_UNITS:
    _unit['kind'] = _unit.pop('kind_override', _unit['kind'])
# The third en-passant scene intentionally differs: correct rank is part of the rule.
_rank = next(u for u in RULE_UNITS if u['id'] == 'rules-ep-rank')
_rank.update(rule='앙파상은 내 폰이 상대 폰의 두 칸 전진 도착 줄 옆에 있을 때만 가능해요.',
             goal='상대 이동을 본 뒤, 이번에는 특별한 잡기 대신 내 폰을 빈 앞칸으로 옮겨보세요.')
BY_ID = {u['id']: u for u in RULE_UNITS}


def _capturable(board, square):
    """board.turn is the opponent; count actual legal captures, not pseudo-attacks."""
    return any(m.to_square == square and board.is_capture(m) for m in board.legal_moves)


def _protected(board, square):
    target = board.piece_at(square)
    if not target or target.color == board.turn: return False
    captures = [m for m in board.legal_moves if m.to_square == square and board.is_capture(m)]
    if not captures: return False  # This scene teaches a real recapture relation.
    for attack in captures:
        reply = board.copy(); reply.push(attack)
        if not any(m.to_square == square and reply.is_capture(m) for m in reply.legal_moves): return False
    return True


def accepts(unit, board, move):
    """Pure one-action goal predicate; ordinary chess legality is always first."""
    if move not in board.legal_moves: return False
    predicate = unit['predicate']; kind = predicate['type']; after = board.copy(); after.push(move)
    if kind == 'legal_move': return True
    if kind == 'shield':
        target = chess.parse_square(predicate['target'])
        return move.from_square != target and bool(board.attackers(not board.turn, target)) and not board.is_capture(move) and not after.is_attacked_by(after.turn, target)
    if kind == 'arrive': return move.to_square == chess.parse_square(predicate['target']) and board.piece_at(move.from_square).symbol().upper() == predicate['piece']
    if kind == 'promotion': return bool(move.promotion) and (not predicate.get('capture') or board.is_capture(move))
    if kind == 'capture':
        if not board.is_capture(move): return False
        if predicate.get('safe') and _capturable(after, move.to_square): return False
        if predicate.get('max_value'):
            def value(m):
                piece = board.piece_at(m.to_square)
                return 1 if board.is_en_passant(m) else VALUES.get(piece.piece_type, 0) if piece else 0
            candidates = []
            for candidate in board.legal_moves:
                if not board.is_capture(candidate): continue
                position_after = board.copy(); position_after.push(candidate)
                if predicate.get('safe') and _capturable(position_after, candidate.to_square): continue
                candidates.append(value(candidate))
            return bool(candidates) and value(move) == max(candidates)
        return True
    if kind == 'safe_move': return chess.square_name(move.from_square) == predicate['source'] and not _capturable(after, move.to_square)
    if kind == 'protect': return move.from_square != chess.parse_square(predicate['target']) and _protected(after, chess.parse_square(predicate['target']))
    if kind == 'check': return after.is_check()
    if kind == 'mate': return after.is_checkmate()
    if kind == 'stalemate': return after.is_stalemate()
    if kind == 'escape':
        if not board.is_check(): return False
        method = predicate['method']; piece = board.piece_at(move.from_square)
        if method == 'any': return True
        if method == 'king': return piece.piece_type == chess.KING
        if method == 'capture': return move.to_square in board.checkers() and board.is_capture(move)
        return piece.piece_type != chess.KING and not board.is_capture(move)
    if kind == 'castle': return board.is_castling(move) and (board.is_kingside_castling(move) if predicate['side'] == 'king' else board.is_queenside_castling(move))
    if kind == 'king_step': return board.piece_type_at(move.from_square) == chess.KING and not board.is_castling(move)
    if kind == 'en_passant': return board.is_en_passant(move)
    if kind == 'pawn_forward': return board.piece_type_at(move.from_square) == chess.PAWN and not board.is_capture(move)
    raise ValueError('지원하지 않는 학습 판정입니다.')


def choose_reply(unit, board):
    for value in unit.get('reply', {}).get('preferred', []):
        move = chess.Move.from_uci(value)
        if move in board.legal_moves: return move
    candidates = sorted(board.legal_moves, key=lambda m: m.uci())
    return candidates[0] if candidates else None


def replay_rule(unit, actions):
    if not isinstance(actions, list) or len(actions) > 128: raise ValueError('연습 행동 수를 확인해 주세요.')
    board = chess.Board(unit['fen']); done = False; failed = False; feedback = ''
    played = []; selected = []; own_moves = 0; opponent_played = False
    for value in actions:
        if done or failed: raise ValueError('끝난 확인에는 행동을 더할 수 없어요. 새 확인을 시작해 주세요.')
        if not isinstance(value, str) or len(value) > 12: raise ValueError('행동 형식을 확인해 주세요.')
        predicate = unit['predicate']; kind = unit['kind']
        if kind == 'square':
            if not value.startswith('square:'): raise ValueError('보드의 칸을 선택해 주세요.')
            square = value[7:]; chess.parse_square(square)
            correct = square in predicate['squares']
            if predicate['type'] == 'attacked_squares': correct = correct and board.is_attacked_by(predicate['by'] == 'white', chess.parse_square(square))
            if predicate['type'] == 'no_ep_square': correct = correct and not board.has_legal_en_passant()
            done = correct; failed = not correct; selected.append(square)
        elif kind == 'place':
            parts = value.split(':')
            if len(parts) != 3 or parts[0] != 'place' or parts[1] not in 'RNBQKP' or len(parts[1]) != 1: raise ValueError('배치할 말과 칸을 확인해 주세요.')
            _, symbol, square = parts; sq = chess.parse_square(square)
            correct = predicate['pieces'].get(square) == symbol and board.piece_at(sq) is None
            if correct:
                board.set_piece_at(sq, chess.Piece.from_symbol(symbol)); selected.append(square)
                done = all(board.piece_at(chess.parse_square(s)) == chess.Piece.from_symbol(p) for s, p in predicate['pieces'].items())
                if done: board.set_castling_fen('KQkq')
            else: failed = True
        else:
            try: move = chess.Move.from_uci(value)
            except ValueError: raise ValueError('출발 칸과 도착 칸을 확인해 주세요.')
            if move not in board.legal_moves: raise ValueError('이 이동은 체스 규칙상 둘 수 없어요. 킹의 안전과 막힌 길을 확인해 주세요.')
            if predicate['type'] == 'ep_chain':
                if not board.is_en_passant(move):
                    failed = True; board.push(move); played.append(value)
                else:
                    board.push(move); played.append(value); own_moves += 1
                    done = own_moves == predicate['required']
                    if not done:
                        reply = chess.Move.from_uci(unit['replies'][own_moves - 1])
                        if reply not in board.legal_moves: raise ValueError('예시 응수가 현재 배치와 맞지 않아요.')
                        board.push(reply); played.append(reply.uci()); opponent_played = True
                        feedback = '상대 폰이 새로 두 칸 왔어요. 바로 다음 앙파상을 찾아보세요.'
            elif predicate['type'] in ('check_plan', 'promotion_followup', 'castle_plan'):
                after = board.copy(); after.push(move); own_moves += 1
                if own_moves == 1:
                    # Require a rook preparation, followed by an actual legal opponent move.
                    if (predicate['type'] == 'check_plan' and (board.piece_type_at(move.from_square) != chess.ROOK or after.is_check())) or (predicate['type'] == 'promotion_followup' and not move.promotion) or (predicate['type'] == 'castle_plan' and board.piece_type_at(move.from_square) != chess.KNIGHT):
                        failed = True; board = after; played.append(value)
                    else:
                        reply = choose_reply(unit, after)
                        if reply is None:
                            failed = True; board = after; played.append(value)
                        else:
                            after.push(reply); played.extend([value, reply.uci()]); board = after; opponent_played = True
                            # Do not strand the learner in a second step with no checking move.
                            if predicate['type'] == 'check_plan' and not any(after.gives_check(m) for m in after.legal_moves): failed = True
                            if predicate['type'] == 'castle_plan' and not any(after.is_kingside_castling(m) for m in after.legal_moves): failed = True
                            feedback = '상대가 예시 수로 응수했어요. 이제 한 수로 체크해보세요.' if predicate['type'] == 'check_plan' else '상대가 응수했어요. 이제 킹사이드 캐슬링을 해보세요.' if predicate['type'] == 'castle_plan' else '상대가 응수했어요. 이제 승격으로 바뀐 말을 움직여보세요.'
                else:
                    done = after.is_check() if predicate['type'] == 'check_plan' else board.is_kingside_castling(move) if predicate['type'] == 'castle_plan' else move.from_square == chess.parse_square(actions[0][2:4]); failed = not done; board = after; played.append(value)
            else:
                done = accepts(unit, board, move); failed = not done
                board.push(move); played.append(value); own_moves += 1
        if done: feedback = unit.get('reason', '이번 규칙을 직접 확인했어요.')
        elif failed: feedback = '합법 여부와 이번 목표는 달라요. ' + unit['rule'] + ' 원래 배치에서 다시 확인할 수 있어요.'
    place_symbol = None
    if unit['kind'] == 'place' and not done and not failed:
        missing = [p for s, p in unit['predicate']['pieces'].items() if board.piece_at(chess.parse_square(s)) != chess.Piece.from_symbol(p)]
        place_symbol = next((p for p in unit.get('placement_order', []) if p in missing), None)
    return dict(fen=board.fen(en_passant='fen'), source=None, remaining=[], visited=selected,
                done=done, failed=failed, legal=[m.uci() for m in board.legal_moves] if unit['kind'] == 'move' and not done and not failed else [],
                moves=list(actions), move_count=len(actions), played=played, feedback=feedback,
                place_symbol=place_symbol, opponent_example=unit.get('reply', {}).get('label') if opponent_played else None)


def validate_content():
    assert len(BY_ID) == len(RULE_UNITS)
    assert (set(SOURCES) - {'queen', 'king', 'knight'}).issubset({u['stage'] for u in RULE_UNITS})
    for unit in RULE_UNITS:
        board = chess.Board(unit['fen'])
        if unit['kind'] != 'place': assert board.is_valid(), (unit['id'], board.status())
        if unit.get('prelude'):
            prelude = unit['prelude']; before = chess.Board(prelude['before_fen'])
            assert before.is_valid(), unit['id']
            for value in prelude['moves']:
                move = chess.Move.from_uci(value); assert move in before.legal_moves, unit['id']; before.push(move)
            assert before.fen(en_passant='fen') == unit['fen'], unit['id']
        result = replay_rule(unit, unit['example_actions'])
        assert result['done'] and not result['failed'], (unit['id'], result)
        if unit['kind'] == 'place': assert chess.Board(result['fen']).board_fen() == chess.Board().board_fen(), unit['id']
    return {'units': len(RULE_UNITS), 'stages': len(SOURCES)}
