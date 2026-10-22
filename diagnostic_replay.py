"""Derive legal replay frames without writes, exposure events or grading."""
import chess


def replay_snapshot(item, played=None):
    try:
        fen = item['fen']
        if len(fen.split()) != 6:
            raise ValueError('incomplete FEN')
        board = chess.Board(fen)
        if not board.is_valid():
            raise ValueError('invalid position')
        line = item['line'] if played is None else played
        if not line:
            raise ValueError('missing line')
        frames = [{'fen': fen, 'move': None, 'san': '처음 · 정답 첫 수 이전', 'facts': position_facts(board)}]
        for uci in line:
            move = chess.Move.from_uci(uci)
            if move not in board.legal_moves:
                raise ValueError('illegal continuation')
            san = board.san(move)
            effects = move_effects(board, move)
            board.push(move)
            frames.append({'fen': board.fen(en_passant='fen'), 'move': uci, 'san': san, 'effects': effects, 'facts': position_facts(board, move.to_square)})
        return {'available': True, 'side': 'white' if chess.Board(fen).turn else 'black',
                'frames': frames, 'basis': '실제 완료 수순' if played is not None else '저장된 기준 수순'}
    except (KeyError, TypeError, ValueError, IndexError):
        return {'available': False, 'frames': [], 'reason': '저장된 시작 위치 또는 수순이 불완전해 재생하지 않습니다. 기존 채점은 유지됩니다.'}


PIECE_NAMES = {chess.PAWN:'폰', chess.KNIGHT:'나이트', chess.BISHOP:'비숍', chess.ROOK:'룩', chess.QUEEN:'퀸', chess.KING:'킹'}


def move_effects(board, move):
    """Observable effects only, not engine superiority or inferred learner intention."""
    effects=[]
    if board.is_en_passant(move): effects.append('앙파상: 도착 칸 옆의 직전 두 칸 전진한 폰을 잡습니다.')
    elif board.is_capture(move): effects.append('상대 '+PIECE_NAMES[board.piece_type_at(move.to_square)]+'을 잡습니다.')
    if board.is_castling(move): effects.append('캐슬링으로 킹과 룩을 함께 옮깁니다.')
    if move.promotion: effects.append(PIECE_NAMES[move.promotion]+'으로 승격합니다.')
    after=board.copy();after.push(move)
    if after.is_checkmate(): effects.append('상대 킹이 체크이고 합법 수가 없어 체크메이트입니다.')
    elif after.is_stalemate(): effects.append('체크가 아니지만 합법 수가 없어 스테일메이트입니다.')
    elif after.is_check(): effects.append('상대 킹을 공격하여 다음 수에 체크 대응이 필요합니다.')
    if not effects: effects.append('말을 '+chess.square_name(move.from_square)+'에서 '+chess.square_name(move.to_square)+'로 옮깁니다. 아래 표시로 새 공격·보호 관계를 확인하세요.')
    return effects


def position_facts(board, moved_square=None):
    """King safety is evaluated after vacating/capturing squares, including x-rays."""
    arrows=[]; squares={}; king=board.king(board.turn)
    for target in chess.SQUARES:
        attackers=list(board.attackers(not board.turn,target))
        if attackers: squares[chess.square_name(target)]='상대 공격: '+', '.join(chess.square_name(s)+' '+PIECE_NAMES[board.piece_type_at(s)] for s in attackers)
    if king is not None:
        for attacker in board.checkers(): arrows.append({'from':chess.square_name(attacker),'to':chess.square_name(king),'kind':'threat','label':'체크 공격'})
    escapes=[]
    if king is not None and (board.is_check() or board.is_stalemate()):
        for dest in chess.SquareSet(chess.BB_KING_ATTACKS[king]):
            name=chess.square_name(dest); occupant=board.piece_at(dest)
            legal=chess.Move(king,dest) in board.legal_moves
            after=board.copy();after.remove_piece_at(king);after.set_piece_at(dest,chess.Piece(chess.KING,board.turn))
            attackers=list(after.attackers(not board.turn,dest))
            why='안전하게 이동 가능' if legal else '내 말이 있는 칸' if occupant and occupant.color==board.turn else '이동 뒤 상대 공격: '+', '.join(chess.square_name(s)+' '+PIECE_NAMES[after.piece_type_at(s)] for s in attackers)
            squares[name]=why;escapes.append({'square':name,'legal':legal,'reason':why})
            # Capturing the checking piece must still leave the king safe.
            if occupant and occupant.color!=board.turn:
                for source in attackers: arrows.append({'from':chess.square_name(source),'to':name,'kind':'protect','label':chess.square_name(source)+'가 '+name+' 기물을 보호'})
    if moved_square is not None and board.piece_at(moved_square):
        piece=board.piece_at(moved_square)
        for target in board.attacks(moved_square):
            other=board.piece_at(target)
            if other and target!=moved_square:
                kind='protect' if other.color==piece.color else 'threat'
                arrow={'from':chess.square_name(moved_square),'to':chess.square_name(target),'kind':kind,'label':('보호' if kind=='protect' else '공격')+' 관계'}
                if not any(a['from']==arrow['from'] and a['to']==arrow['to'] for a in arrows):arrows.append(arrow)
    responses=[]
    if board.is_check():
        for move in board.legal_moves:
            captured=move.to_square+(-8 if board.turn else 8) if board.is_en_passant(move) else move.to_square
            action='체크 기물 잡기' if captured in board.checkers() else '킹 이동' if board.piece_type_at(move.from_square)==chess.KING else '공격선 막기'
            if action not in responses:responses.append(action)
    return {'fen':board.fen(en_passant='fen'),'arrows':arrows[:6],'squares':squares,'king_moves':escapes,'responses':responses,
            'ending':'checkmate' if board.is_checkmate() else 'stalemate' if board.is_stalemate() else None,
            'check_king':chess.square_name(king) if board.is_check() else None,
            'note':'합법 수와 현재 공격 관계입니다. 보호 표시만으로 안전·최선 수를 보장하지 않습니다.'}


def evaluate_frame(fen, path):
    """Explicit read-only request, bounded shared engine admission; never used to grade."""
    import chess.engine
    from pathlib import Path
    from engine_budget import open_engine, EngineBusy
    board=chess.Board(fen)
    if board.is_checkmate():return {'status':'mate','winner':'black' if board.turn else 'white','basis':'합법 수 검사 · 체크메이트'}
    if board.is_stalemate():return {'status':'draw','cp_white':0,'basis':'합법 수 검사 · 스테일메이트'}
    if not path or not Path(path).is_file():return {'status':'unavailable','reason':'분석 엔진을 사용할 수 없습니다.'}
    try:
        with open_engine(path,timeout=3) as engine:
            engine.configure({'Threads':1,'Hash':16})
            info=engine.analyse(board,chess.engine.Limit(time=.2,depth=14))
            score=info['score'].white();depth=info.get('depth',0)
            basis=f"{engine.id.get('name','Stockfish')} · 깊이 {depth} · 최대 0.2초/14깊이 · 백 기준 · 짧은 탐색, 확정 승률 아님"
            if depth<10:return {'status':'unavailable','reason':'탐색 깊이가 부족하여 우세를 표시하지 않습니다.','basis':basis}
            return {'status':'mate' if score.is_mate() else 'analysed','cp_white':score.score(),'mate_white':score.mate(),'basis':basis}
    except EngineBusy:return {'status':'busy','reason':'다른 분석 중입니다. 잠시 뒤 이 위치만 다시 분석하세요.'}
    except (chess.engine.EngineError,TimeoutError,OSError,ValueError,KeyError):
        return {'status':'failed','reason':'분석을 마치지 못했습니다. 대등으로 해석하지 않습니다. 다시 시도할 수 있습니다.'}
