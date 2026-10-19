"""Small, carefully sourced mate-in-three drill with board symmetries.
Original sample position and 5-ply line from Chessonomy (2026).
Distinct visual orientations are not independent puzzles.
"""
import chess
from fastapi import Header,HTTPException
from pydantic import BaseModel

BASE_FEN='8/8/8/2N5/8/2k1N3/Q3r2q/K7 w - - 0 1'
LINE=['a2c4','c3d2','c4c1','d2c1','c5b3']

def transform(sq,kind):
    f=chess.square_file(sq);r=chess.square_rank(sq)
    if kind&1:f=7-f
    if kind&2:r=7-r
    return chess.square(f,r)

def variant(kind):
    src=chess.Board(BASE_FEN);b=chess.Board(None)
    for sq,p in src.piece_map().items():b.set_piece_at(transform(sq,kind),p)
    b.turn=chess.WHITE;b.castling_rights=0
    moves=[]
    for u in LINE:
        m=chess.Move.from_uci(u);moves.append(chess.Move(transform(m.from_square,kind),transform(m.to_square,kind)).uci())
    return b,moves

def attach_mate3(app,ns):
    auth=ns['auth'];get_state=ns['get_state'];save_state=ns['save_state']
    class Reply(BaseModel):
        move:str
    def shown(s):
        b=chess.Board(s['fen'])
        for move in s['played']:b.push_uci(move)
        return {'fen':b.fen(),'legal':[m.uci() for m in b.legal_moves],
                'step':len(s['played'])//2+1,'total':3,'finished':len(s['played'])==5}
    @app.post('/api/v8/mate3/start')
    def start(authorization:str|None=Header(default=None)):
        import secrets
        code=auth(authorization);state=get_state(code)
        idx=secrets.randbelow(4);board,moves=variant(idx)
        if not board.is_valid():raise HTTPException(500,'문제 포지션 검증 실패')
        check=board.copy()
        for i,u in enumerate(moves):
            m=chess.Move.from_uci(u)
            if m not in check.legal_moves:raise HTTPException(500,'문제 수순 검증 실패')
            check.push(m)
        if not check.is_checkmate():raise HTTPException(500,'문제 수순이 메이트가 아닙니다.')
        state['mate3_v8']={'fen':board.fen(),'moves':moves,'played':[]}
        save_state(code,state)
        return {'active':True,'message':'백이 3수 안에 메이트할 수를 찾아보세요.',**shown(state['mate3_v8'])}
    @app.post('/api/v8/mate3/move')
    def play(body:Reply,authorization:str|None=Header(default=None)):
        code=auth(authorization);state=get_state(code);s=state.get('mate3_v8')
        if not s or len(s['played'])>=5:raise HTTPException(409,'진행 중인 메이트 문제가 없습니다.')
        board=chess.Board(s['fen'])
        for u in s['played']:board.push_uci(u)
        try:m=chess.Move.from_uci(body.move)
        except ValueError:raise HTTPException(400,'잘못된 이동 형식입니다.')
        if m not in board.legal_moves:raise HTTPException(400,'합법적으로 이동할 수 없습니다.')
        if body.move!=s['moves'][len(s['played'])]:
            return {'correct':False,'message':'체크를 유지하고 상대의 강제 응수를 다시 계산해 보세요.',**shown(s)}
        s['played'].append(body.move)
        opponent=None
        if len(s['played'])<5:
            opponent=s['moves'][len(s['played'])];s['played'].append(opponent)
        payload=shown(s)
        if payload['finished']:
            state.setdefault('puzzle_results',[]).append({'id':'mate3-v8','correct':True,'theme':'mateIn3'})
            state.pop('mate3_v8',None)
        save_state(code,state)
        return {'correct':True,'opponent':opponent,'message':'체크메이트!' if payload['finished'] else '정확합니다. 흑이 응수했습니다.',**payload}
