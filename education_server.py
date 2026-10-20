"""Bounded educational observations; no diagnostic credit or mastery claims."""
import copy
import json
import secrets
from typing import Literal
import chess
from fastapi import Header, HTTPException
from pydantic import BaseModel, Field
from education_content import LESSONS, BY_ID, VERSION
from repertoire_server import archive, records, can_start, reserve_attempt, now

KEY='education_paths_v1'
MAX_BYTES=1048576
MAX_EVENTS=256
class Action(BaseModel):
    action:Literal['start','answer','hint','next','finish']
    revision:int=Field(ge=0)
    attempt_id:str=Field(default='',max_length=40)
    lesson_id:str=Field(default='',max_length=80)
    mode:Literal['learn','review']='learn'
    answer:str=Field(default='',max_length=40)

def prior_context(step):
    """Saved last move is question context, never a suggested answer."""
    if not step.get('prior_fen') or not step.get('prior_move'):return None
    try:
        b=chess.Board(step['prior_fen']);m=chess.Move.from_uci(step['prior_move'])
        if not b.is_valid() or m not in b.legal_moves:return None
        san=b.san(m);b.push(m)
        if b.fen()!=step['fen']:return None
        return dict(before_fen=step['prior_fen'],move=m.uci(),san=san,after_fen=b.fen())
    except ValueError:return None

def payload(s):
    r=copy.deepcopy(s.get('active'))
    if r:
        step=r.pop('snapshot')['steps'][r['index']]
        reveal=r['mode']=='learn' or r['hinted'] or r['answered']
        r['step']={k:step[k] for k in ('id','kind','choices') if k in step}
        r['step']['prior']=prior_context(step)
        r['step']['prompt']=step['prompt'] if reveal else step['review_prompt']
        r['step']['reason']=step['reason'] if r['answered'] or r['hinted'] else None
        r['step']['examples']=step['answers'] if reveal and step['kind']=='move' else []
        b=chess.Board(r['fen']);r['legal']=[u.uci() for u in b.legal_moves] if r['phase']=='playing' and not r['answered'] else []
        r['outdated']=r['version']!=VERSION
        if r['outdated']:r['legal']=[]
    return dict(revision=s.get('revision',0),active=r,can_start=can_start(s),metrics=s.get('metrics',{}),
        history=[{k:x.get(k) for k in ('id','title','mode','phase','index','hints','misses','at')} for x in records(s)],
        catalog=[{k:c[k] for k in ('id','group','title','intro','prerequisite')} for c in LESSONS])

def attach_education(app,ns):
    @app.get('/api/education')
    def get(authorization:str|None=Header(default=None)):
        return payload(ns['get_state'](ns['auth'](authorization)).get(KEY,{}))
    @app.get('/api/education/history/{ident}')
    def history(ident:str,authorization:str|None=Header(default=None)):
        s=ns['get_state'](ns['auth'](authorization)).get(KEY,{})
        r=next((r for r in records(s) if r['id']==ident),None)
        if not r:raise HTTPException(404,'이 계정의 기록이 없습니다.')
        return copy.deepcopy(r)
    @app.post('/api/education/action')
    def action(req:Action,authorization:str|None=Header(default=None)):
        code=ns['auth'](authorization);state=ns['get_state'](code)
        s=copy.deepcopy(state.get(KEY,dict(revision=0,history=[],metrics={})))
        if req.revision!=s['revision']:raise HTTPException(409,'다른 화면에서 기록이 바뀌었습니다. 저장 상태를 다시 확인하세요.')
        r=s.get('active')
        if req.action=='start':
            if r:raise HTTPException(409,'현재 시도를 먼저 이어가거나 결과를 보관하세요.')
            if req.lesson_id not in BY_ID:raise HTTPException(400,'등록된 교육 경로를 선택하세요.')
            reserve_attempt(s);c=copy.deepcopy(BY_ID[req.lesson_id])
            r=dict(id=secrets.token_hex(16),lesson_id=c['id'],title=c['title'],version=VERSION,snapshot=c,mode=req.mode,
                phase='playing',index=0,fen=c['steps'][0]['fen'],answered=False,hinted=False,hints=0,misses=0,events=[],at=now(),feedback='관찰하고 입력하세요.')
            s['active']=r;s['metrics'].setdefault(c['id'],dict(hints=0,misses=0,completed=0,attempts=0))['attempts']+=1
        else:
            if not r or r['id']!=req.attempt_id:raise HTTPException(409,'시도가 바뀌었습니다. 저장 상태를 확인하세요.')
            if req.action=='finish':archive(s)
            else:
                if r['version']!=VERSION:raise HTTPException(409,'콘텐츠 버전이 변경됐습니다. 기존 시도를 보관한 뒤 새 버전을 시작하세요.')
                if r['phase']!='playing':raise HTTPException(409,'완료 결과를 먼저 보관하세요.')
                step=r['snapshot']['steps'][r['index']];metric=s['metrics'][r['lesson_id']]
                if req.action=='next':
                    if not r['answered']:raise HTTPException(409,'현재 관찰을 먼저 마치세요.')
                    if r['index']==len(r['snapshot']['steps'])-1:
                        r['phase']='complete';metric['completed']+=1;r['feedback']='교육 예시를 완료했습니다. 독립 숙련도나 진단 결과가 아닙니다.'
                    else:
                        r['index']+=1;r.update(fen=r['snapshot']['steps'][r['index']]['fen'],answered=False,hinted=False,feedback='새 비교 위치입니다. 이전 착수의 연속 대국이 아닙니다.')
                else:
                    if r['answered']:raise HTTPException(409,'이미 응답한 관찰입니다. 다음 비교로 이동하세요.')
                    if len(r['events'])>=MAX_EVENTS:raise HTTPException(409,'256행 한도입니다. 현재 시도를 기록하고 마친 뒤 다시 선택하세요.')
                    accepted=req.answer in step['answers']
                    if req.action=='answer':
                        if step['kind']=='move':
                            b=chess.Board(step['fen'])
                            try:m=chess.Move.from_uci(req.answer)
                            except ValueError:raise HTTPException(400,'착수 형식을 확인하세요.')
                            if m not in b.legal_moves:raise HTTPException(400,'불법 수입니다. 위치와 기록은 바뀌지 않았습니다.')
                            if accepted:
                                b.push(m)
                                if step.get('reply'):b.push_uci(step['reply'])
                                r['fen']=b.fen()
                        elif step['kind']=='square' and req.answer not in chess.SQUARE_NAMES:raise HTTPException(400,'보드 칸을 선택하세요.')
                        elif step['kind']=='choice' and req.answer not in [c[0] for c in step['choices']]:raise HTTPException(400,'제공된 선택지를 고르세요.')
                        if accepted:r['answered']=True;r['feedback']='수업의 비교 목표를 확인했습니다. 이유를 읽고 다음 비교로 이동하세요.'
                        else:
                            r['misses']+=1;metric['misses']+=1
                            r['feedback']='이 수업에서 비교하는 응답과 다릅니다. 합법 수의 우열이나 실력 감점은 판정하지 않습니다.' if step['kind']=='move' else '관찰 또는 이유를 다시 비교하세요. 진단 점수에는 반영하지 않습니다.'
                    else:r['hinted']=True;r['hints']+=1;metric['hints']+=1;r['feedback']='설명과 예시를 공개하고 도움 사용을 저장했습니다.'
                    r['events'].append(dict(kind='hint' if req.action=='hint' else 'accepted' if accepted else 'difference',step_id=step['id'],fen=step['fen'],input=req.answer,at=now()))
        s['revision']+=1;s['write_id']=secrets.token_hex(16)
        old_size=len(json.dumps(state.get(KEY,{}),ensure_ascii=False).encode())
        limit=max(MAX_BYTES,old_size+1024) if req.action=='finish' else MAX_BYTES
        if len(json.dumps(s,ensure_ascii=False).encode())>limit:raise HTTPException(409,'교육 저장 용량 1MiB 한도입니다. 현재 기록을 보관하고 기존 결과를 조회할 수 있습니다. 자동 삭제하지 않습니다.')
        state[KEY]=s;ns['save_state'](code,state);return payload(s)
