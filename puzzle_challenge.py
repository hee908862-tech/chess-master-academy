"""Optional untimed puzzle game. Own state/score, never writes measured learning credit."""
import copy
import secrets
from datetime import datetime, timezone
from typing import Literal
import chess
from fastapi import Header, HTTPException
from pydantic import BaseModel,Field
from v9_server import LIB, LEVELS, THEMES

KEY='puzzle_challenge_v1'
class Action(BaseModel):
    action:Literal['start','move','hint','next','finish']
    revision:int=Field(ge=0)
    session_id:str|None=None
    level:Literal['입문','중급','고급']='입문'
    move:str=Field(default='',max_length=5)


def board(run):
    p=run['puzzles'][run['index']];b=chess.Board(p['fen'])
    for u in p['moves'][:run['offset']]:b.push_uci(u)
    return b


def attach_challenge(app,ns):
    def payload(saved):
        run=saved.get('active');task=None
        if run:
            p=run['puzzles'][run['index']];b=board(run)
            task={k:copy.deepcopy(run[k]) for k in ['id','level','index','phase','score','lives','feedback','hinted','hint','started_at']}
            task.update(total=len(run['puzzles']),fen=run.get('display_fen',b.fen()),side='white' if chess.Board(p['fen']).turn==chess.BLACK else 'black',legal=[m.uci() for m in b.legal_moves] if run['phase']=='playing' else [],rating=p['rating'],themes=[THEMES[t] for t in p['themes'] if t in THEMES],puzzle_id=p['id'])
        return {'revision':saved.get('revision',0),'active':task,'history':[{k:r[k] for k in ['id','score','ended_at','solved','hinted_solved','reason']} for r in reversed(saved.get('history',[]))], 'policy':'시간제한 없는 10문제·목숨3개. 기준 수순 완주 10점, 힌트 사용 후 완주 5점. 기준과 다른 수/건너뛰기는 목숨1개. 대안 메이트는 규칙으로 확인한 경우 인정합니다. 다른 합법 수의 우열은 판정하지 않습니다. 게임 점수는 진단·Elo·추천 훈련과 별도입니다.'}
    def end(saved,reason):
        r=saved['active']
        if r['phase']=='ended':return
        r['phase']='ended';r['feedback']=reason
        saved.setdefault('history',[]).append({'id':r['id'],'score':r['score'],'ended_at':datetime.now(timezone.utc).isoformat(),'solved':sum(a['correct'] for a in r['attempts']),'hinted_solved':sum(a['correct'] and a['hinted'] for a in r['attempts']),'reason':reason,'review':copy.deepcopy(r['attempts'])})
    def complete(saved,correct,message,submitted=None):
        r=saved['active'];p=r['puzzles'][r['index']]
        points=(5 if r['hinted'] else 10) if correct else 0
        r['score']+=points;r['lives']-=int(not correct);r['phase']='feedback';r['feedback']=message+f' · 이번 문제 {points}점'
        r['attempts'].append({'puzzle':copy.deepcopy(p),'correct':correct,'hinted':r['hinted'],'points':points,'submitted':list(r['submitted']),'last_move':submitted,'reason':message})
        if r['lives']==0:end(saved,'목숨을 모두 사용했습니다. 실수한 문제의 수순을 복습할 수 있어요.')
        elif r['index']+1==len(r['puzzles']):end(saved,'10문제를 확인했습니다. 결과를 살펴보고 필요하면 다시 도전하세요.')
    @app.get('/api/challenge')
    def get(authorization:str|None=Header(default=None)):
        return payload(ns['get_state'](ns['auth'](authorization)).get(KEY,{}))
    @app.get('/api/challenge/review/{run_id}')
    def review(run_id:str,authorization:str|None=Header(default=None)):
        saved=ns['get_state'](ns['auth'](authorization)).get(KEY,{})
        row=next((r for r in saved.get('history',[]) if r['id']==run_id),None)
        if not row:raise HTTPException(404,'이 계정에서 완료한 도전을 찾을 수 없습니다.')
        out=[]
        for a in row['review']:
            p=a['puzzle'];b=chess.Board(p['fen']);frames=[]
            for i,u in enumerate(p['moves']):
                san=b.san(chess.Move.from_uci(u));b.push_uci(u);frames.append({'fen':b.fen(),'san':san,'move':u,'solver':bool(i%2)})
            out.append({k:a[k] for k in ['correct','hinted','points','submitted','reason']}|{'id':p['id'],'frames':frames,'rating':p['rating'],'source':'Lichess CC0 기준 수순 · 대안 전체를 비교한 해설은 아닙니다.'})
        return {'id':run_id,'items':out}
    @app.post('/api/challenge/action')
    def action(req:Action,authorization:str|None=Header(default=None)):
        code=ns['auth'](authorization);state=ns['get_state'](code);saved=copy.deepcopy(state.get(KEY,{'revision':0,'history':[]}))
        if req.revision!=saved['revision']:raise HTTPException(409,'다른 요청에서 도전이 갱신됐습니다. 저장 상태를 다시 불러오세요.')
        r=saved.get('active')
        if req.action=='start':
            if r and r['phase']!='ended':raise HTTPException(409,'진행 중인 도전을 이어가거나 먼저 마쳐 주세요.')
            lo,hi=LEVELS[req.level];candidates=[p for p in LIB.values() if lo<=p['rating']<hi]
            if len(candidates)<10:raise HTTPException(503,'이 난도의 검증된 문제가 부족합니다. 일반 퍼즐이나 다른 난도를 이용하세요.')
            selected=secrets.SystemRandom().sample(candidates,10)
            saved['active']={'id':secrets.token_hex(16),'puzzles':[{k:copy.deepcopy(p[k]) for k in ['id','fen','moves','rating','themes']} for p in selected],'level':req.level,'index':0,'offset':1,'phase':'playing','score':0,'lives':3,'hinted':False,'hint':None,'feedback':'상대 직전 수 뒤의 위치입니다. 내 수와 이어지는 수순을 직접 두세요.','attempts':[],'submitted':[],'started_at':datetime.now(timezone.utc).isoformat()}
        else:
            if not r or r['id']!=req.session_id:raise HTTPException(409,'도전 세션이 바뀌었습니다. 저장 상태를 확인하세요.')
            if r['phase']=='ended':raise HTTPException(409,'이미 종료된 도전입니다. 결과를 복습하거나 새 도전을 시작하세요.')
            if req.action=='finish':end(saved,'직접 도전을 마쳤습니다. 아직 풀지 않은 문제는 채점하지 않았습니다.')
            elif req.action=='next':
                if r['phase']=='playing':
                    complete(saved,False,'문제를 건너뛰었습니다.')
                else:
                    r.update(index=r['index']+1,offset=1,phase='playing',hinted=False,hint=None,submitted=[],feedback='다음 문제입니다. 상대 응수 뒤의 내 수까지 직접 두세요.');r.pop('display_fen',None)
            elif r['phase']!='playing':raise HTTPException(409,'이미 채점한 문제입니다. 다음 문제를 선택하세요.')
            elif req.action=='hint':
                r['hinted']=True;r['hint']=r['puzzles'][r['index']]['moves'][r['offset']];r['feedback']='현재 기준 수를 표시했습니다. 이 문제 완주 시5점이며 도움 사용을 별도 표시합니다.'
            else:
                b=board(r);p=r['puzzles'][r['index']]
                try:m=chess.Move.from_uci(req.move)
                except ValueError:raise HTTPException(400,'출발·도착 칸과 승격 기물을 다시 선택하세요.')
                if m not in b.legal_moves:raise HTTPException(400,'현재 위치의 합법 수가 아닙니다. 점수나 목숨은 바뀌지 않았습니다.')
                r['submitted'].append(req.move);trial=b.copy();trial.push(m)
                if req.move==p['moves'][r['offset']] or trial.is_checkmate():
                    if trial.is_checkmate() or r['offset']+1==len(p['moves']):
                        r['display_fen']=trial.fen();complete(saved,True,'기준 수순을 완주했거나 규칙으로 확인된 메이트입니다.',req.move)
                    else:
                        r['offset']+=2;r['hint']=None;r['feedback']='기준 수를 두었고 상대가 응수했습니다. 다음 내 수를 이어 두세요.'
                else:complete(saved,False,'기준 수순과 달라 이번 문제의 도전을 마쳤습니다. 이 합법 수의 우열은 미검증이며 실력 점수로 기록하지 않습니다.',req.move)
        # Distinguish concurrent identical transitions so existing field CAS rejects the loser.
        saved['write_id']=secrets.token_hex(16)
        saved['revision']+=1;state[KEY]=saved;ns['save_state'](code,state);return payload(saved)
