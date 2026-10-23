from engine_budget import open_engine, EngineBusy
"""Bounded background analysis of saved games. No material-only fallback or Elo mapping."""
import hashlib
import json
import math
import secrets
import threading
import time
from contextvars import copy_context
from pathlib import Path
from datetime import datetime,timezone
import chess
import chess.engine
from fastapi import Header,HTTPException
from app_rating import summary as rating_summary, public_game as rating_game
from game_observations import observe_game

VERSION='move-quality-v2'
_slots=threading.BoundedSemaphore(1)

def game_key(game):
    return hashlib.sha256(json.dumps(game,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:32]

def move_quality(before,after):
    """Own-side centipawn loss -> bounded internal quality, not Lichess/Chess.com accuracy."""
    loss=max(0,before-after)
    return round(100*math.exp(-loss/200),1),loss

def analyse_game(game,path):
    if not path or not Path(path).is_file():raise RuntimeError('분석 엔진을 사용할 수 없습니다.')
    board=chess.Board(game.get('initial_fen',chess.STARTING_FEN));side=game.get('color','white')=='white'
    if not board.is_valid():raise RuntimeError('저장된 시작 국면이 올바르지 않습니다.')
    moves=game.get('moves',[]);rows=[];expected=sum((i%2==0)==(board.turn==side) for i in range(len(moves)))
    engine=open_engine(path,timeout=5)
    try:
        engine.configure({'Threads':1,'Hash':16});engine_name=engine.id.get('name','Stockfish')
        for ply,uci in enumerate(moves):
            move=chess.Move.from_uci(uci)
            if move not in board.legal_moves:raise RuntimeError('저장된 수순을 확인하지 못했습니다.')
            if board.turn!=side:board.push(move);continue
            if len(rows)>=80:break
            before=engine.analyse(board,chess.engine.Limit(time=.08,depth=14));board.push(move)
            terminal=board.is_game_over(claim_draw=True)
            after=({'score':chess.engine.PovScore(chess.engine.Cp(0),side)} if terminal else engine.analyse(board,chess.engine.Limit(time=.08,depth=14)))
            if 'score' not in before or 'score' not in after:continue
            a=before['score'].pov(side).score();b=after['score'].pov(side).score()
            mate=board.is_checkmate() or before['score'].is_mate() or after['score'].is_mate()
            basis='centipawn_loss';score=loss=None
            if board.is_checkmate():score=100.;loss=0;basis='rules_checkmate';b=None
            elif a is not None and b is not None:score,loss=move_quality(a,b)
            else:basis='mate_not_on_cp_scale'
            depth=before.get('depth',0) if terminal else min(before.get('depth',0),after.get('depth',0))
            rows.append({'ply':ply+1,'quality':score,'loss_cp':loss,'before_cp':a,'after_cp':b,'depth':depth,
                         'terminal':terminal,'quality_basis':basis,'mate_evaluation':mate})
    finally:
        try:engine.quit()
        except Exception:pass
    if not rows:raise RuntimeError('분석할 내 착수가 없거나 엔진 평가가 없습니다.')
    helped=bool(game.get('hint_used') or game.get('hint_plies') or (game.get('assistance') or {}).get('events'))
    assistance_known=bool((game.get('assistance') or {}).get('version') and (game.get('assistance') or {}).get('complete'))
    shallow=any(r['depth']<8 for r in rows);partial=len(rows)<expected or shallow
    flags=[]
    if helped:flags.append('힌트·무르기 사용')
    if not assistance_known:flags.append('과거 도움 기록 미확인')
    if len(rows)<10:flags.append('짧은 대국')
    if game.get('termination') not in (None,'rules','resign','timeout'):flags.append('미완료 대국')
    if shallow:flags.append('낮은 탐색 깊이')
    if len(rows)<expected:flags.append('일부 착수만 분석')
    quality=[r['quality'] for r in rows if r['quality'] is not None]
    if not quality:flags.append('수치 평가 없음: 메이트 평가 별도')
    return {'status':'partial' if partial else 'complete','score_version':VERSION,'quality':round(sum(quality)/len(quality),1) if quality else None,'quality_moves':len(quality),'mate_unscored':sum(r['quality'] is None for r in rows),
            'user_moves':len(rows),'expected_moves':expected,'rows':rows,'flags':flags,'representative':not flags,
            'engine':engine_name,'settings':{'threads':1,'hash_mb':16,'seconds_per_position':.08,'max_depth':14,'minimum_depth':8,'max_user_moves':80},
            'rating':None,'rating_reason':'외부 사람 레이팅으로의 환산은 보류합니다. 검증된 환산 모델이 없어요.',
            'method':'내 수 품질: 내 관점의 엔진 평가 손실에 100×exp(-손실cp/200)를 적용한 평균. 공식 정확도·Elo가 아닙니다.'}


def attach_analysis(app,ns):
    db,execute,auth=ns['db'],ns['execute'],ns['auth']
    with db() as conn:execute(conn,'CREATE TABLE IF NOT EXISTS game_analysis (code TEXT NOT NULL, game_key TEXT NOT NULL, state TEXT NOT NULL, PRIMARY KEY(code,game_key))')
    def read(code,key):
        with db() as conn:
            row=execute(conn,'SELECT state FROM game_analysis WHERE code=? AND game_key=?',(code,key)).fetchone()
            return json.loads(row['state']) if row else None
    def finish_save(code,key,data):
        with db() as conn:
            row=execute(conn,'SELECT state FROM game_analysis WHERE code=? AND game_key=?',(code,key)).fetchone()
            if row and json.loads(row['state']).get('job_id')==data['job_id']:
                execute(conn,'UPDATE game_analysis SET state=? WHERE code=? AND game_key=? AND state=?',(json.dumps(data,ensure_ascii=False),code,key,row['state']))
    def visible(data):
        if not data:return {'status':'not_started'}
        result={k:v for k,v in data.items() if k not in ('rows','previous_analysis')}
        if data['status'] in ('complete','partial') and data.get('score_version')!=VERSION:
            result.update(status='outdated',error='이전 분석 방식의 기록입니다. 새 방식으로 다시 분석할 수 있어요.')
        if data['status'] in ('queued','running') and time.time()-data['requested_at']>120:
            result.update(status='failed',error='분석이 중단됐어요. 다시 분석할 수 있습니다.')
        return result
    @app.get('/api/games/analysis')
    def status(authorization:str|None=Header(default=None)):
        code=auth(authorization);state=ns['get_state'](code);games=state.get('games',[])
        with db() as conn:
            stored={r['game_key']:json.loads(r['state']) for r in execute(conn,'SELECT game_key,state FROM game_analysis WHERE code=?',(code,)).fetchall()}
        records=[{'index':i,'game_key':game_key(g),'observations_available':True,'at':g.get('ended'),'color':g.get('color','white'),'app_rating':rating_game(g),'time_mode':g.get('time_mode','unknown'),**visible(stored.get(game_key(g)))} for i,g in enumerate(games)]
        eligible=[r for r in records if r.get('quality') is not None and r.get('representative') and r.get('score_version')==VERSION and r['status']=='complete']
        return {'games':records,'average':round(sum(r['quality']*r.get('quality_moves',r['user_moves']) for r in eligible)/sum(r.get('quality_moves',r['user_moves']) for r in eligible),1) if eligible else None,
                'representative_games':len(eligible),'app_rating':rating_summary(state),'rating':None,'rating_reason':'정확도 하나로 Elo를 환산하지 않습니다. 검증된 모델이 없어 외부 사람 레이팅으로의 환산은 보류합니다.'}
    @app.get('/api/games/observations/{key}')
    def observations(key:str,authorization:str|None=Header(default=None)):
        code=auth(authorization)
        game=next((g for g in ns['get_state'](code).get('games',[]) if game_key(g)==key),None)
        if game is None:raise HTTPException(404,'저장된 대국을 찾을 수 없습니다.')
        return observe_game(game,key)

    @app.post('/api/games/analysis/{key}')
    def start(key:str,authorization:str|None=Header(default=None)):
        code=auth(authorization);game=next((g for g in ns['get_state'](code).get('games',[]) if game_key(g)==key),None)
        if game is None:raise HTTPException(404,'저장된 대국을 찾을 수 없습니다.')
        old=read(code,key)
        if old and visible(old)['status'] in ('queued','running','complete','partial'):return visible(old)
        if not _slots.acquire(blocking=False):raise HTTPException(429,'다른 대국을 분석하고 있어요. 잠시 후 다시 눌러 주세요.',headers={'Retry-After':'5'})
        job={'status':'queued','score_version':VERSION,'job_id':secrets.token_hex(12),'requested_at':time.time()}
        if old:
            previous=dict(old.get('previous_analysis',{}))
            if old.get('score_version') and old.get('score_version')!=VERSION:previous[old['score_version']]={k:v for k,v in old.items() if k!='previous_analysis'}
            if previous:job['previous_analysis']=previous
        duplicate=None
        try:
            with db() as conn:
                if not ns['DATABASE_URL']:execute(conn,'BEGIN IMMEDIATE')
                else:execute(conn,'SELECT pg_advisory_xact_lock(hashtext(?))',('game-analysis:'+code,))
                row=execute(conn,'SELECT state FROM game_analysis WHERE code=? AND game_key=?',(code,key)).fetchone()
                if row and visible(json.loads(row['state']))['status'] in ('queued','running','complete','partial'):
                    duplicate=visible(json.loads(row['state']))
                else:
                    execute(conn,'INSERT INTO game_analysis(code,game_key,state) VALUES(?,?,?) ON CONFLICT(code,game_key) DO UPDATE SET state=excluded.state',(code,key,json.dumps(job)))
        except Exception:_slots.release();raise
        if duplicate is not None:
            _slots.release();return duplicate
        context=copy_context()
        def work():
            try:
                finish_save(code,key,{**job,'status':'running'})
                result=analyse_game(game,ns['STOCKFISH_PATH'])
                # The original request generation is preserved; reset cannot resurrect old work.
                finish_save(code,key,{**job,**result,'finished_at':datetime.now(timezone.utc).isoformat()})
            except Exception:
                try:finish_save(code,key,{**job,'status':'failed','error':'분석을 완료하지 못했어요. 대국 기록은 그대로이며 다시 시도할 수 있습니다.'})
                except Exception:pass
            finally:_slots.release()
        try:threading.Thread(target=lambda:context.run(work),daemon=True,name='game-analysis').start()
        except Exception:
            _slots.release()
            finish_save(code,key,{**job,'status':'failed','error':'분석 작업을 시작하지 못했어요. 다시 시도해 주세요.'})
            raise HTTPException(503,'분석 작업을 시작하지 못했어요. 다시 시도해 주세요.')
        return visible(job)
