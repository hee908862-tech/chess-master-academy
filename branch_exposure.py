"""Separate, owner-scoped exploration exposure; never edits scores or game records."""
import copy
import chess
from fastapi import Header,HTTPException
from pydantic import BaseModel,Field

LIMIT=4096
FIELD='branch_exposure_v1'


class Exposure(BaseModel):
    fens:list[str]=Field(min_length=1,max_length=32)


def canonical(fen):
    if not isinstance(fen,str) or len(fen)>120 or len(fen.split())!=6:raise ValueError('full FEN required')
    board=chess.Board(fen)
    if not board.is_valid():raise ValueError('invalid board')
    return ' '.join(board.fen(en_passant='legal').split()[:4])+' 0 1'


def exposure_info(state):
    record=state.get(FIELD,{})
    if not isinstance(record,dict):return set(),True
    positions=set();unknown=bool(record.get('overflow'))
    for row in record.get('positions',[]):
        try:positions.add(' '.join(canonical(row['fen']).split()[:4]))
        except (ValueError,KeyError,TypeError):unknown=True
    return positions,unknown


def attach_branch_exposure(app,ns):
    @app.post('/api/study/exposure')
    def expose(body:Exposure,authorization:str|None=Header(default=None)):
        code=ns['auth'](authorization)
        try:fens=list(dict.fromkeys(canonical(fen) for fen in body.fens))
        except (ValueError,TypeError):raise HTTPException(400,'완전하고 합법적인 FEN 국면만 노출 기록에 저장할 수 있습니다.')
        # Preserve ProgressState's compare/merge metadata; only this top-level field changes.
        state=ns['get_state'](code)
        positions,unknown=exposure_info(state)
        rows=copy.deepcopy(state.get(FIELD,{}).get('positions',[])) if isinstance(state.get(FIELD,{}),dict) else []
        added=0
        for fen in fens:
            key=' '.join(fen.split()[:4])
            if key in positions:continue
            if len(positions)>=LIMIT:unknown=True;continue
            rows.append({'fen':fen});positions.add(key);added+=1
        record={'version':1,'positions':rows,'overflow':unknown}
        if state.get(FIELD)!=record:
            state[FIELD]=record
            ns['save_state'](code,state)
        return {'status':'recorded','added':added,'recorded':len(positions),'overflow':unknown,
                'note':'분기에서 본 국면을 별도 보존했습니다. 기존 채점·기보는 바뀌지 않습니다.' if not unknown else '노출 기록 한도로 이후 독립 관찰 여부를 보류합니다. 기존 점수를 감점하지 않습니다.'}
