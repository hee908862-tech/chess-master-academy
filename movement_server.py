"""Versioned movement-only playground; append-only checkpoints, no chess score writes."""
import copy
import secrets
from datetime import datetime,timezone
from typing import Literal, Annotated
from fastapi import Header,HTTPException
from pydantic import BaseModel,Field
from basic_clips import clip, teaches_relationships, threats
import chess
from movement_content import UNITS,BY_ID,VERSION,POLICY,MAX_MOVES,public_unit,replay
KEY='movement_v1'


def summary(state):
    saved=state.get(KEY,{})
    old=state.get('foundation_v1',{})
    active=saved.get('active');row=saved.get('units',{}).get(active,{})
    ever_done={k for k,v in saved.get('units',{}).items() if v.get('done')} | {v['unit_id'] for v in saved.get('history',[]) if v.get('done')}
    started=bool(saved.get('units'));old_started=bool(old.get('courses'))
    return dict(started=started,completed=len(ever_done),total=len(UNITS),
                active=active,name=BY_ID.get(active,{}).get('name'),done=bool(row.get('done')),
                preferred=(not old_started and not started) or bool(started and saved.get('updated_at','')>old.get('updated_at','')))


class Start(BaseModel):
    action:Literal['start','next','restart']='start'
    relationship_flow:bool=False
    retry_practice:bool=False
    unit_id:str|None=None
    revision:int=Field(ge=0)
    request_id:str=Field(min_length=8,max_length=80)


class Demo(BaseModel):
    unit_id:str
    session_id:str
    revision:int=Field(ge=0)


class Lesson(BaseModel):
    session_id:str
    revision:int=Field(ge=0)
    action:Literal['guided','step','independent','skip']
    move:str=Field(default='',max_length=24)


class Save(BaseModel):
    unit_id:str
    session_id:str=Field(max_length=80)
    revision:int=Field(ge=0)
    version:str
    policy:str
    moves:list[Annotated[str,Field(min_length=4,max_length=24,pattern=r'^(?:[a-h][1-8][a-h][1-8][qrbn]?|square:[a-h][1-8]|place:[KQRBNPkqrbnp]:[a-h][1-8])$')]]=Field(max_length=MAX_MOVES)
    mistakes:int=Field(default=0,ge=0,le=10000)
    helped:bool=False


def attach_movement(app,ns):
    def payload(state):
        saved=state.get(KEY,{});units=saved.get('units',{});active=saved.get('active');row=units.get(active)
        historical={v['unit_id'] for v in saved.get('history',[]) if v.get('done')}
        task=None
        if row and active in BY_ID:
            u=BY_ID[active];task={**public_unit(u),**replay(u,row['moves']), 'unit_id':active,'session_id':row['session_id'],'mistakes':row.get('mistakes',0),'helped':row.get('helped',False),'result':row.get('result'),'run':row.get('run',0),'relationship_available':teaches_relationships(u)}
        if task and row.get('teaching'):
            teaching = copy.deepcopy(row['teaching'])
            if teaching['phase'] == 'guided':
                teaching['guide_state'] = replay(u, teaching['guide_moves'])
                index = len(teaching['guide_moves'])
                teaching['next_action'] = u['example_actions'][index] if index < len(u['example_actions']) else None
                board = chess.Board(teaching['guide_state']['fen'])
                teaching['relations'] = threats(board, board.turn if board.is_check() else chess.Board(u['fen']).turn)
                if not teaching['guide_moves'] and not teaching['relations']:
                    teaching['relations'] = clip(u)['frames'][0].get('arrows', [])
            if teaching['phase'] == 'explain':
                teaching['clip'] = clip(u)
            task['teaching'] = teaching
            task['practice_result'] = row.get('practice_result')
        recommended=next((u['id'] for u in UNITS if not units.get(u['id'],{}).get('done')),None)
        return dict(version=VERSION,policy=POLICY,revision=saved.get('revision',0),active=task,recommended=recommended,
                    units=[dict(id=u['id'],name=u['name'],short_title=u['short_title'],goal=u['goal'],stage=u['stage'],symbol=u['symbol'],rule=u['rule'],mode=u['mode'],completed_before=u['id'] in historical,started=u['id'] in units,done=bool(units.get(u['id'],{}).get('done'))) for u in UNITS],summary=summary(state),
                    scope='기초 직접 연습 · 이동판은 같은 말을 연속해서, 규칙판은 표시된 차례와 목표에 맞춰 둡니다. 진단 점수와 별도입니다.')

    @app.get('/api/movement')
    def read(authorization:str|None=Header(default=None)):
        return payload(ns['get_state'](ns['auth'](authorization)))

    @app.post('/api/movement/start')
    def start(body:Start,authorization:str|None=Header(default=None)):
        code=ns['auth'](authorization);state=ns['get_state'](code);saved=copy.deepcopy(state.get(KEY,{'revision':0,'units':{}}))
        if saved.get('last_request')==body.request_id:return payload(state)
        if saved['revision']!=body.revision:raise HTTPException(409,'다른 화면에서 연습이 바뀌었어요. 저장 위치를 확인해 주세요.')
        current=saved['units'].get(saved.get('active'))
        if body.action=='next':
            if not current or not current.get('done'):raise HTTPException(409,'현재 단위의 저장된 완료를 먼저 확인해 주세요.')
            index=next(i for i,u in enumerate(UNITS) if u['id']==saved['active'])
            if index+1>=len(UNITS):return payload(state)
            unit_id=UNITS[index+1]['id']
        else:unit_id=body.unit_id or saved.get('active') or next((u['id'] for u in UNITS if not saved['units'].get(u['id'],{}).get('done')),UNITS[0]['id'])
        if unit_id not in BY_ID:raise HTTPException(404,'이동 연습을 찾지 못했어요.')
        prior=saved['units'].get(unit_id)
        if body.action=='restart' and (saved.get('active')!=unit_id or not prior):raise HTTPException(409,'다시 시작할 현재 연습을 확인해 주세요.')
        if body.retry_practice and (body.action!='restart' or not prior or prior.get('teaching',{}).get('phase','independent')!='independent'):
            raise HTTPException(409,'현재 직접 실습만 다시 시작할 수 있어요.')
        if not prior or body.action=='restart':
            if prior:saved.setdefault('history',[]).append(dict(prior,unit_id=unit_id))
            saved['units'][unit_id]={'version':VERSION,'policy':POLICY,'unit_policy':BY_ID[unit_id].get('policy','same-piece-movement-v1'),'session_id':secrets.token_urlsafe(18),'moves':[],'done':False,'mistakes':0,'helped':unit_id in saved.get('demo_views',[]),'run':prior.get('run',0)+1 if prior else 0}
            if body.relationship_flow and teaches_relationships(BY_ID[unit_id]):
                # Existing sessions are not migrated or reset by a GET or normal resume.
                saved['units'][unit_id]['teaching'] = dict(phase='independent' if body.retry_practice else 'explain', guide_moves=[], guide_done=False, skipped=False, independent_helped=False)
                if body.retry_practice and prior.get('teaching'):
                    # Retrying must not erase answer exposure or completed guidance.
                    saved['units'][unit_id]['teaching'] = copy.deepcopy(prior['teaching'])
                saved['units'][unit_id]['helped'] = True
        saved['active']=unit_id;saved['last_request']=body.request_id;saved['revision']+=1;saved['updated_at']=datetime.now(timezone.utc).isoformat();state[KEY]=saved;ns['save_state'](code,state)
        return payload(state)

    @app.post('/api/movement/demo')
    def demo(body:Demo,authorization:str|None=Header(default=None)):
        from basic_clips import clip
        code=ns['auth'](authorization);state=ns['get_state'](code)
        saved=copy.deepcopy(state.get(KEY,{}))
        current=saved.get('units',{}).get(saved.get('active'))
        if not current or current['session_id']!=body.session_id or saved['revision']!=body.revision:
            raise HTTPException(409,'현재 연습의 저장 위치를 다시 확인해 주세요.')
        index=next(i for i,u in enumerate(UNITS) if u['id']==saved['active'])
        allowed=[saved['active']] + ([UNITS[index-1]['id']] if index else [])
        target=BY_ID.get(body.unit_id)
        if body.unit_id not in allowed or not target or target['mode']!='rule':
            raise HTTPException(400,'현재 또는 직전 규칙 연습의 시연을 선택해 주세요.')
        demonstration=clip(target)
        views=saved.setdefault('demo_views',[])
        if body.unit_id not in views:views.append(body.unit_id)
        row=saved['units'].get(body.unit_id)
        if row:
            row['helped']=True
            if row.get('teaching',{}).get('phase') == 'independent' and not row.get('done'):
                row['teaching']['independent_helped'] = True
        saved['revision']+=1
        state[KEY]=saved;ns['save_state'](code,state)
        return dict(dashboard=payload(state),clip=demonstration)

    @app.post('/api/movement/lesson')
    def lesson(body:Lesson,authorization:str|None=Header(default=None)):
        code=ns['auth'](authorization);state=ns['get_state'](code)
        saved=copy.deepcopy(state.get(KEY,{}));row=saved.get('units',{}).get(saved.get('active'))
        if not row or row['session_id']!=body.session_id or saved['revision']!=body.revision:
            raise HTTPException(409,'현재 연습의 저장 위치를 확인해 주세요.')
        teaching=row.get('teaching');u=BY_ID[saved['active']]
        if not teaching or teaching['phase']=='independent':
            raise HTTPException(409,'현재 설명 또는 따라 하기 단계를 확인해 주세요.')
        if body.action=='guided':
            if teaching['phase']!='explain':raise HTTPException(409,'이미 따라 하기 중이에요.')
            teaching['phase']='guided'
        elif body.action=='step':
            index=len(teaching['guide_moves'])
            if teaching['phase']!='guided' or index>=len(u['example_actions']) or body.move!=u['example_actions'][index]:
                raise HTTPException(400,'따라 하기 화살표의 수를 확인해 주세요.')
            actions=teaching['guide_moves']+[body.move]
            result=replay(u,actions)
            teaching['guide_moves']=actions;teaching['guide_done']=result['done']
        else:
            if body.action=='independent' and not teaching['guide_done']:
                raise HTTPException(409,'따라 하기를 마치거나 건너뛰기를 선택해 주세요.')
            teaching['phase']='independent';teaching['skipped']=body.action=='skip'
        saved['revision']+=1;state[KEY]=saved;ns['save_state'](code,state)
        return payload(state)

    @app.post('/api/movement/save')
    def save(body:Save,authorization:str|None=Header(default=None)):
        code=ns['auth'](authorization);state=ns['get_state'](code);saved=copy.deepcopy(state.get(KEY,{}));row=saved.get('units',{}).get(body.unit_id)
        if body.version!=VERSION or body.policy!=POLICY:raise HTTPException(409,'연습 규칙 버전이 달라요. 저장 위치를 확인해 주세요.')
        if not row or saved.get('active')!=body.unit_id or row['session_id']!=body.session_id:raise HTTPException(409,'현재 연습 또는 계정이 달라요. 기존 진행은 보존했어요.')
        if row.get('teaching',{}).get('phase') in ('explain','guided'):
            raise HTTPException(409,'설명과 따라 하기는 직접 연습 기록과 별도예요. 이전 화면이면 페이지를 새로고침해 주세요.')
        old=row['moves']
        if body.moves==old and body.mistakes<=row.get('mistakes',0) and (not body.helped or row.get('helped')):return payload(state)
        if saved['revision']!=body.revision:raise HTTPException(409,'다른 화면의 진행과 충돌했어요. 자동으로 덮어쓰지 않아요.')
        if body.moves[:len(old)]!=old:raise HTTPException(409,'저장된 이동을 바꾸거나 지울 수 없어요.')
        try:result=replay(BY_ID[body.unit_id],body.moves)
        except (ValueError,IndexError,TypeError):raise HTTPException(400,'이동 규칙과 저장된 순서를 확인해 주세요.')
        row['moves']=body.moves;row['mistakes']=max(row.get('mistakes',0),body.mistakes);row['helped']=row.get('helped',False) or body.helped
        row['done']=result['done'];row['failed']=result.get('failed',False)
        if row['done']:
            if row.get('teaching'):
                row['practice_result']='assisted_application' if row['teaching']['independent_helped'] else 'independent_application_after_intro'
            row['result']='rule_applied' if BY_ID[body.unit_id]['mode']=='rule' else 'guided' if BY_ID[body.unit_id]['mode']=='collect' else 'first_application' if not row['mistakes'] and not row['helped'] and row['run']==0 else 'practice_application'
        saved['revision']+=1;saved['updated_at']=datetime.now(timezone.utc).isoformat();state[KEY]=saved;ns['save_state'](code,state)
        return payload(state)
