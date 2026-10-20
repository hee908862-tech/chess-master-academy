"""Account-scoped, bounded repertoire recall; no diagnostic or game credit writes."""
import copy
import json
import secrets
from datetime import datetime, timezone
from typing import Literal
import chess
from fastapi import Header, HTTPException
from pydantic import BaseModel, Field
from study_server import courses, replay, view
from repertoire_content import CORE, lesson, explanation

KEY='opening_repertoire_v1'
MAX_HISTORY=64
MAX_EVENTS=256
MAX_BYTES=1048576
POLICY='레퍼토리 예시 재현 기록입니다. 다른 합법 수는 이 레슨에서 다루지 않는 수이며 나쁜 수 판정이 아닙니다. 진단·추천5개·7일 확인·대국 점수에 반영하지 않습니다. 재시도해도 누적 도움·이탈과 첫 복습 결과는 유지합니다. 최대16강 선택, 완료/중단 시도64개·시도당256행·전체1MiB까지 저장하며 한도에서 새 쓰기를 중단합니다.'
class Action(BaseModel):
    action:Literal['select','start','move','hint','retry','weak','finish']
    revision:int=Field(ge=0)
    attempt_id:str|None=Field(default=None,max_length=40)
    lesson_id:str=Field(default='',max_length=80)
    selected:list[str]=Field(default_factory=list,max_length=16)
    mode:Literal['learn','recall']='learn'
    side:Literal['white','black']='white'
    move:str=Field(default='',max_length=5)

def now():return datetime.now(timezone.utc).isoformat()
def board(run):return replay(chess.STARTING_FEN,run['moves'])
def compatible(run):
    return [(bid,line) for bid,line in run['branches'].items() if line[:len(run['moves'])]==run['moves']]
def next_moves(run):return list(dict.fromkeys(line[len(run['moves'])] for _,line in compatible(run) if len(line)>len(run['moves'])))
def outdated(run):return run['lesson_id'] not in courses() or run['version']!=lesson(run['lesson_id'])['version']
def event(run,kind,move=None):
    if len(run['events'])>=MAX_EVENTS:raise HTTPException(409,'시도 기록 한도입니다. 현재 시도를 마친 뒤 새 시도로 이어가세요.')
    if kind in ('hint','deviation'):
        point={'ply':len(run['moves']),'moves':list(run['moves']),'fen':board(run).fen()}
        if point not in run.setdefault('weak_points',[]):run['weak_points'].append(point)
    run['events'].append({'kind':kind,'ply':len(run['moves']),'fen':board(run).fen(),'move':move,'at':now()})
def advance(run):
    # Opponent uses the selected main line, or the registered alternate already chosen.
    while next_moves(run) and board(run).turn!=(run['side']=='white'):
        run['moves'].append(next_moves(run)[0])
    run['branch_ids']=[bid for bid,_ in compatible(run)]
    if not next_moves(run):run['phase']='complete';run['feedback']='선택한 레퍼토리 예시를 재현했습니다. 독립 실력이나 모든 대응의 숙련을 뜻하지 않습니다.'
def archive(saved):
    r=saved.get('active')
    if not r:return
    if len(saved['history'])>=MAX_HISTORY:raise HTTPException(409,'보존 가능한 시도64개에 도달했습니다. 기존 기록을 지우지 않으며 새 시도를 만들지 않습니다.')
    if r['phase']=='playing':r['phase']='stopped'
    saved['history'].append(copy.deepcopy(r));saved['active']=None

def record_completion(saved):
    r=saved['active'];metric=saved['metrics'].setdefault(r['lesson_id'],{'hints':0,'deviations':0,'recall_attempts':0,'completions':0,'first_recall':None})
    if r['phase']=='complete' and not r.get('recorded'):
        r['recorded']=True;metric['completions']+=1
        if r['mode']=='recall' and metric['first_recall'] is None:
            metric['first_recall']={'attempt_id':r['id'],'clean':not r['hints'] and not r['deviations'] and r['start_ply']==0,'completed':True}

def payload(saved):
    r=saved.get('active');active=None
    if r:
        active={k:copy.deepcopy(r[k]) for k in ['id','root_id','lesson_id','version','title','side','mode','phase','moves','branch_ids','events','hints','deviations','feedback','start_ply','weak_points']}
        active.update(view(board(r)));active['outdated']=outdated(r)
        active['legal']=active['legal'] if r['phase']=='playing' and not active['outdated'] else []
        reveal=r['mode']=='learn' or r.get('hint_ply')==len(r['moves']) or r['phase']!='playing'
        active['guidance']=explanation(r['lesson_id'],r['moves']) if reveal and not active['outdated'] else None
        active['options']=[{'move':u,'san':board(r).san(chess.Move.from_uci(u))} for u in next_moves(r)] if reveal and not active['outdated'] else []
    return {'revision':saved.get('revision',0),'selected':saved.get('selected',[]),'active':active,'metrics':saved.get('metrics',{}),
            'history':[{k:r[k] for k in ['id','lesson_id','title','version','mode','side','phase','hints','deviations','start_ply']} for r in saved.get('history',[])],
            'catalog':[{'id':c['id'],'title':c['title'],'core':c['id'] in CORE,'version':lesson(c['id'])['version']} for c in courses().values()], 'policy':POLICY}

def attach_repertoire(app,ns):
    @app.get('/api/repertoire')
    def get(authorization:str|None=Header(default=None)):
        return payload(ns['get_state'](ns['auth'](authorization)).get(KEY,{}))
    @app.get('/api/repertoire/history/{attempt_id}')
    def history(attempt_id:str,authorization:str|None=Header(default=None)):
        s=ns['get_state'](ns['auth'](authorization)).get(KEY,{})
        r=next((r for r in s.get('history',[]) if r['id']==attempt_id),None)
        if not r:raise HTTPException(404,'이 계정의 시도 기록이 없습니다.')
        return copy.deepcopy(r)
    @app.post('/api/repertoire/action')
    def action(req:Action,authorization:str|None=Header(default=None)):
        code=ns['auth'](authorization);state=ns['get_state'](code)
        saved=copy.deepcopy(state.get(KEY,{'revision':0,'selected':[],'history':[],'metrics':{}}))
        if req.revision!=saved['revision']:raise HTTPException(409,'다른 화면에서 레퍼토리가 바뀌었습니다. 저장 상태를 다시 불러오세요.')
        r=saved.get('active')
        if req.action=='select':
            if any(c not in courses() for c in req.selected):raise HTTPException(400,'등록된 강의만 선택할 수 있습니다.')
            saved['selected']=list(dict.fromkeys(req.selected))
        elif req.action=='start':
            if r and r['phase']=='playing':raise HTTPException(409,'진행 중 시도를 먼저 이어가거나 마쳐 주세요.')
            if req.lesson_id not in saved['selected']:raise HTTPException(400,'내 레퍼토리에 먼저 선택해 주세요.')
            archive(saved);c=lesson(req.lesson_id);ident=secrets.token_hex(16)
            saved['active']={'id':ident,'root_id':ident,'lesson_id':c['id'],'version':c['version'],'title':c['title'],'branches':copy.deepcopy(c['branches']),'moves':[],'branch_ids':list(c['branches']),'side':req.side,'mode':req.mode,'phase':'playing','events':[],'weak_points':[],'hints':0,'deviations':0,'feedback':'상대 대응을 확인하며 선택한 색의 수를 두세요.','start_ply':0,'at':now()}
            metric=saved['metrics'].setdefault(c['id'],{'hints':0,'deviations':0,'recall_attempts':0,'completions':0,'first_recall':None})
            if req.mode=='recall':metric['recall_attempts']+=1
            advance(saved['active'])
        else:
            if not r or r['id']!=req.attempt_id:raise HTTPException(409,'시도가 바뀌었습니다. 저장 상태를 확인하세요.')
            metric=saved['metrics'][r['lesson_id']]
            if req.action=='finish':
                if r['mode']=='recall' and metric['first_recall'] is None:metric['first_recall']={'attempt_id':r['id'],'completed':False,'clean':False}
                if r['phase']=='playing':r['phase']='stopped';r['feedback']='중단한 시도를 기록했습니다. 완주로 집계하지 않습니다.'
                archive(saved)
            elif outdated(r):raise HTTPException(409,'콘텐츠 버전이 바뀌었습니다. 기존 시도를 기록으로 마친 뒤 새 버전을 명시적으로 시작하세요.')
            elif req.action in ('retry','weak'):
                old=copy.deepcopy(r)
                if req.action=='weak':
                    points=r.get('weak_points',[])
                    if not points:raise HTTPException(409,'도움이나 이탈 위치가 없습니다. 전체 복습을 선택하세요.')
                    point=min(points,key=lambda p:p['ply']);start=point['ply']
                else:start=0
                if r['mode']=='recall' and metric['first_recall'] is None:metric['first_recall']={'attempt_id':r['id'],'completed':False,'clean':False}
                archive(saved)
                old.update(id=secrets.token_hex(16),moves=point['moves'] if req.action=='weak' else [],phase='playing',events=[],start_ply=start,feedback='이전 도움·이탈 누적을 유지하는 재시도입니다.',at=now())
                old.pop('hint_ply',None);old.pop('recorded',None);saved['active']=old
                if old['mode']=='recall':metric['recall_attempts']+=1
                advance(old)
            elif r['phase']!='playing':raise HTTPException(409,'완료한 시도입니다. 다시 연습하거나 다른 레슨을 선택하세요.')
            elif req.action=='hint':
                event(r,'hint');r['hint_ply']=len(r['moves']);r['hints']+=1;metric['hints']+=1;r['feedback']='현재 위치의 등록 수와 설명을 공개했습니다. 도움 사용을 저장했습니다.'
            else:
                b=board(r)
                try:m=chess.Move.from_uci(req.move)
                except ValueError:raise HTTPException(400,'출발·도착과 승격 기물을 확인하세요.')
                if m not in b.legal_moves:raise HTTPException(400,'불법 수입니다. 저장된 위치는 바뀌지 않았습니다.')
                if req.move not in next_moves(r):
                    event(r,'deviation',req.move);r['deviations']+=1;metric['deviations']+=1;r['feedback']='선택한 레퍼토리 수순과 다릅니다. 이 레슨에서 다루지 않는 합법 수이며 우열은 판정하지 않습니다. 현재 위치에서 다시 선택하세요.'
                else:
                    event(r,'accepted',req.move);r['moves'].append(req.move);r.pop('hint_ply',None);r['feedback']='등록 수를 두었습니다. 상대 응수 뒤 다음 내 수를 선택하세요.';advance(r)
        if saved.get('active'):record_completion(saved)
        saved['revision']+=1;saved['write_id']=secrets.token_hex(16)
        if len(json.dumps(saved,ensure_ascii=False).encode())>MAX_BYTES:raise HTTPException(409,'레퍼토리 저장 용량 한도입니다. 기존 기록은 보존되며 이번 변경은 저장하지 않습니다.')
        state[KEY]=saved;ns['save_state'](code,state);return payload(saved)
