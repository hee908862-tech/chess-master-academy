import os, json, secrets, hashlib, hmac, sqlite3, random, threading, time
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import chess
import chess.engine
from exercises import bank as exercise_bank, public as public_exercise

ROOT=Path(__file__).resolve().parent
DATABASE_URL=os.getenv('DATABASE_URL','')
SQLITE_FILE=os.getenv('SQLITE_FILE',str(ROOT/'chess_data.sqlite3'))
STOCKFISH_PATH=os.getenv('STOCKFISH_PATH','')
if DATABASE_URL:
 import psycopg
 from psycopg.rows import dict_row

_db_lock=threading.RLock()

@contextmanager
def db():
 with _db_lock:
  if DATABASE_URL:
   conn=psycopg.connect(DATABASE_URL, row_factory=dict_row)
  else:
   conn=sqlite3.connect(SQLITE_FILE)
   conn.row_factory=sqlite3.Row
  try:
   yield conn
   conn.commit()
  except:
   conn.rollback();raise
  finally:
   conn.close()

def execute(conn,query,args=()):
 if DATABASE_URL: query=query.replace('?','%s')
 return conn.execute(query,args)

def initdb():
 with db() as c:
  execute(c,'CREATE TABLE IF NOT EXISTS accounts (code TEXT PRIMARY KEY, pin_hash TEXT NOT NULL, salt TEXT NOT NULL, created TEXT NOT NULL)')
  execute(c,'CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, code TEXT NOT NULL, created INTEGER NOT NULL)')
  execute(c,'CREATE TABLE IF NOT EXISTS progress (code TEXT PRIMARY KEY, state TEXT NOT NULL)')

initdb()
app=FastAPI(title='Chess Master Academy')

class AccountBody(BaseModel):
 code:str=Field(min_length=4,max_length=24)
 pin:str=Field(min_length=6,max_length=72)

class MoveBody(BaseModel):
 from_sq:str
 to_sq:str
 promotion:str='q'

class PuzzleBody(BaseModel):
 puzzle_id:int
 move:str

class LessonBody(BaseModel):
 lesson_id:str

def clean_code(code):
 code=code.strip().upper()
 if not 4<=len(code)<=24 or not all(c.isascii() and (c.isalnum() or c in '-_') for c in code):
  raise HTTPException(400,'개인 코드는 영문·숫자·-·_ 조합 4~24자로 입력하세요.')
 return code

def hash_pin(pin,salt):return hashlib.scrypt(pin.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()

def blank_state():return {'games':[],'active_game':None,'puzzle_results':[],'completed_lessons':[],'assessment':None,'exercise_history':{},'practice':None,'test':None,'lesson_attempts':[]}

def get_state(code):
 with db() as c:
  r=execute(c,'SELECT state FROM progress WHERE code=?',(code,)).fetchone()
 return json.loads(r['state']) if r else blank_state()

def save_state(code,state):
 serialized=json.dumps(state,ensure_ascii=False)
 with db() as c:
  execute(c,'DELETE FROM progress WHERE code=?',(code,))
  execute(c,'INSERT INTO progress(code,state) VALUES(?,?)',(code,serialized))

def auth(authorization):
 token=authorization.removeprefix('Bearer ').strip() if authorization else ''
 if not token:raise HTTPException(401,'로그인이 필요합니다.')
 with db() as c:
  r=execute(c,'SELECT code FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
 if not r:raise HTTPException(401,'로그인이 만료됐습니다.')
 return r['code']

def issue_token(code):
 token=secrets.token_urlsafe(36)
 with db() as c:
  execute(c,'INSERT INTO sessions(token_hash,code,created) VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),code,int(time.time())))
 return {'token':token,'code':code}

@app.post('/api/register')
def register(body:AccountBody):
 code=clean_code(body.code)
 salt=secrets.token_hex(16)
 try:
  with db() as c:
   execute(c,'INSERT INTO accounts(code,pin_hash,salt,created) VALUES(?,?,?,?)',(code,hash_pin(body.pin,salt),salt,datetime.now(timezone.utc).isoformat()))
 except Exception:
  raise HTTPException(409,'이미 사용 중인 코드입니다. 다른 코드를 선택하세요.')
 save_state(code,blank_state())
 return issue_token(code)

@app.post('/api/login')
def login(body:AccountBody):
 code=clean_code(body.code)
 with db() as c:
  r=execute(c,'SELECT pin_hash,salt FROM accounts WHERE code=?',(code,)).fetchone()
 if not r or not hmac.compare_digest(r['pin_hash'],hash_pin(body.pin,r['salt'])):
  raise HTTPException(401,'코드 또는 PIN이 올바르지 않습니다.')
 return issue_token(code)

@app.post('/api/logout')
def logout(authorization:str|None=Header(default=None)):
 token=authorization.removeprefix('Bearer ').strip() if authorization else ''
 if token:
  with db() as c: execute(c,'DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
 return {'ok':True}

@app.get('/api/me')
def me(authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code)
 games=state.get('games',[])
 wins=sum(g['result']=='win' for g in games)
 losses=sum(g['result']=='loss' for g in games)
 draws=sum(g['result']=='draw' for g in games)
 attempts=state.get('puzzle_results',[])
 solved=sum(bool(r.get('correct')) for r in attempts)
 return {'code':code,'state':state,'stats':{'games':len(games),'wins':wins,'losses':losses,'draws':draws,'puzzles':len(attempts),'solved':solved},'engine':'stockfish' if STOCKFISH_PATH and Path(STOCKFISH_PATH).exists() else 'fallback'}

PIECE_SCORE={chess.PAWN:100,chess.KNIGHT:320,chess.BISHOP:335,chess.ROOK:500,chess.QUEEN:900,chess.KING:0}
def positional_score(board):
 value=0
 for square,p in board.piece_map().items():
  r=chess.square_rank(square);f=chess.square_file(square)
  bonus=(3.5-abs(f-3.5))*3+(3.5-abs(r-3.5))*3
  if p.piece_type==chess.PAWN:bonus+=(r if p.color else 7-r)*3
  value+=(PIECE_SCORE[p.piece_type]+bonus)*(1 if p.color==chess.WHITE else -1)
 if board.is_checkmate(): return -100000 if board.turn==chess.WHITE else 100000
 return value

def fallback_ai(board,depth=2):
 def search(b,d,alpha,beta):
  if d==0 or b.is_game_over(claim_draw=True):return positional_score(b)
  moves=list(b.legal_moves)
  moves.sort(key=lambda m: 1000 if b.is_capture(m) else 0,reverse=True)
  if b.turn:
   best=-1e9
   for m in moves:
    b.push(m);v=search(b,d-1,alpha,beta);b.pop();best=max(best,v);alpha=max(alpha,best)
    if alpha>=beta:break
   return best
  best=1e9
  for m in moves:
   b.push(m);v=search(b,d-1,alpha,beta);b.pop();best=min(best,v);beta=min(beta,best)
   if beta<=alpha:break
  return best
 moves=list(board.legal_moves)
 random.shuffle(moves)
 moves.sort(key=lambda m:1000 if board.is_capture(m) else 0,reverse=True)
 scored=[]
 for m in moves:
  board.push(m);sc=search(board,depth-1,-1e9,1e9);board.pop();scored.append((sc,m))
 if not scored:return None
 return min(scored,key=lambda x:x[0])[1]

def ai_move(board):
 if STOCKFISH_PATH and Path(STOCKFISH_PATH).exists():
  try:
   with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH,timeout=8) as engine:
    return engine.play(board,chess.engine.Limit(time=.25)).move
  except Exception: pass
 return fallback_ai(board)

def serialize_board(board):
 positions={chess.square_name(s):p.symbol() for s,p in board.piece_map().items()}
 return {'fen':board.fen(),'turn':'white' if board.turn else 'black','squares':positions,'legal':[{'from':chess.square_name(m.from_square),'to':chess.square_name(m.to_square),'promotion':chess.piece_symbol(m.promotion) if m.promotion else None} for m in board.legal_moves] if board.turn==chess.WHITE else [],'is_over':board.is_game_over(claim_draw=True),'result':board.result(claim_draw=True),'check':board.is_check(),'last_move':board.peek().uci() if board.move_stack else None,'ply':len(board.move_stack)}

def reconstruct(game):
 b=chess.Board()
 for uci in game['moves']:b.push_uci(uci)
 return b

def store_finished(state,board):
 result=board.result(claim_draw=True)
 outcome='win' if result=='1-0' else 'loss' if result=='0-1' else 'draw'
 active=state['active_game']
 state['games'].append({'result':outcome,'moves':active['moves'],'ended':datetime.now(timezone.utc).isoformat(),'engine':active['engine']})
 state['active_game']=None

@app.post('/api/game/new')
def new_game(authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code)
 state['active_game']={'moves':[],'engine':'stockfish' if STOCKFISH_PATH and Path(STOCKFISH_PATH).exists() else 'fallback'}
 save_state(code,state)
 return {'board':serialize_board(chess.Board()),'message':'새 대국을 시작했습니다. 백으로 플레이합니다.'}

@app.get('/api/game')
def game(authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code)
 if not state['active_game']:return {'active':False}
 return {'active':True,'board':serialize_board(reconstruct(state['active_game']))}

@app.post('/api/game/move')
def move(body:MoveBody,authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code)
 active=state['active_game']
 if not active:raise HTTPException(400,'진행 중인 대국이 없습니다.')
 board=reconstruct(active)
 if board.turn!=chess.WHITE:raise HTTPException(400,'현재 AI 차례입니다.')
 try:
  candidate=chess.Move.from_uci(body.from_sq+body.to_sq+(body.promotion if board.piece_at(chess.parse_square(body.from_sq)) and board.piece_at(chess.parse_square(body.from_sq)).piece_type==chess.PAWN and chess.square_rank(chess.parse_square(body.to_sq))==7 else ''))
 except ValueError: raise HTTPException(400,'올바른 이동 좌표가 아닙니다.')
 if candidate not in board.legal_moves: raise HTTPException(400,'체스 규칙상 이동할 수 없는 칸입니다.')
 active['moves'].append(candidate.uci());board.push(candidate)
 ai_uci=None
 if not board.is_game_over(claim_draw=True):
  ai=ai_move(board)
  if ai:
   ai_uci=ai.uci();active['moves'].append(ai_uci);board.push(ai)
 finished=board.is_game_over(claim_draw=True)
 if finished:store_finished(state,board)
 save_state(code,state)
 return {'board':serialize_board(board),'ai_move':ai_uci,'finished':finished}

@app.post('/api/game/resign')
def resign(authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code)
 if not state['active_game']:raise HTTPException(400,'대국이 없습니다.')
 active=state['active_game']
 state['games'].append({'result':'loss','moves':active['moves'],'ended':datetime.now(timezone.utc).isoformat(),'engine':active['engine'],'resigned':True})
 state['active_game']=None;save_state(code,state)
 return {'ok':True}

# Curated tactical puzzle positions. Solver must make an exact verified legal move.
PUZZLES=[
 {'fen':'4k3/8/8/8/3q4/8/4Q3/4K3 w - - 0 1','move':'e2e4','theme':'퀸 이동','difficulty':'입문','description':'백 차례: 퀸으로 안전한 칸에 이동하세요.','hint':'퀸은 직선 및 대각선으로 움직입니다.'},
 {'fen':'4k3/8/8/8/8/8/6R1/6K1 w - - 0 1','move':'g2g8','theme':'룩으로 체크','difficulty':'입문','description':'백 차례: 룩으로 체크를 걸어보세요.','hint':'룩은 행과 열을 따라 이동합니다.'},
 {'fen':'4k3/8/8/8/5q2/8/4N3/4K3 w - - 0 1','move':'e2f4','theme':'나이트 기물 포획','difficulty':'초급','description':'백 차례: 공격받는 기물을 잡는 수를 찾으세요.','hint':'나이트는 ㄱ자 모양으로 움직입니다.'},
 {'fen':'7k/8/5K2/8/8/8/8/6R1 w - - 0 1','move':'g1g8','theme':'룩 체크','difficulty':'초급','description':'백 차례: 상대 킹에게 체크를 거는 수를 찾으세요.','hint':'룩을 같은 열 끝까지 움직일 수 있습니다.'},
]
for p in PUZZLES:
 try:
  assert chess.Move.from_uci(p['move']) in chess.Board(p['fen']).legal_moves, p
 except Exception as exc: print('PUZZLE ERROR',exc)

class ExerciseAnswer(BaseModel):
 exercise_id:int
 move:str

class LessonAnswer(BaseModel):
 lesson_id:str
 choice:int

class TestAnswer(BaseModel):
 question_id:int
 move:str

LESSON_QUIZZES={
 'rules':[('체크 상태에서 가장 먼저 해야 할 일은?', ['폰을 아무 칸에 둔다','반드시 체크를 벗어난다','킹을 두 칸 전진한다','무조건 캐슬링한다'],1),('체크메이트의 의미는?', ['퀸을 잃음','킹이 잡힘','합법적으로 체크를 벗어날 수 없음','상대가 3수 연속 체크'],2),('나이트는 어떤 경로로 움직이나요?', ['대각선만','L자 이동','한 칸씩 직선','다른 말처럼 직선'],1)],
 'capture':[('룩의 대략적인 상대 가치?', ['폰 1개','폰 3개','폰 5개','폰 10개'],2),('유리한 기물 교환을 판단할 때 중요한 것?', ['잡은 뒤 다시 잡히는지','기물 색깔','말을 빨리 두는지','중앙 무조건 진입'],0),('퀸 가치와 가장 가까운 것은?', ['1','3','5','9'],3)],
 'tactics':[('하나의 기물로 두 목표를 동시에 공격하는 전술은?', ['포크','캐슬링','앙파상','오포지션'],0),('상대 기물이 움직이면 뒤의 고가치 기물이 노출되는 전술은?', ['프로모션','핀','스테일메이트','체크메이트'],1),('룩이 퀸을 가로지르는 선에서 왕을 먼저 공격한 뒤 퀸을 잡는 전술?', ['스큐어','템포','오포지션','피앙케토'],0)],
 'calculation':[('수를 계산할 때 먼저 확인할 강제수는?', ['임의의 폰 이동','체크·잡기·위협','가장 화려한 희생','킹 전진'],1),('후보수 비교 시 상대 응수는?', ['상대가 가장 실수하는 수','가장 강한 응수','임의의 한 수','고려하지 않음'],1),('수읽기에서 중요한 습관은?', ['첫 생각대로 즉시 착수','후속 수순까지 확인','무조건 퀸 교환','오프닝 수순만 외움'],1)],
 'endgame':[('킹과 폰 엔드게임에서 킹은?', ['절대 움직이지 않음','활동적으로 참여','바로 희생','룩 뒤에 숨어 있음'],1),('오포지션은 주로 무엇과 관련?', ['킹의 마주 보는 위치','나이트의 이동','캐슬링','앙파상'],0),('폰 승격 조건은?', ['상대 폰을 두 개 잡음','맨 마지막 랭크 도달','중앙에서 두 칸 전진','킹 옆에 둠'],1)],
 'opening':[('오프닝 주요 원칙 중 하나?', ['중앙 통제','퀸 반복 이동','킹 노출','기물 희생 강제'],0),('일반적으로 경량 기물 전개 이유는?', ['중앙과 중요 칸 통제','상대를 혼란시키기만','무조건 폰 잡기','무조건 퀸 교환'],0),('초반 캐슬링의 주된 목적은?', ['킹 안전','즉시 체크메이트','기물 승격','폰 이동 증가'],0)],
 'review':[('복기 때 가장 먼저 찾으면 좋은 것은?', ['결정적인 실수','기물 색','상대의 닉네임','착수음'],0),('엔진 최선의 수를 볼 때 중요한 것은?', ['이유와 후속 수순 이해','무조건 암기','수치만 기록','분석 없이 넘김'],0),('같은 유형 실수가 반복된다면?', ['유형별 훈련에 반영','무시','난이도만 올림','대국 기록 삭제'],0)],
}

# This endpoint is retained as a non-answer-leaking practice index for older clients.
@app.get('/api/puzzles')
def puzzles(authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code);items=exercise_bank()
 history=state.get('exercise_history',{})
 return [{**public_exercise(items[i],i),'solved':history.get(str(i),{}).get('correct',0)>0} for i in range(min(len(items),24))]

@app.post('/api/puzzle/solve')
def solve(body:PuzzleBody,authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code);items=exercise_bank()
 if not 0<=body.puzzle_id<len(items):raise HTTPException(404,'퍼즐이 없습니다.')
 p=items[body.puzzle_id]
 try: legal=chess.Move.from_uci(body.move) in chess.Board(p['fen']).legal_moves
 except Exception:legal=False
 correct=legal and body.move in p['answers']
 state.setdefault('puzzle_results',[]).append({'puzzle_id':body.puzzle_id,'correct':correct,'at':datetime.now(timezone.utc).isoformat()})
 entry=state.setdefault('exercise_history',{}).setdefault(str(body.puzzle_id),{'correct':0,'incorrect':0})
 entry['correct' if correct else 'incorrect']+=1
 save_state(code,state)
 return {'correct':correct,'explanation':'정답입니다. '+p['theme']+' 전술을 이해하고 다른 문제에 적용하세요.' if correct else '다른 후보수를 찾아보세요. 상대의 가장 강한 응수를 확인하세요.'}

@app.post('/api/practice/next')
def next_exercise(authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code);items=exercise_bank()
 if not items:raise HTTPException(503,'문제은행을 생성하지 못했습니다.')
 history=state.setdefault('exercise_history',{})
 used=state.setdefault('practice_seen',[])
 if len(used)>=len(items):used=[];state['practice_seen']=used
 candidates=[i for i in range(len(items)) if i not in used]
 # Prefer unmastered and previously missed variants, but avoid same question until pool cycle.
 weights=[5 if str(i) not in history else (3 if history[str(i)].get('incorrect',0)>history[str(i)].get('correct',0) else 1) for i in candidates]
 index=random.choices(candidates,weights=weights,k=1)[0]
 used.append(index)
 state['practice']={'id':index,'issued':int(time.time()),'attempted':False}
 save_state(code,state)
 return public_exercise(items[index],index)

@app.post('/api/practice/answer')
def answer_exercise(body:ExerciseAnswer,authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code);session=state.get('practice')
 if not session or session.get('attempted') or session['id']!=body.exercise_id:raise HTTPException(409,'활성 퍼즐이 아니거나 이미 채점되었습니다.')
 p=exercise_bank()[body.exercise_id]
 try:legal=chess.Move.from_uci(body.move) in chess.Board(p['fen']).legal_moves
 except Exception:legal=False
 correct=legal and body.move in p['answers']
 session['attempted']=True
 entry=state.setdefault('exercise_history',{}).setdefault(str(body.exercise_id),{'correct':0,'incorrect':0})
 entry['correct' if correct else 'incorrect']+=1
 state.setdefault('puzzle_results',[]).append({'puzzle_id':body.exercise_id,'correct':correct,'at':datetime.now(timezone.utc).isoformat()})
 save_state(code,state)
 return {'correct':correct,'explanation':('정답입니다. ' if correct else '정답은 '+p['answers'][0]+' 입니다. ')+p['theme']+' 개념을 다른 포지션에도 적용해 보세요.','answer':p['answers'][0]}

@app.post('/api/test/start')
def start_test(authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code);items=exercise_bank()
 if len(items)<12:raise HTTPException(503,'평가 문제 수가 충분하지 않습니다.')
 history=state.get('test_seen',[])
 unseen=[i for i in range(len(items)) if i not in history]
 if len(unseen)<12:history=[];unseen=list(range(len(items)))
 chosen=random.sample(unseen,12)
 state['test']={'ids':chosen,'index':0,'correct':0,'mistakes':[],'started':int(time.time())}
 state['test_seen']=(history+chosen)[-min(len(items),240):]
 save_state(code,state)
 return {'total':12,'index':0,'question':public_exercise(items[chosen[0]],chosen[0])}

@app.post('/api/test/answer')
def test_answer(body:TestAnswer,authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code);test=state.get('test')
 if not test:raise HTTPException(409,'진행 중인 평가가 없습니다.')
 idx=test['index']
 if idx>=len(test['ids']) or test['ids'][idx]!=body.question_id:raise HTTPException(409,'현재 평가 문항이 아닙니다.')
 p=exercise_bank()[body.question_id]
 correct=body.move in p['answers']
 test['correct']+=int(correct)
 if not correct:test['mistakes'].append({'theme':p['theme'],'id':body.question_id})
 test['index']+=1
 if test['index']<len(test['ids']):
  next_id=test['ids'][test['index']]
  save_state(code,state)
  return {'done':False,'correct':correct,'index':test['index'],'total':len(test['ids']),'question':public_exercise(exercise_bank()[next_id],next_id)}
 result={'correct':test['correct'],'total':len(test['ids']),'stage':('입문자' if test['correct']<3 else '초급자' if test['correct']<7 else '중급 진입' if test['correct']<10 else '전술 숙련'),'confidence':'예비 진단','weaknesses':list(dict.fromkeys(m['theme'] for m in test['mistakes'])),'at':datetime.now(timezone.utc).isoformat()}
 state['assessment']=result
 state['test']=None
 save_state(code,state)
 return {'done':True,'correct':correct,'result':result}

@app.get('/api/lessons/quiz/{lesson_id}')
def lesson_quiz(lesson_id:str,authorization:str|None=Header(default=None)):
 code=auth(authorization)
 if lesson_id not in LESSON_QUIZZES:raise HTTPException(404,'강의가 없습니다.')
 state=get_state(code)
 attempts=state.get('lesson_attempts',[])
 seen=sum(1 for a in attempts if a['lesson_id']==lesson_id)
 index=seen%len(LESSON_QUIZZES[lesson_id])
 question,choices,_=LESSON_QUIZZES[lesson_id][index]
 state['lesson_quiz']={'lesson_id':lesson_id,'index':index}
 save_state(code,state)
 return {'lesson_id':lesson_id,'question':question,'choices':choices,'remaining':3-index}

@app.post('/api/lessons/answer')
def lesson_answer(body:LessonAnswer,authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code);active=state.get('lesson_quiz')
 if not active or active['lesson_id']!=body.lesson_id:raise HTTPException(409,'먼저 학습 확인 문제를 열어주세요.')
 index=active['index'];expected=LESSON_QUIZZES[body.lesson_id][index][2]
 correct=body.choice==expected
 state.setdefault('lesson_attempts',[]).append({'lesson_id':body.lesson_id,'question':index,'correct':correct,'at':datetime.now(timezone.utc).isoformat()})
 state['lesson_quiz']=None
 # Need all 3 recent distinct questions correct before marking complete. Failures reset progress.
 recent=[a for a in state['lesson_attempts'] if a['lesson_id']==body.lesson_id]
 streak=[]
 for r in reversed(recent):
  if not r['correct']:break
  streak.append(r['question'])
 completed=len(set(streak))==3
 if completed and body.lesson_id not in state.setdefault('completed_lessons',[]):state['completed_lessons'].append(body.lesson_id)
 save_state(code,state)
 return {'correct':correct,'completed':completed,'progress':len(set(streak)),'message':'정답입니다.' if correct else '오답입니다. 핵심 개념을 확인하고 다시 풀어보세요.'}

LESSONS={
 'rules':'기초 규칙과 기물 이동',
 'tactics':'포크·핀·스큐어',
 'calculation':'2~3수 계산하기',
 'endgame':'킹·폰 엔드게임 기초',
 'opening':'오프닝 4대 원칙',
 'review':'대국 복기 습관',
}
@app.post('/api/lesson/complete')
def complete_lesson_disabled():
 raise HTTPException(410,'교육 완료는 이해도 확인 문제 3개를 연속 통과해야 인정됩니다.')

@app.get('/api/health')
def health():return {'ok':True,'engine':'stockfish' if STOCKFISH_PATH and Path(STOCKFISH_PATH).exists() else 'fallback'}

app.mount('/assets',StaticFiles(directory=str(ROOT/'public')),name='assets')
@app.get('/')
def index():return FileResponse(ROOT/'public'/'index.html')
