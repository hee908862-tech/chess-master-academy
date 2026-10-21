from engine_budget import open_engine, EngineBusy
"""Version 7 API additions: server-validated hint, takeback, and review variations.
No automatic changes to existing database schemas are necessary.
"""
import chess
from assistance import event as assistance_event, record_undo as assistance_undo
import chess.engine
from pathlib import Path
from fastapi import HTTPException, Header
from pydantic import BaseModel, Field

class GameContext(BaseModel):
    session_id: str | None = None
    expected_fen: str | None = None

class ReviewVariationRequest(BaseModel):
    index:int=Field(ge=0)
    ply:int=Field(ge=0)
    move:str
    depth:int=Field(default=4,ge=1,le=12)

def attach_v7(app, ns):
    auth=ns['auth'];get_state=ns['get_state'];save_state=ns['save_state'];serialize_board=ns['serialize_board']
    ai_move=ns['ai_move'];get_engine=lambda:ns['STOCKFISH_PATH']
    def best_move(board,time_limit=.20):
        exe=get_engine()
        if exe and Path(exe).exists():
            try:
                with open_engine(exe,timeout=10) as eng:
                    return eng.play(board,chess.engine.Limit(time=time_limit)).move, 'stockfish'
            except Exception:pass
        return ai_move(board,5),'fallback'

    @app.get('/api/v7/game/hint')
    @ns['game_serialized']
    def hint(session_id:str|None=None, expected_fen:str|None=None, authorization:str|None=Header(default=None)):
        code=auth(authorization);s=get_state(code);g=s.get('active_game')
        if not g:raise HTTPException(409,'진행 중인 대국이 없습니다.')
        board=chess.Board()
        for u in g['moves']:board.push_uci(u)
        if session_id is not None and session_id!=g.get('session_id'):raise HTTPException(409,'대국이 변경되었습니다.')
        if expected_fen is not None and expected_fen!=board.fen():raise HTTPException(409,'위치가 변경되었습니다.')
        player=chess.WHITE if g.get('color','white')=='white' else chess.BLACK
        if board.is_game_over(claim_draw=True) or board.turn!=player:raise HTTPException(409,'본인 차례에만 힌트를 볼 수 있습니다.')
        if g.get('time_mode','unlimited')!='unlimited' and ns['clock_payload'](g)['white_ms' if board.turn else 'black_ms']<=0:raise HTTPException(409,'시간이 종료된 대국입니다.')
        m,source=best_move(board)
        if not m or m not in board.legal_moves:raise HTTPException(409,'추천 수를 찾을 수 없습니다.')
        assistance_event(g,board,'hint',recommended=m.uci(),source=source)
        g['hint_used']=True
        g.setdefault('hint_plies',[])
        ply=len(g['moves'])+1
        if ply not in g['hint_plies']:g['hint_plies'].append(ply)
        save_state(code,s)
        return {'move':m.uci(),'san':board.san(m),'source':source,'fen':board.fen(),'note':'최선 후보수입니다. 힌트를 사용한 대국은 평가 대국 레이팅에 반영하지 않는 편이 적절합니다.'}

    @app.post('/api/v7/game/undo')
    @ns['game_serialized']
    def undo(body:GameContext|None=None, authorization:str|None=Header(default=None)):
        code=auth(authorization);state=get_state(code);g=state.get('active_game')
        if not g or not g.get('moves'):raise HTTPException(409,'되돌릴 수 있는 착수가 없습니다.')
        color=g.get('color','white')
        side=chess.WHITE if color=='white' else chess.BLACK
        # Roll back until the human side is to play; include at least one move by the human.
        board=chess.Board()
        for u in g['moves']:board.push_uci(u)
        if body and body.session_id is not None and body.session_id!=g.get('session_id'):raise HTTPException(409,'대국이 변경되었습니다.')
        if body and body.expected_fen is not None and body.expected_fen!=board.fen():raise HTTPException(409,'위치가 변경되었습니다.')
        if not any((i%2==0)==side for i in range(len(g['moves']))):raise HTTPException(409,'되돌릴 내 착수가 없습니다.')
        if g.get('time_mode','unlimited')!='unlimited' and ns['clock_payload'](g)['white_ms' if board.turn else 'black_ms']<=0:raise HTTPException(409,'시간이 종료된 대국입니다.')
        before_moves=list(g['moves']);before_board=board.copy()
        removed=0;human_removed=False
        while g['moves']:
            mover=not board.turn
            board.pop();g['moves'].pop();removed+=1
            if mover==side:human_removed=True
            if human_removed and board.turn==side:break
        assistance_undo(g,before_moves,before_board,board)
        save_state(code,state)
        return {'session_id':g.get('session_id'),'board':serialize_board(board,color),'player_color':color,'removed_plies':removed,'undone_moves':before_moves[-removed:],'message':'마지막 선택을 되돌렸습니다.'}

    @app.post('/api/v7/review/variation')
    def variation(req:ReviewVariationRequest,authorization:str|None=Header(default=None)):
        code=auth(authorization);state=get_state(code);games=state.get('games',[])
        if req.index>=len(games):raise HTTPException(404,'대국 기록이 없습니다.')
        old=games[req.index].get('moves',[])
        if req.ply>len(old):raise HTTPException(400,'존재하지 않는 수순입니다.')
        b=chess.Board()
        for u in old[:req.ply]:
            try:b.push_uci(u)
            except ValueError:raise HTTPException(409,'대국 기록이 손상되어 있습니다.')
        try:m=chess.Move.from_uci(req.move)
        except ValueError:raise HTTPException(400,'올바른 이동 형식이 아닙니다.')
        if m not in b.legal_moves:raise HTTPException(400,'해당 포지션에서 불가능한 수입니다.')
        san=b.san(m);b.push(m)
        sequence=[{'uci':m.uci(),'san':san,'fen':b.fen(),'side':'백' if not b.turn else '흑','kind':'user'}]
        for i in range(req.depth):
            if b.is_game_over(claim_draw=True):break
            nxt,source=best_move(b,.15)
            if not nxt:break
            san=b.san(nxt);b.push(nxt)
            sequence.append({'uci':nxt.uci(),'san':san,'fen':b.fen(),'side':'백' if not b.turn else '흑','kind':'engine'})
        return {'base_ply':req.ply,'moves':sequence,'engine':source if len(sequence)>1 else 'none','note':'이 분기는 복기용 가상 수순이며 원래 대국 기록을 변경하지 않습니다.'}

    @app.get('/api/v7/assessment/status')
    def assessment_status(authorization:str|None=Header(default=None)):
        code=auth(authorization);s=get_state(code);a=s.get('assessment') or {}
        return {'complete':bool(a),'result':a,'note':'현재는 25문항 기반 예비 진단입니다. 49문항 검증형 진단은 준비 중입니다.'}
