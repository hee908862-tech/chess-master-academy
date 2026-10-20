"""Versioned product index from outcomes against recorded AI, never human Elo."""
import copy
import math
from contextvars import ContextVar

VERSION='app-rating-beta-v1'
AI_VERSION='ai-execution-v1'
INITIAL=50.0
K=8.0
SCALE=12.0
_call=ContextVar('rating_ai_call',default=None)


def record_ai(board,engine,settings,anchor):
    target=_call.get()
    if target is not None:
        target.append({'ply':len(board.move_stack)+1,'engine':engine,'settings':settings,'anchor':anchor,'policy':AI_VERSION})


def play_recorded(fn,board,level,active):
    calls=[];token=_call.set(calls)
    try:return fn(board,level)
    finally:
        _call.reset(token)
        ledger=active.setdefault('ai_execution',{'version':AI_VERSION,'complete':True,'calls':[]})
        if not calls:ledger['complete']=False
        ledger['calls'].extend(calls)


def reasons(game):
    result=[];log=game.get('ai_execution') or {};help_log=game.get('assistance') or {}
    if game.get('time_mode') not in ('unlimited','rapid','blitz','bullet'):result.append('시계 형식 미확인')
    if not game.get('session_id'):result.append('대국 식별 기록 없음')
    if not help_log.get('version') or not help_log.get('complete'):result.append('과거 도움 정보 미확인')
    if game.get('hint_used') or game.get('hint_plies') or help_log.get('events'):result.append('힌트·무르기 사용')
    if game.get('termination') not in ('rules','resign','timeout'):result.append('정상 종료된 대국이 아님')
    if game.get('result') not in ('win','draw','loss'):result.append('승무패 미확인')
    side=game.get('color');moves=game.get('moves',[])
    own=[i+1 for i in range(len(moves)) if (i%2==0)==(side=='white')]
    opponent=[i+1 for i in range(len(moves)) if (i%2==0)!=(side=='white')]
    if side not in ('white','black') or not own:result.append('사용자 착수 부족')
    calls=log.get('calls',[])
    # AI can consume its remaining clock while computing a move that is never played.
    expected_calls=list(opponent)
    if game.get('termination')=='timeout' and game.get('result')=='win' and calls and calls[-1].get('ply')==len(moves)+1 and (len(moves)%2==0)!=(side=='white'):
        expected_calls.append(len(moves)+1)
    if log.get('version')!=AI_VERSION or not log.get('complete') or [c.get('ply') for c in calls]!=expected_calls:
        result.append('실제 AI 설정 기록 불완전')
    if any(c.get('engine')=='cma-minimax-v1' for c in calls):result.append('대체 AI 사용: 미보정 참고 대국')
    if not calls or any(c.get('policy')!=AI_VERSION or c.get('anchor') is None for c in calls):result.append('내부 기준점 없는 AI 설정')
    if calls and any((c.get('engine'),c.get('settings'),c.get('anchor'))!=(calls[0].get('engine'),calls[0].get('settings'),calls[0].get('anchor')) for c in calls):result.append('대국 중 AI 설정 변경')
    return result


def archive(state,active):
    game=state['games'][-1]
    if active.get('ai_execution'):
        game['ai_execution']=copy.deepcopy(active['ai_execution'])
        for call in game['ai_execution']['calls']:call['played']=call.get('ply',0)<=len(game['moves'])
    if game.get('app_rating'):return
    prior=next((g.get('app_rating') for g in state['games'][:-1] if g.get('session_id') and g.get('session_id')==game.get('session_id') and g.get('app_rating')),None)
    if prior:game['app_rating']=copy.deepcopy(prior);return
    excluded=reasons(game)
    row={'version':VERSION,'eligible':not excluded,'reasons':excluded,'result':game.get('result'),'before':None,'after':None,'anchor':None,'time_mode':game.get('time_mode','unknown')}
    if not excluded:
        mode=game.get('time_mode','unknown')
        models=state.setdefault('app_ratings',{})
        model=models.get(mode) or {};before=model.get('value',INITIAL);count=model.get('games',0)
        anchor=game['ai_execution']['calls'][0]['anchor']
        expectation=1/(1+math.exp((anchor-before)/SCALE));outcome={'win':1.,'draw':.5,'loss':0.}[game['result']]
        after=round(max(0,min(100,before+K*(outcome-expectation))),3)
        row.update(before=before,after=after,anchor=anchor,expected=expectation,outcome=outcome,k=K,scale=SCALE,number=count+1)
        models[mode]={'version':VERSION,'value':after,'games':count+1}
    game['app_rating']=row


def public_game(game):
    return copy.deepcopy(game.get('app_rating') or {'version':VERSION,'eligible':False,'reasons':reasons(game) or ['지표 도입 이전 대국: 소급 갱신하지 않음'],'before':None,'after':None})


def summary(state):
    return {'version':VERSION,'series':copy.deepcopy(state.get('app_ratings',{})),
            'initial':INITIAL,'label':'앱 내 추정 레이팅 · 베타','note':'0–100 앱 내부 승무패 지표입니다. AI 기준점은 미보정 제품 기본값이며, 대국 수와 관계없이 공식 Elo·검증된 사람 레이팅이 아닙니다. 내 수 품질과 별도로 계산합니다.'}
