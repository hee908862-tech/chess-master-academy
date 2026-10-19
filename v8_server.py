"""V8 API: 49 timed questions + short AI evaluation game, rating history.
Works with existing JSON progress records, no schema migration.
"""
import secrets,time,datetime
import chess
import chess.engine
from fastapi import HTTPException,Header
from pydantic import BaseModel,Field
from assessment_v8 import questions,public_question,points,finalize,DOMAINS

class AnswerV8(BaseModel):
    id:int=Field(ge=0,le=48)
    move:str
class GameMoveV8(BaseModel):
    move:str

def attach_v8(app,ns):
    auth=ns['auth'];get_state=ns['get_state'];save_state=ns['save_state']
    serialize_board=ns['serialize_board'];medium_move=ns['medium_move']
    Path=ns['Path']
    def engine_eval(board):
        path=ns['STOCKFISH_PATH']
        if not path or not Path(path).exists():return None
        try:
            with chess.engine.SimpleEngine.popen_uci(path,timeout=10) as engine:
                info=engine.analyse(board,chess.engine.Limit(time=0.11))
                return info['score'].white().score(mate_score=10000)
        except Exception:
            return None
    def require(authorization):
        code=auth(authorization);state=get_state(code);t=state.get('assessment_v8')
        if not t:raise HTTPException(409,'진행 중인 v8 진단이 없습니다.')
        return code,state,t
    def clock_view(t):
        c=t.get('clock',{'white_ms':600000,'black_ms':600000,'increment_ms':5000})
        out=dict(c)
        if t.get('phase')=='game' and t.get('clock_started_at'):
            b=board_from(t)
            side='white_ms' if b.turn else 'black_ms'
            out[side]=max(0,out[side]-int((time.time()-t['clock_started_at'])*1000))
        return out
    def current(t):
        q=questions(t['seed'])[t['index']]
        return {'phase':'questions','index':t['index'],'total':49,'domain':q['domain_name'],
                'question':public_question(q),'start_time':t['shown_at']}
    def board_from(t):
        b=chess.Board()
        for m in t.get('moves',[]):b.push_uci(m)
        return b
    @app.post('/api/v8/assessment/start')
    def start(authorization:str|None=Header(default=None)):
        code=auth(authorization);s=get_state(code)
        seed=secrets.randbits(32)
        questions(seed) # fail before mutating existing state
        s['assessment_v8']={'seed':seed,'index':0,'phase':'questions','shown_at':time.time(),
                             'log':[],'moves':[],'losses':[],'engine_ok':False}
        save_state(code,s)
        return current(s['assessment_v8'])
    @app.get('/api/v8/assessment/status')
    def status(authorization:str|None=Header(default=None)):
        code=auth(authorization);s=get_state(code);t=s.get('assessment_v8')
        if not t:return {'active':False,'recent':s.get('assessment_v8_latest'),'history':s.get('assessment_v8_history',[])[-12:]}
        if t['phase']=='feedback':return {'active':True,'phase':'feedback','feedback':t['feedback'],'index':t['index'],'total':49}
        if t['phase']=='game' and clock_view(t).get('white_ms',1)<=0:
            return {'active':False,**finish_assessment(code,s,t,board_from(t),'백 시간 초과')}
        if t['phase']=='game':return {'active':True,'phase':'game','board':serialize_board(board_from(t)),
                                     'white_moves':len(t['losses']),'target_white_moves':None,'clock':clock_view(t)}
        return {'active':True,**current(t)}
    @app.post('/api/v8/assessment/answer')
    def answer(body:AnswerV8,authorization:str|None=Header(default=None)):
        code,s,t=require(authorization)
        if t['phase']!='questions' or body.id!=t['index']:
            raise HTTPException(409,'현재 진단 문항이 아닙니다.')
        q=questions(t['seed'])[t['index']];b=chess.Board(q['fen'])
        try:m=chess.Move.from_uci(body.move)
        except ValueError:raise HTTPException(400,'올바른 착수 형식이 아닙니다.')
        if m not in b.legal_moves:raise HTTPException(400,'합법적인 착수가 아닙니다.')
        correct=m.uci() in q['answers']
        elapsed=max(0.1,min(3600,time.time()-t['shown_at']))
        score=points(correct,elapsed,q['difficulty'])
        t['log'].append({'id':q['id'],'domain':q['domain'],'difficulty':q['difficulty'],
                         'correct':correct,'seconds':round(elapsed,2),'points':score})
        best=q['answers'][0];b.push_uci(best)
        t['feedback']={'correct':correct,'answer':best,'answer_fen':b.fen(),
                       'original_fen':q['fen'],'submitted':body.move,'seconds':round(elapsed,1),
                       'points':score,'domain':q['domain_name'],'difficulty':q['difficulty']}
        t['phase']='feedback';save_state(code,s)
        return {'phase':'feedback','feedback':t['feedback'],'index':t['index'],'total':49}
    @app.post('/api/v8/assessment/next')
    def advance(authorization:str|None=Header(default=None)):
        code,s,t=require(authorization)
        if t['phase']!='feedback':raise HTTPException(409,'이전 문제 채점이 필요합니다.')
        t['index']+=1;t.pop('feedback',None)
        if t['index']>=49:
            t['phase']='game';t['moves']=[];t['losses']=[];t['clock']={'white_ms':600000,'black_ms':600000,'increment_ms':5000};t['clock_started_at']=time.time();save_state(code,s)
            return {'phase':'game','board':serialize_board(chess.Board()),'white_moves':0,'target_white_moves':None,'clock':clock_view(t)}
        t['phase']='questions';t['shown_at']=time.time();save_state(code,s)
        return current(t)
    def finish_assessment(code,s,t,b,reason):
        count=len(t['losses'])
        losses=[x for x in t['losses'] if x is not None]
        previous=s.get('assessment_v8_latest')
        result=finalize(t['log'],losses,t['engine_ok'] and len(losses)==count,count,previous)
        result['at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        result['ending']=reason
        result['game_result']=b.result(claim_draw=True) if b.is_game_over(claim_draw=True) else '시간패'
        history=s.get('assessment_v8_history',[])
        history.append({'at':result['at'],'index':result['index'],'stage':result['stage'],
                        'quiz_score':result['quiz_score'],'game_score':result['game_score']})
        s['assessment_v8_history']=history[-50:];s['assessment_v8_latest']=result
        s['assessment_v8']=None
        s['assessment']={'stage':result['stage'],'index':result['index'],
                        'skills':{v['label']:v['score'] for v in result['domains'].values()},
                        'strengths':result['strengths'],'weaknesses':result['weaknesses'],
                        'total':49,'correct':sum(int(x['correct']) for x in t['log']),
                        'confidence':result['confidence'],'source':'v8.1'}
        save_state(code,s)
        return {'phase':'results','done':True,'board':serialize_board(b),'result':result,'clock':t.get('clock')}

    @app.post('/api/v8/assessment/game-move')
    def game_move(body:GameMoveV8,authorization:str|None=Header(default=None)):
        code,s,t=require(authorization)
        if t['phase']!='game':raise HTTPException(409,'평가 대국 단계가 아닙니다.')
        b=board_from(t)
        if b.turn!=chess.WHITE:raise HTTPException(409,'AI 차례입니다.')
        now=time.time(); elapsed=max(0,int((now-t.get('clock_started_at',now))*1000))
        c=t.setdefault('clock',{'white_ms':600000,'black_ms':600000,'increment_ms':5000})
        c['white_ms']=max(0,c['white_ms']-elapsed)
        if c['white_ms']<=0:return finish_assessment(code,s,t,b,'백 시간 초과')
        try:m=chess.Move.from_uci(body.move)
        except ValueError:raise HTTPException(400,'잘못된 착수 표기입니다.')
        if m not in b.legal_moves:raise HTTPException(400,'합법적으로 둘 수 없는 수입니다.')
        before=engine_eval(b)
        b.push(m);t['moves'].append(m.uci())
        after=engine_eval(b) if before is not None else None
        if before is not None and after is not None:
            t['losses'].append(max(0,min(1500,before-after)));t['engine_ok']=True
        else:t['losses'].append(None)
        c['white_ms']+=c['increment_ms']
        if b.is_game_over(claim_draw=True):return finish_assessment(code,s,t,b,'체스 규칙상 종료')
        ai_start=time.time()
        reply=medium_move(b)
        ai_elapsed=int((time.time()-ai_start)*1000)
        c['black_ms']=max(0,c['black_ms']-ai_elapsed)
        if c['black_ms']<=0:return finish_assessment(code,s,t,b,'흑 시간 초과')
        if reply and reply in b.legal_moves:
            b.push(reply);t['moves'].append(reply.uci());c['black_ms']+=c['increment_ms']
        if b.is_game_over(claim_draw=True):return finish_assessment(code,s,t,b,'체스 규칙상 종료')
        t['clock_started_at']=time.time()
        save_state(code,s)
        return {'phase':'game','board':serialize_board(b),'white_moves':len(t['losses']),
                'target_white_moves':None,'clock':clock_view(t)}

    @app.post('/api/v8/assessment/resign')
    def eval_resign(authorization:str|None=Header(default=None)):
        code,s,t=require(authorization)
        if t['phase']!='game':raise HTTPException(409,'진행 중인 평가 대국이 없습니다.')
        return finish_assessment(code,s,t,board_from(t),'백 기권')

    @app.get('/api/v8/recommendations')
    def recommendations(authorization:str|None=Header(default=None)):
        code=auth(authorization);s=get_state(code);r=s.get('assessment_v8_latest')
        if not r:return {'ready':False,'courses':[]}
        mapping={'mate':['mateIn1','mateIn2','mateIn3'],'defense':['defensiveMove','equality'],
                 'calculation':['fork','discoveredAttack'],'capture':['hangingPiece','trappedPiece'],
                 'tactics':['pin','skewer'],'strategy':['quietMove','interference'],
                 'endgame':['endgame','zugzwang']}
        ordered=sorted(r['domains'].items(),key=lambda item:item[1]['score'])
        seen=set();courses=[]
        for domain,data in ordered:
            for course in mapping.get(domain,[]):
                if course in seen:continue
                seen.add(course);courses.append({'id':course,'domain':data['label'],
                             'reason':f"{data['label']} {data['score']}점 · 우선 보완 추천"})
        return {'ready':True,'index':r['index'],'courses':courses[:8]}
    @app.get('/api/v8/assessment/history')
    def history(authorization:str|None=Header(default=None)):
        code=auth(authorization);s=get_state(code)
        return {'latest':s.get('assessment_v8_latest'),'history':s.get('assessment_v8_history',[])}
