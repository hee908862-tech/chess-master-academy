"""V9 Lichess CC0 puzzle library. Explicitly fails closed when no verified corpus is installed.
Chess legality validated with python-chess for every loaded line. Dataset-based lessons
require complete 15 distinct puzzles for a chosen course and rating band.
"""
import json, secrets, os, chess
from mate_explanation import explain_mate
from pathlib import Path
from fastapi import HTTPException,Header
from pydantic import BaseModel

THEMES={
 'mateIn1':'1수 메이트','mateIn2':'2수 메이트','mateIn3':'3수 메이트','mateIn4':'4수 메이트','mateIn5':'5수 메이트',
 'fork':'포크','pin':'핀','skewer':'스큐어','discoveredAttack':'발견 공격','doubleCheck':'더블 체크',
 'defensiveMove':'위협 방어','endgame':'엔드게임','equality':'불리한 상황에서 무승부','advantage':'우세 확보',
 'hangingPiece':'무방비 기물 포획','trappedPiece':'기물 가두기','interference':'간섭','quietMove':'조용한 수',
 'sacrifice':'희생','promotion':'승격','zugzwang':'추크츠방','backRankMate':'백랭크 메이트',
 'clearance':'길 열기','deflection':'유인·수비 제거','attraction':'유인','overloading':'과부하',
 'xRayAttack':'엑스레이 공격','intermezzo':'중간 수','underPromotion':'언더프로모션',
 'exposedKing':'노출된 킹 공략','capturingDefender':'수비 기물 제거'}
LEVELS={'입문':(600,1200),'중급':(1200,1800),'고급':(1800,2900)}
DATA_FILE=Path(os.getenv('CMA_PUZZLE_FILE',str(Path(__file__).with_name('puzzles_lichess.jsonl'))))
LIB={};BY_THEME={key:[] for key in THEMES};BAD=0

def build():
 global BAD
 if not DATA_FILE.is_file():return
 with DATA_FILE.open(encoding='utf8') as f:
  for line in f:
   try:
    p=json.loads(line);b=chess.Board(p['fen']);moves=p['moves']
    if not b.is_valid() or len(moves)<2 or len(moves)%2 or p['id'] in LIB:continue
    for u in moves:b.push_uci(u)
    # At least one solver move exists and all moves were legal.
    if not any(t in THEMES for t in p['themes']):continue
    LIB[p['id']]=p
    for t in p['themes']:
     if t in BY_THEME:BY_THEME[t].append(p['id'])
   except Exception:BAD+=1
build()


def _is_alternative_mate(board, move, puzzle, task):
 """Allow another proven mating finish; never accept mere checking or a guessed move."""
 trial=board.copy();trial.push(move)
 if trial.is_checkmate():
  return True
 # Non-terminal alternative lines are not accepted without full forced-mate proof.
 return False

class ModeBody(BaseModel):
 theme:str='random'
 level:str='중급'
class CourseStartBody(BaseModel):
 theme:str
 level:str
class MoveBody(BaseModel):
 move:str
 session_id:str|None=None
 expected_fen:str|None=None

def attach_v9(app,ns):
 auth=ns['auth'];get_state=ns['get_state'];save_state=ns['save_state']
 def account(h):return auth(h)
 def eligible(theme,level):
  lo,hi=LEVELS[level]
  ids=LIB.keys() if theme=='random' else BY_THEME.get(theme,[])
  return [pid for pid in ids if lo<=LIB[pid]['rating']<hi]
 def public(p,offset=1):
  b=chess.Board(p['fen'])
  for u in p['moves'][:offset]:b.push_uci(u)
  return {'id':p['id'],'fen':b.fen(),'legal':[m.uci() for m in b.legal_moves],
          'opponent_last_move':p['moves'][offset-1] if offset>0 else None,
          'rating':p['rating'],'themes':[THEMES[t] for t in p['themes'] if t in THEMES],
          'ply':offset,'total_solver_moves':len(p['moves'][1::2]),
          'remaining':len(p['moves'][offset::2]),'side':'white' if b.turn else 'black'}
 def get_session(s,kind):
  task=s.get('v9_'+kind)
  if not task:raise HTTPException(409,'현재 진행 중인 문제가 없습니다.')
  return task
 def task_payload(task):
  p=LIB.get(task['ids'][task['index']])
  if not p:raise HTTPException(409,'문제 데이터가 업데이트되었습니다. 새 세션을 시작하세요.')
  return {'session_id':task.get('session_id'),'type':task['type'],'theme':task.get('theme'),'level':task.get('level'),
          'index':task['index'],'total':len(task['ids']),'correct_count':task['correct_count'],
          'attempted':task['attempted'],**public(p,task['offset'])}
 def start_for(code,theme,level,typ):
  if level not in LEVELS:raise HTTPException(400,'난이도가 올바르지 않습니다.')
  if theme!='random' and theme not in THEMES:raise HTTPException(400,'해당 과목이 없습니다.')
  state=get_state(code)
  if theme=='random':
   # Balance major puzzle themes: pure material-capture puzzles must not dominate.
   groups=['mateIn1','mateIn2','mateIn3','mateIn4','fork','pin','skewer',
           'discoveredAttack','defensiveMove','endgame','equality','zugzwang',
           'sacrifice','trappedPiece','promotion','quietMove']
   live=[g for g in groups if eligible(g,level)]
   if not live:raise HTTPException(503,'해당 난이도의 공개 퍼즐이 없습니다.')
   theme_selected=secrets.choice(live)
   candidates=eligible(theme_selected,level)
   recent=state.get('v9_recent_puzzles',[])
   fresh=[x for x in candidates if x not in recent]
   if fresh:candidates=fresh
  else:candidates=eligible(theme,level)
  count=15 if typ=='course' else 1
  if len(candidates)<count:
   raise HTTPException(503,f'검증된 {THEMES.get(theme,"랜덤")} · {level} 문제 {len(candidates)}개. 최소 {count}개가 필요합니다. Lichess 공개 CSV를 가져오세요.')
  rng=secrets.SystemRandom()
  picks=rng.sample(candidates,count)
  if typ=='puzzle':state['v9_recent_puzzles']=(state.get('v9_recent_puzzles',[])+picks)[-100:]
  state['v9_'+typ]={'session_id':secrets.token_hex(16),'type':typ,'theme':theme,'level':level,'ids':picks,'index':0,
                    'offset':1,'correct_count':0,'attempted':False,'hint_used':False,'wrong_moves':0,'done':False,'awaiting_next':False}
  save_state(code,state)
  return task_payload(state['v9_'+typ])
 @app.get('/api/v9/catalog')
 def catalog(authorization:str|None=Header(default=None)):
  # Available to non-authenticated users to explain setup state.
  out=[]
  for name,label in THEMES.items():
   counts={level:len(eligible(name,level)) for level in LEVELS}
   out.append({'id':name,'name':label,'counts':counts})
  return {'ready':bool(LIB),'count':len(LIB),'invalid_skipped':BAD,'required_per_course':15,
          'levels':list(LEVELS),'themes':out,'source':'Lichess public puzzles (CC0)',
          'setup':'공개 CSV를 import_lichess.py로 선별하여 puzzles_lichess.jsonl을 서버에 업로드하세요.'}
 @app.post('/api/v9/puzzle/start')
 def start_puzzle(body:ModeBody,authorization:str|None=Header(default=None)):
  return start_for(account(authorization),body.theme,body.level,'puzzle')
 @app.post('/api/v9/course/start')
 def start_course(body:CourseStartBody,authorization:str|None=Header(default=None)):
  return start_for(account(authorization),body.theme,body.level,'course')
 @app.get('/api/v9/session/{kind}')
 def session(kind:str,authorization:str|None=Header(default=None)):
  if kind not in ('course','puzzle'):raise HTTPException(400,'잘못된 종류')
  state=get_state(account(authorization));task=state.get('v9_'+kind)
  return {'active':bool(task),'done':task.get('done',False) if task else False,
          'session_id':task.get('session_id') if task else None,
          'result':task.get('last_result') if task and (task.get('done') or task.get('awaiting_next')) else None,
          **(task_payload(task) if task and not task['done'] and not task.get('awaiting_next') else {})}
 @app.get('/api/v9/{kind}/hint')
 def hint(kind:str,authorization:str|None=Header(default=None)):
  if kind not in ('course','puzzle'):raise HTTPException(400,'잘못된 종류')
  code=account(authorization);state=get_state(code);task=get_session(state,kind)
  if task.get('done'):raise HTTPException(409,'이미 끝난 문제입니다.')
  p=LIB[task['ids'][task['index']]];b=chess.Board(p['fen'])
  for u in p['moves'][:task['offset']]:b.push_uci(u)
  u=p['moves'][task['offset']];m=chess.Move.from_uci(u)
  if m not in b.legal_moves:raise HTTPException(500,'문제 데이터의 수순이 잘못되었습니다.')
  label=b.san(m)
  task['attempted']=True;task['hint_used']=True;save_state(code,state)
  return {'from':u[:2],'to':u[2:4],'move_label':label,
          'explanation':'기록된 정답 수순의 현재 착수입니다. 다른 최선 수가 있을 수 있습니다.'}
 @app.post('/api/v9/{kind}/move')
 def move(kind:str,body:MoveBody,authorization:str|None=Header(default=None)):
  if kind not in ('course','puzzle'):raise HTTPException(400,'잘못된 종류')
  code=account(authorization);state=get_state(code);task=get_session(state,kind)
  if task.get('done'):raise HTTPException(409,'이미 완료된 세션입니다.')
  if task.get('awaiting_next'):raise HTTPException(409,'다음 문제 버튼을 눌러주세요.')
  p=LIB[task['ids'][task['index']]];b=chess.Board(p['fen'])
  for u in p['moves'][:task['offset']]:b.push_uci(u)
  if body.session_id is not None and body.session_id!=task.get('session_id'):raise HTTPException(409,'문제 세션이 변경되었습니다. 새 문제를 시작하세요.')
  if body.expected_fen is not None and body.expected_fen!=b.fen():raise HTTPException(409,'문제 위치가 변경되었습니다. 새 문제를 시작하세요.')
  try:m=chess.Move.from_uci(body.move)
  except (ValueError,TypeError):raise HTTPException(400,'잘못된 착수 형식')
  if m not in b.legal_moves:raise HTTPException(400,'합법적으로 이동할 수 없는 수입니다.')
  expected=p['moves'][task['offset']]
  if m.uci()!=expected and not (any(t.startswith('mateIn') for t in p['themes']) and _is_alternative_mate(b,m,p,task)):
   task['attempted']=True;task['wrong_moves']=task.get('wrong_moves',0)+1;save_state(code,state)
   return {'correct':False,'message':'합법적인 착수이지만 이 퍼즐의 검증된 정답 수순과 다릅니다. 다른 동등한 최선 수가 있을 가능성은 별도 엔진 분석이 필요합니다.',
           'can_retry':True,**task_payload(task)}
  b.push(m);task['offset']+=1
  if b.is_checkmate():
   # A proven terminal alternative has no remaining opponent reply.
   task['offset']=len(p['moves'])
  if task['offset']<len(p['moves']):
   response=p['moves'][task['offset']]
   b.push_uci(response);task['offset']+=1
  else:response=None
  if task['offset']<len(p['moves']):
   save_state(code,state)
   return {'correct':True,'solved':False,'reply':response,'message':'맞는 수입니다. 상대의 응수를 확인하고 다음 수를 찾아보세요.',**task_payload(task)}
  if not task['attempted']:task['correct_count']+=1
  # Reset per-puzzle flags only after persisting the result.
  state.setdefault('puzzle_results',[]).append({'source':'lichess','puzzle_id':p['id'],
      'correct':True,'first_try_correct':not task['attempted'],'hint_used':bool(task.get('hint_used')),'wrong_moves':task.get('wrong_moves',0),'course':kind=='course','at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()})
  task['index']+=1;task['offset']=1;task['attempted']=False;task['hint_used']=False;task['wrong_moves']=0;task['awaiting_next']=True
  task['done']=task['index']>=len(task['ids'])
  if task['done'] and kind=='course':
   item={'theme':task['theme'],'level':task['level'],'attempts':15,'first_try':task['correct_count'],
         'mastered':task['correct_count']>=12}
   state.setdefault('v9_course_history',[]).append(item)
  result={'session_id':task.get('session_id'),'correct':True,'solved':True,'done':task['done'],'reply':response,'completed_fen':b.fen(),
          'correct_count':task['correct_count'],'index':task['index'],'total':len(task['ids']),
          'mastered':task['done'] and task['correct_count']>=12,
          'message':'수순 해결 완료. 다음 문제로 진행하세요.' if not task['done'] else ('랜덤 퍼즐 해결 완료!' if kind=='puzzle' else '15문제 세션 완료!')}
  if any(t.startswith('mateIn') for t in p['themes']):
   result['mate_explanation']=explain_mate(b)
   result['mate_explanation']['source']='실제로 해결한 최종 위치 · 대체 메이트 착수 포함'
  task['last_result']=result
  save_state(code,state)
  return result
 @app.post('/api/v9/{kind}/next')
 def next_task(kind:str,authorization:str|None=Header(default=None)):
  if kind not in ('course','puzzle'):raise HTTPException(400,'잘못된 종류')
  code=account(authorization);s=get_state(code);t=get_session(s,kind)
  if t.get('done'):return {'done':True,'correct_count':t['correct_count'],'total':len(t['ids'])}
  if not t.get('awaiting_next'):raise HTTPException(409,'현재 문제의 정답 수순을 먼저 완료하세요.')
  t['awaiting_next']=False;save_state(code,s)
  # Re-opening a completed item is forbidden; next only when the solver has finished.
  if t['offset']!=1:raise HTTPException(409,'현재 문제를 먼저 완료해야 합니다.')
  return task_payload(t)
 @app.get('/api/v9/progress')
 def progress(authorization:str|None=Header(default=None)):
  s=get_state(account(authorization))
  return {'courses':s.get('v9_course_history',[])}
