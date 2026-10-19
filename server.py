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
 code:str
 pin:str

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
 if not 6<=len(body.pin)<=72:raise HTTPException(400,'PIN은 6~72자로 입력하세요.')
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
 if not 6<=len(body.pin)<=72:raise HTTPException(400,'PIN은 6~72자로 입력하세요.')
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
 return {'code':code,'state':{'completed_lessons':state.get('completed_lessons',[]),'assessment':state.get('assessment')},'stats':{'games':len(games),'wins':wins,'losses':losses,'draws':draws,'puzzles':len(attempts),'solved':solved},'engine':'stockfish' if STOCKFISH_PATH and Path(STOCKFISH_PATH).exists() else 'fallback'}

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
 return (max(scored,key=lambda x:x[0]) if board.turn==chess.WHITE else min(scored,key=lambda x:x[0]))[1]

def ai_move(board,level=5):
 if STOCKFISH_PATH and Path(STOCKFISH_PATH).exists():
  try:
   with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH,timeout=8) as engine:
    
    try:
     engine.configure({'UCI_LimitStrength':True,'UCI_Elo':max(1320,min(3000,800+int(level)*220))})
    except Exception: pass
    return engine.play(board,chess.engine.Limit(time=.07+int(level)*.065)).move
  except Exception: pass
 return fallback_ai(board,depth=1 if int(level)<=2 else 2 if int(level)<=6 else 3)

def serialize_board(board,player_color='white'):
 positions={chess.square_name(s):p.symbol() for s,p in board.piece_map().items()}
 return {'fen':board.fen(),'turn':'white' if board.turn else 'black','squares':positions,'legal':[{'from':chess.square_name(m.from_square),'to':chess.square_name(m.to_square),'promotion':chess.piece_symbol(m.promotion) if m.promotion else None} for m in board.legal_moves] if board.turn==(chess.WHITE if player_color=='white' else chess.BLACK) else [],'is_over':board.is_game_over(claim_draw=True),'result':board.result(claim_draw=True),'check':board.is_check(),'last_move':board.peek().uci() if board.move_stack else None,'ply':len(board.move_stack)}

def reconstruct(game):
 b=chess.Board()
 for uci in game['moves']:b.push_uci(uci)
 return b

def store_finished(state,board):
 result=board.result(claim_draw=True)
 outcome='win' if result==('1-0' if state['active_game'].get('color','white')=='white' else '0-1') else 'loss' if result in ('1-0','0-1') else 'draw'
 active=state['active_game']
 state['games'].append({'result':outcome,'moves':active['moves'],'ended':datetime.now(timezone.utc).isoformat(),'engine':active['engine'],'color':active.get('color','white'),'difficulty':active.get('difficulty',5),'started':active.get('started')})
 state['active_game']=None

class NewGameBody(BaseModel):
 color:str='white'
 difficulty:int=Field(default=5,ge=1,le=10)

@app.post('/api/game/new')
def new_game(body:NewGameBody,authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code)
 if body.color not in ('white','black'):raise HTTPException(400,'백 또는 흑을 선택해 주세요.')
 state['active_game']={'moves':[],'color':body.color,'engine':'stockfish' if STOCKFISH_PATH and Path(STOCKFISH_PATH).exists() else 'fallback','difficulty':body.difficulty,'started':datetime.now(timezone.utc).isoformat()}
 board=chess.Board()
 if body.color=='black':
  first=ai_move(board,body.difficulty)
  if first:
   board.push(first);state['active_game']['moves'].append(first.uci())
 save_state(code,state)
 return {'board':serialize_board(board,body.color),'player_color':body.color,'message':'새 대국을 시작했습니다. '+('백' if body.color=='white' else '흑')+'으로 플레이합니다.'}

@app.get('/api/game')
def game(authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code)
 if not state['active_game']:return {'active':False}
 return {'active':True,'board':serialize_board(reconstruct(state['active_game']),state['active_game'].get('color','white')),'player_color':state['active_game'].get('color','white')}

@app.post('/api/game/move')
def move(body:MoveBody,authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code)
 active=state['active_game']
 if not active:raise HTTPException(400,'진행 중인 대국이 없습니다.')
 board=reconstruct(active)
 color=active.get('color','white')
 player_side=chess.WHITE if color=='white' else chess.BLACK
 if board.turn!=player_side:raise HTTPException(400,'현재 AI 차례입니다.')
 try:
  candidate=chess.Move.from_uci(body.from_sq+body.to_sq+(body.promotion if board.piece_at(chess.parse_square(body.from_sq)) and board.piece_at(chess.parse_square(body.from_sq)).piece_type==chess.PAWN and chess.square_rank(chess.parse_square(body.to_sq))==(7 if player_side else 0) else ''))
 except ValueError: raise HTTPException(400,'올바른 이동 좌표가 아닙니다.')
 if candidate not in board.legal_moves: raise HTTPException(400,'체스 규칙상 이동할 수 없는 칸입니다.')
 active['moves'].append(candidate.uci());board.push(candidate)
 ai_uci=None
 if not board.is_game_over(claim_draw=True):
  ai=ai_move(board,active.get('difficulty',5))
  if ai:
   ai_uci=ai.uci();active['moves'].append(ai_uci);board.push(ai)
 finished=board.is_game_over(claim_draw=True)
 if finished:store_finished(state,board)
 save_state(code,state)
 return {'board':serialize_board(board,color),'ai_move':ai_uci,'finished':finished,'player_color':color}

@app.post('/api/game/resign')
def resign(authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code)
 if not state['active_game']:raise HTTPException(400,'대국이 없습니다.')
 active=state['active_game']
 state['games'].append({'result':'loss','moves':active['moves'],'ended':datetime.now(timezone.utc).isoformat(),'engine':active['engine'],'resigned':True,'color':active.get('color','white'),'difficulty':active.get('difficulty',5),'started':active.get('started')})
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
 if lesson_id not in get_state(code).get('guided_passed',[]):raise HTTPException(409,'체스판 실습을 먼저 완료하세요.')
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
@app.get('/favicon.ico')
def favicon_ico():return FileResponse(ROOT/'public'/'favicon.svg',media_type='image/svg+xml')

@app.get('/favicon.svg')
def favicon():return FileResponse(ROOT/'public'/'favicon.svg',media_type='image/svg+xml')

@app.get('/')
def index():return FileResponse(ROOT/'public'/'index.html')

# ===== V3 guided scenarios and multi-domain assessment =====
from assessment_v3 import exam_bank, DOMAINS
from lesson_scenarios import SCENARIOS

class GuidedMove(BaseModel):
 lesson_id:str
 move:str

@app.post('/api/guided/start/{lesson_id}')
def guided_start(lesson_id:str,authorization:str|None=Header(default=None)):
 code=auth(authorization)
 if lesson_id not in SCENARIOS:raise HTTPException(404,'교육이 없습니다.')
 state=get_state(code)
 state['guided']={'lesson_id':lesson_id,'index':0,'complete':False}
 save_state(code,state)
 s=SCENARIOS[lesson_id][0]
 return {'index':0,'total':len(SCENARIOS[lesson_id]),'fen':s['fen'],'prompt':s['prompt'],'legal':[m.uci() for m in chess.Board(s['fen']).legal_moves]}

@app.post('/api/guided/move')
def guided_move(body:GuidedMove,authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code);g=state.get('guided')
 if not g or g['lesson_id']!=body.lesson_id or g.get('complete'):raise HTTPException(409,'활성 실습이 아닙니다.')
 scenarios=SCENARIOS[body.lesson_id];s=scenarios[g['index']]
 b=chess.Board(s['fen'])
 try: move=chess.Move.from_uci(body.move)
 except ValueError:move=None
 correct=move in b.legal_moves and body.move==s['answer']
 if not correct:return {'correct':False,'message':'다른 수를 고려해 보세요. 목표를 확인하고 다시 시도해 보세요.','index':g['index']}
 g['index']+=1
 if g['index']>=len(scenarios):
  g['complete']=True
  state.setdefault('guided_passed',[])
  if body.lesson_id not in state['guided_passed']:state['guided_passed'].append(body.lesson_id)
  save_state(code,state)
  return {'correct':True,'done':True,'message':'실습 완료! 개념 확인 문제로 넘어갈 수 있습니다.'}
 s=scenarios[g['index']]
 save_state(code,state)
 return {'correct':True,'done':False,'index':g['index'],'total':len(scenarios),'fen':s['fen'],'prompt':s['prompt'],'legal':[m.uci() for m in chess.Board(s['fen']).legal_moves]}

# Require guided play before the legacy multiple-choice checks.
_old_quiz=lesson_quiz
@app.get('/api/lessons/quiz2/{lesson_id}')
def lesson_quiz_gate(lesson_id:str,authorization:str|None=Header(default=None)):
 code=auth(authorization)
 if lesson_id not in get_state(code).get('guided_passed',[]):raise HTTPException(409,'해당 교육의 체스판 실습을 먼저 완료해 주세요.')
 return _old_quiz(lesson_id,authorization)

class AssessmentMove(BaseModel):
 question_id:int
 move:str

@app.post('/api/assessment-v3/start')
def assessment_start(authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code)
 seed=secrets.randbits(32)
 questions=exam_bank(seed)
 state['assessment_v3']={'seed':seed,'index':0,'correct':{d:0 for d in DOMAINS},'move_log':[],'phase':'questions'}
 save_state(code,state)
 return assessment_question(questions,0)

def assessment_question(questions,idx):
 q=questions[idx]
 return {'phase':'questions','index':idx,'total':25,'domain':q['domain'],'question':{'id':idx,'fen':q['fen'],'description':q['description'],'legal':[m.uci() for m in chess.Board(q['fen']).legal_moves]}}

@app.post('/api/assessment-v3/answer')
def assessment_answer(body:AssessmentMove,authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code);t=state.get('assessment_v3')
 if not t or t['phase']!='questions':raise HTTPException(409,'활성 진단 문제가 없습니다.')
 idx=t['index']
 if idx!=body.question_id:raise HTTPException(409,'현재 문제가 아닙니다.')
 if t.get('pending_feedback'):
  return {'phase':'feedback','feedback':t['pending_feedback'],'index':idx,'total':25}
 questions=exam_bank(t['seed']);q=questions[idx];b=chess.Board(q['fen'])
 try:valid=chess.Move.from_uci(body.move) in b.legal_moves
 except ValueError:valid=False
 correct=valid and body.move in q['answers']
 t['correct'][q['domain']]+=int(correct)
 t['move_log'].append({'domain':q['domain'],'correct':correct})
 solution=(body.move if correct else next((u for u in q['answers'] if chess.Move.from_uci(u) in b.legal_moves),None))
 after=b.copy();
 if solution:after.push(chess.Move.from_uci(solution))
 feedback={'correct':correct,'submitted':body.move,'solution':solution,'answer_fen':after.fen(),'original_fen':q['fen'],'domain':q['domain'],'explanation':('선택한 수는 이 문항의 학습 목표에 부합합니다.' if correct else '녹색으로 표시된 정답 수순을 확인한 뒤 다음 문제로 이동하세요.'),'has_alternatives':len(q['answers'])>1}
 t['pending_feedback']=feedback
 save_state(code,state)
 return {'done':False,'phase':'feedback','feedback':feedback,'index':idx,'total':25}

def eval_for_white(board):
 if STOCKFISH_PATH and Path(STOCKFISH_PATH).exists():
  try:
   with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH,timeout=8) as engine:
    res=engine.analyse(board,chess.engine.Limit(time=.07))
    return res['score'].white().score(mate_score=10000)
  except Exception:pass
 return positional_score(board)

def medium_move(board):
 if STOCKFISH_PATH and Path(STOCKFISH_PATH).exists():
  try:
   with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH,timeout=8) as engine:
    engine.configure({'UCI_LimitStrength':True,'UCI_Elo':1500})
    return engine.play(board,chess.engine.Limit(time=.17)).move
  except Exception:pass
 return fallback_ai(board,depth=2)

@app.get('/api/assessment-v3/status')
def assessment_status(authorization:str|None=Header(default=None)):
 code=auth(authorization);t=get_state(code).get('assessment_v3')
 if not t:return {'active':False}
 if t.get('pending_feedback'):return {'active':True,'phase':'feedback','feedback':t['pending_feedback'],'index':t['index'],'total':25}
 if t['phase']=='game':return {'active':True,'phase':'game','board':serialize_board(reconstruct({'moves':t['game_moves']})),'white_moves':len(t['game_scores'])}
 return {'active':True,**assessment_question(exam_bank(t['seed']),t['index'])}

@app.post('/api/assessment-v3/game-move')
def assessment_game_move(body:MoveBody,authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code);t=state.get('assessment_v3')
 if not t or t['phase']!='game':raise HTTPException(409,'평가 대국을 진행 중이지 않습니다.')
 b=reconstruct({'moves':t['game_moves']})
 if b.turn!=chess.WHITE:raise HTTPException(409,'AI 차례입니다.')
 try:
  source=chess.parse_square(body.from_sq);dest=chess.parse_square(body.to_sq)
  pawn=b.piece_at(source)
  promote=body.promotion if pawn and pawn.piece_type==chess.PAWN and chess.square_rank(dest)==7 else ''
  m=chess.Move.from_uci(body.from_sq+body.to_sq+promote)
 except ValueError:raise HTTPException(400,'잘못된 좌표입니다.')
 if m not in b.legal_moves:raise HTTPException(400,'합법적으로 이동할 수 없는 칸입니다.')
 before=eval_for_white(b)
 b.push(m);t['game_moves'].append(m.uci())
 after=eval_for_white(b)
 t['game_scores'].append(max(0,min(500,before-after)))
 if not b.is_game_over(claim_draw=True):
  reply=medium_move(b)
  if reply:b.push(reply);t['game_moves'].append(reply.uci())
 done=b.is_game_over(claim_draw=True) or len(t['game_scores'])>=12
 if not done:
  save_state(code,state);return {'done':False,'board':serialize_board(b),'white_moves':len(t['game_scores']),'target_white_moves':12}
 counts=t['correct'];accuracy={d:round(counts[d]*20) for d in DOMAINS}
 avg_loss=round(sum(t['game_scores'])/max(1,len(t['game_scores'])))
 blunders=sum(x>=200 for x in t['game_scores'])
 inaccuracies=sum(50<=x<200 for x in t['game_scores'])
 game_strengths=[]
 game_weaknesses=[]
 if blunders==0:game_strengths.append('평가 대국에서 큰 실수 없음')
 else:game_weaknesses.append(f'큰 실수 {blunders}회 · 착수 전 상대 강제수 확인')
 if inaccuracies>=3:game_weaknesses.append('후보수 비교 및 기물 안전 확인 필요')
 strengths=[d for d in DOMAINS if accuracy[d]>=80]
 weaknesses=sorted(DOMAINS,key=lambda d:accuracy[d])[:2]
 # Internal readiness bands only; no Elo conversion claimed.
 overall=sum(accuracy.values())/5
 stage='입문자' if overall<35 else '초급자' if overall<60 else '중급 진입' if overall<80 else '전술 숙련'
 recommendations={'체크메이트':'메이트 패턴 연습','전술·포획':'포크·핀·기물 교환 훈련','오프닝 전개':'오프닝 원칙 실전 학습','킹·폰 엔드게임':'킹·폰 엔드게임','수읽기·강제수':'체크·잡기·위협 계산 연습'}
 result={'stage':stage,'skills':accuracy,'correct':sum(counts.values()),'total':25,'strengths':strengths,'game_strengths':game_strengths,'weaknesses':weaknesses,'game_weaknesses':game_weaknesses,'recommendations':[recommendations[d] for d in weaknesses], 'game':{'white_moves':len(t['game_scores']),'avg_evaluation_loss_cp':avg_loss,'blunders':blunders,'inaccuracies':inaccuracies,'evaluation_method':'Stockfish' if STOCKFISH_PATH and Path(STOCKFISH_PATH).exists() else '기본 휴리스틱','outcome':b.result(claim_draw=True) if b.is_game_over(claim_draw=True) else '12수 평가 구간 종료'},'item_log':t.get('move_log',[]),'confidence':'영역별 5문항 + 제한된 AI 대국에 기반한 비공식 예비 진단 · 공식 Elo 아님','at':datetime.now(timezone.utc).isoformat()}
 state['assessment']=result;state['assessment_v3']=None;save_state(code,state)
 return {'done':True,'phase':'results','board':serialize_board(b),'result':result}


# V4 playable opening courses: each move is legal and the opposite side is shown as a real response.
OPENING_LINES={
 'italian_white':{'name':'이탈리안 게임 · 백','color':'white','intro':'e4로 중앙을 차지하고 나이트와 비숍을 전개합니다. 흑의 ...e5, ...Nc6, ...Bc5에 대응하세요.','moves':['e2e4','e7e5','g1f3','b8c6','f1c4','f8c5','e1g1','g8f6'],'notes':['백: e4로 중앙을 확보합니다.','흑: ...e5로 중앙 균형을 맞춥니다.','백: Nf3는 e5를 압박하며 킹 쪽 기물을 전개합니다.','흑: ...Nc6로 e5폰을 보호합니다.','백: Bc4는 f7의 약점을 주시합니다.','흑: ...Bc5도 f2를 겨냥합니다.','백: O-O로 킹을 보호하고 룩을 중앙으로 연결할 준비를 합니다.','흑: ...Nf6가 e4를 공격합니다. 다음엔 d3나 Re1 등으로 e4를 보강할 수 있습니다.']},
 'italian_black':{'name':'이탈리안 게임 · 흑','color':'black','intro':'백의 e4, Nf3, Bc4에 ...e5, ...Nc6, ...Bc5로 대응하고 캐슬링합니다.','moves':['e2e4','e7e5','g1f3','b8c6','f1c4','f8c5','e1g1','g8f6'],'notes':['백: e4를 두어 중앙을 차지합니다.','흑: ...e5로 중앙을 견제합니다.','백: Nf3가 e5를 공격합니다.','흑: ...Nc6로 e5를 지키면서 전개합니다.','백: Bc4는 f7을 노립니다.','흑: ...Bc5로 대칭적으로 전개하며 f2에 압박을 줍니다.','백: O-O로 킹을 안전하게 합니다.','흑: ...Nf6는 e4를 공격합니다. 백의 d3 또는 Re1에 따라 다음 계획이 달라집니다.']},
 'queens_white':{'name':'퀸즈 갬빗 · 백','color':'white','intro':'d4, c4로 중앙을 압박하고, ...d5와 ...e6에 대해 자연스럽게 전개합니다.','moves':['d2d4','d7d5','c2c4','e7e6','b1c3','g8f6'],'notes':['백: d4로 중앙을 통제합니다.','흑: ...d5로 중앙을 맞섭니다.','백: c4는 d5를 압박하는 퀸즈 갬빗입니다.','흑: ...e6는 d5를 지키지만 c8비숍의 대각선을 제한합니다.','백: Nc3로 d5에 대한 압박을 강화합니다.','흑: ...Nf6로 전개하고 e4를 견제합니다.']},
 'queens_black':{'name':'퀸즈 갬빗 · 흑','color':'black','intro':'백의 d4, c4에 ...d5, ...e6, ...Nf6로 대응하는 퀸즈 갬빗 디클라인드를 실습합니다.','moves':['d2d4','d7d5','c2c4','e7e6','b1c3','g8f6'],'notes':['백: d4가 중앙을 차지합니다.','흑: ...d5로 대칭적으로 대응합니다.','백: c4로 d5 폰에 압박을 가합니다.','흑: ...e6로 d5를 유지하는 QGD 구조입니다.','백: Nc3으로 d5를 압박합니다.','흑: ...Nf6로 전개해 e4를 견제합니다.']},
 'sicilian_white':{'name':'시실리안 디펜스 · 백','color':'white','intro':'흑의 ...c5에 중앙 전개와 d4 브레이크로 대응합니다.','moves':['e2e4','c7c5','g1f3','d7d6','d2d4','c5d4','f3d4'],'notes':['백: e4로 중앙을 장악합니다.','흑: ...c5로 비대칭적인 중앙 압박을 만듭니다.','백: Nf3로 전개하며 d4를 준비합니다.','흑: ...d6가 e5를 지원합니다.','백: d4로 중앙을 개방합니다.','흑: ...cxd4로 중앙 폰을 교환합니다.','백: Nxd4는 나이트를 중앙에 자리 잡게 합니다.']},
 'sicilian_black':{'name':'시실리안 디펜스 · 흑','color':'black','intro':'백의 e4에 ...c5로 비대칭 구조를 만들고 ...d6와 ...cxd4로 중앙 교환을 연습합니다.','moves':['e2e4','c7c5','g1f3','d7d6','d2d4','c5d4','f3d4'],'notes':['백: e4로 중앙을 장악합니다.','흑: ...c5로 비대칭적 구조를 만듭니다.','백: Nf3로 d4를 준비합니다.','흑: ...d6로 유연한 구조를 유지합니다.','백: d4로 중앙을 개방합니다.','흑: ...cxd4로 중앙을 교환합니다.','백: Nxd4로 되잡습니다. 흑은 ...Nf6나 ...a6 등으로 이어갈 수 있습니다.']}
}
class OpeningStartBody(BaseModel):
 line_id:str
class OpeningMoveBody(BaseModel):
 line_id:str
 move:str

def opening_payload(line,idx):
 b=chess.Board()
 for u in line['moves'][:idx]:b.push_uci(u)
 return {'fen':b.fen(),'squares':{chess.square_name(i):p.symbol() for i,p in b.piece_map().items()},'legal':[m.uci() for m in b.legal_moves] if b.turn==(chess.WHITE if line['color']=='white' else chess.BLACK) else [],'index':idx,'total':len(line['moves']),'color':line['color'],'title':line['name'],'explanation':line['notes'][idx-1] if idx else line['intro'],'done':idx>=len(line['moves'])}
@app.get('/api/openings')
def opening_list(authorization:str|None=Header(default=None)):
 auth(authorization)
 return [{'id':k,'name':v['name'],'color':v['color']} for k,v in OPENING_LINES.items()]
@app.post('/api/openings/start')
def opening_start(body:OpeningStartBody,authorization:str|None=Header(default=None)):
 code=auth(authorization)
 if body.line_id not in OPENING_LINES:raise HTTPException(404,'오프닝 과정을 찾을 수 없습니다.')
 state=get_state(code);line=OPENING_LINES[body.line_id];idx=0
 if line['color']=='black':idx=1 # White makes the first scripted move.
 state['opening_practice']={'line_id':body.line_id,'index':idx}
 save_state(code,state)
 return opening_payload(line,idx)
@app.post('/api/openings/move')
def opening_move(body:OpeningMoveBody,authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code);op=state.get('opening_practice')
 if not op or op.get('line_id')!=body.line_id:raise HTTPException(409,'먼저 오프닝 실습을 시작하세요.')
 line=OPENING_LINES[body.line_id];idx=op['index']
 if idx>=len(line['moves']):raise HTTPException(409,'이미 끝난 실습입니다.')
 b=chess.Board()
 for u in line['moves'][:idx]:b.push_uci(u)
 if body.move!=line['moves'][idx]:return {'correct':False,'message':'다른 계획도 가능하지만, 이 실습에서는 지금 배우는 오프닝 수순을 찾아보세요.',**opening_payload(line,idx)}
 m=chess.Move.from_uci(body.move)
 if m not in b.legal_moves:raise HTTPException(400,'합법적이지 않은 수입니다.')
 idx+=1
 user_note=line['notes'][idx-1]
 opponent_move=None;opponent_note=None
 if idx<len(line['moves']):
  opponent_move=line['moves'][idx]
  b.push(m);reply=chess.Move.from_uci(opponent_move)
  if reply not in b.legal_moves:raise HTTPException(500,'교육용 수순에 오류가 있습니다.')
  opponent_note=line['notes'][idx]
  idx+=1
 op['index']=idx
 if idx>=len(line['moves']):
  state.setdefault('opening_completed',[])
  if body.line_id not in state['opening_completed']:state['opening_completed'].append(body.line_id)
 save_state(code,state)
 return {'correct':True,'player_note':user_note,'opponent_move':opponent_move,'opponent_note':opponent_note,**opening_payload(line,idx)}

# V4 short *continuous* guided games: a three-move lesson, with scripted opponent replies.
# These replace isolated 'guess the square' drills as the default academy practice.
LESSON_GAMES={
 'rules':{'title':'기본 이동과 전개','fen':chess.STARTING_FEN,'moves':['e2e4','e7e5','g1f3','b8c6','f1c4','f8c5'],
 'notes':['e4는 중앙을 확보하는 기본적인 폰 전진입니다.','흑 ...e5는 같은 중앙을 맞섭니다.','Nf3는 나이트의 L자 이동과 e5 압박을 연습합니다.','흑 ...Nc6가 e5 폰을 보호합니다.','Bc4로 비숍의 긴 대각선과 f7 약점을 배웁니다.','흑 ...Bc5도 f2를 압박합니다.']},
 'capture':{'title':'폰 교환과 기물 템포','fen':chess.STARTING_FEN,'moves':['e2e4','d7d5','e4d5','d8d5','b1c3','d5a5'],
 'notes':['e4로 중앙을 선점합니다.','흑 ...d5가 즉시 중앙에서 도전합니다.','exd5로 폰이 대각선으로 잡는 규칙을 체험합니다.','흑 ...Qxd5로 되잡지만 퀸이 일찍 노출됩니다.','Nc3으로 전개하면서 퀸을 공격해 템포를 얻습니다.','흑의 퀸이 안전한 곳으로 물러납니다.']},
 'tactics':{'title':'공격·전술의 기반','fen':chess.STARTING_FEN,'moves':['e2e4','e7e5','g1f3','b8c6','f1c4','g8f6','f3g5','d7d5'],
 'notes':['e4가 중앙을 선점합니다.','흑 ...e5는 균형을 맞춥니다.','Nf3로 e5를 압박합니다.','흑 ...Nc6가 이를 지킵니다.','Bc4는 f7을 견제합니다.','흑 ...Nf6로 e4를 위협합니다.','Ng5가 f7을 비숍과 함께 압박하는 전술적 아이디어를 만듭니다.','흑 ...d5는 중앙에서 방어하며 비숍의 대각선을 차단합니다.']},
 'calculation':{'title':'위협과 응수 계산','fen':chess.STARTING_FEN,'moves':['e2e4','e7e5','g1f3','b8c6','f1b5','a7a6','b5a4','g8f6'],
 'notes':['e4로 중앙 공간을 확보합니다.','흑 ...e5로 맞섭니다.','Nf3가 e5를 공격합니다.','흑 ...Nc6는 e5를 보호합니다.','Bb5는 e5를 지키는 나이트에 간접 압박을 줍니다.','흑 ...a6는 비숍에게 선택을 강요합니다.','Ba4로 비숍을 보존하며 장기 압박을 유지합니다.','흑 ...Nf6가 e4를 압박합니다. 다음 수의 방어가 필요합니다.']},
 'endgame':{'title':'킹과 폰의 협력','fen':'7k/8/8/8/3P4/4K3/8/8 w - - 0 1','moves':['d4d5','h8g7','e3d4','g7f6','d5d6','f6e6'],
 'notes':['d5로 폰을 한 칸 전진시켜 공간을 확보합니다.','흑 킹이 전진해 방어에 참가합니다.','Kd4로 킹을 중앙으로 보내 폰을 지원합니다.','흑 킹이 승격 방향으로 접근합니다.','d6로 승격이 가까워지지만 단독 폰 전진이 항상 안전한 것은 아닙니다.','흑 킹이 폰의 승격 경로를 막으려 합니다.']},
 'opening':{'title':'이탈리안 게임 기초','fen':chess.STARTING_FEN,'moves':['e2e4','e7e5','g1f3','b8c6','f1c4','f8c5'],
 'notes':['e4는 중앙 통제를 시작합니다.','흑은 ...e5로 대응합니다.','Nf3는 중앙과 e5 폰을 압박합니다.','흑 ...Nc6는 e5를 지킵니다.','Bc4로 이탈리안 게임을 만듭니다.','흑 ...Bc5는 f2를 견제합니다.']},
 'review':{'title':'복기하며 대안 찾기','fen':chess.STARTING_FEN,'moves':['e2e4','c7c5','g1f3','d7d6','d2d4','c5d4','f3d4'],
 'notes':['e4 중앙 진출의 목표를 기억하세요.','흑 ...c5는 비대칭적인 구조를 만듭니다.','Nf3로 전개하고 d4를 준비합니다.','흑 ...d6로 탄탄한 중앙을 유지합니다.','d4로 중앙을 개방할 때 상대의 응수를 예측합니다.','흑 ...cxd4로 폰을 교환합니다.','Nxd4로 중앙에 나이트를 배치하는 이유를 설명해 보세요.']},
}
# Structural validation at import, so a malformed scripted line fails visibly rather than teaching an illegal move.
for key,line in LESSON_GAMES.items():
 _b=chess.Board(line['fen'])
 assert len(line['moves'])==len(line['notes']) and len(line['moves'])>=6
 for uci in line['moves']:
  _m=chess.Move.from_uci(uci)
  assert _m in _b.legal_moves,(key,uci)
  _b.push(_m)
for key,line in OPENING_LINES.items():
 _b=chess.Board()
 assert len(line['moves'])==len(line['notes'])
 for uci in line['moves']:
  _m=chess.Move.from_uci(uci)
  assert _m in _b.legal_moves,(key,uci)
  _b.push(_m)

class AcademyPlayBody(BaseModel):
 lesson_id:str
 move:str

def academy_payload(line,idx):
 board=chess.Board(line['fen'])
 for uci in line['moves'][:idx]:board.push_uci(uci)
 return {'fen':board.fen(),'squares':{chess.square_name(s):p.symbol() for s,p in board.piece_map().items()},'legal':[m.uci() for m in board.legal_moves] if board.turn==chess.WHITE else [],'index':idx,'total':len(line['moves']),'title':line['title'],'explanation':line['notes'][idx-1] if idx else '먼저 기물을 선택해 수를 두세요. 상대 응수는 자동으로 이어집니다.','done':idx>=len(line['moves'])}

@app.post('/api/academy/play/start/{lesson_id}')
def academy_play_start(lesson_id:str,authorization:str|None=Header(default=None)):
 code=auth(authorization)
 if lesson_id not in LESSON_GAMES:raise HTTPException(404,'과정을 찾을 수 없습니다.')
 state=get_state(code);state['academy_play']={'lesson_id':lesson_id,'index':0};save_state(code,state)
 return academy_payload(LESSON_GAMES[lesson_id],0)

@app.post('/api/academy/play/move')
def academy_play_move(body:AcademyPlayBody,authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code);cur=state.get('academy_play')
 if not cur or cur['lesson_id']!=body.lesson_id:raise HTTPException(409,'과정부터 시작해 주세요.')
 line=LESSON_GAMES[body.lesson_id];idx=cur['index']
 if idx>=len(line['moves']):raise HTTPException(409,'이 과정은 이미 완료됐습니다.')
 if body.move!=line['moves'][idx]:return {'correct':False,'message':'이 수를 두면 다른 계획으로 진행됩니다. 이번 과정의 핵심 목표에 맞는 수를 선택해 보세요.',**academy_payload(line,idx)}
 board=chess.Board(line['fen'])
 for uci in line['moves'][:idx]:board.push_uci(uci)
 move=chess.Move.from_uci(body.move)
 if move not in board.legal_moves:raise HTTPException(400,'체스 규칙상 허용되지 않는 수입니다.')
 idx+=1;player_note=line['notes'][idx-1];opponent_move=None;opponent_note=None
 if idx<len(line['moves']):
  board.push(move)
  reply=chess.Move.from_uci(line['moves'][idx])
  if reply not in board.legal_moves:raise HTTPException(500,'교육 수순 오류')
  opponent_move=reply.uci();opponent_note=line['notes'][idx];idx+=1
 cur['index']=idx
 if idx>=len(line['moves']):
  state.setdefault('completed_lessons',[])
  if body.lesson_id not in state['completed_lessons']:state['completed_lessons'].append(body.lesson_id)
 save_state(code,state)
 return {'correct':True,'player_note':player_note,'opponent_note':opponent_note,'opponent_move':opponent_move,**academy_payload(line,idx)}

# ==== V5: curated practice sessions, analysis, profile reset and expanded openings ====
class ResetProfile(BaseModel):
 pin:str
 confirmation:str

@app.post('/api/profile/reset')
def profile_reset(body:ResetProfile,authorization:str|None=Header(default=None)):
 code=auth(authorization)
 if body.confirmation!='초기화':raise HTTPException(400,'확인 문구가 정확하지 않습니다.')
 with db() as c:r=execute(c,'SELECT pin_hash,salt FROM accounts WHERE code=?',(code,)).fetchone()
 if not r or not hmac.compare_digest(r['pin_hash'],hash_pin(body.pin,r['salt'])):raise HTTPException(403,'PIN이 일치하지 않습니다.')
 save_state(code,blank_state())
 return {'ok':True,'message':'개인 코드와 로그인은 유지하고 학습·대국·진단 기록을 초기화했습니다.'}

@app.post('/api/practice/retry')
def practice_retry(authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code);current=state.get('practice')
 if not current:raise HTTPException(409,'재도전할 퍼즐이 없습니다.')
 # A retry is a fresh attempt of the current puzzle, not a replay of its old graded session.
 current['attempted']=False;current['issued']=int(time.time())
 save_state(code,state)
 return public_exercise(exercise_bank()[current['id']],current['id'])

@app.get('/api/games/history')
def games_history(authorization:str|None=Header(default=None)):
 code=auth(authorization);items=get_state(code).get('games',[])
 return [{'index':i,'result':g.get('result'),'ended':g.get('ended'),'color':g.get('color','white'),'difficulty':g.get('difficulty',5),'plies':len(g.get('moves',[])),'engine':g.get('engine')} for i,g in reversed(list(enumerate(items)))]

def review_annotation(board,move,engine=None):
 side=board.turn
 bestmove=None
 before_cp=None
 played_cp=None
 source='heuristic'
 if engine:
  try:
   start=engine.analyse(board,chess.engine.Limit(time=.025))
   bestmove=start.get('pv',[None])[0]
   before_cp=start['score'].pov(side).score(mate_score=10000)
   board.push(move)
   try:
    end=engine.analyse(board,chess.engine.Limit(time=.025))
    played_cp=end['score'].pov(side).score(mate_score=10000)
   finally:board.pop()
   source='Stockfish quick analysis'
  except Exception:pass
 if before_cp is None:
  before_cp=positional_score(board)*(1 if side else -1)
  if board.is_capture(move):quality='상황에 맞는 포획'
  else:quality='착수 기록'
  board.push(move);played_cp=positional_score(board)*(1 if side else -1);board.pop()
  loss=max(0,round(before_cp-played_cp))
  # Fallback is a shallow heuristic: don't assign strong move-quality labels.
  return {'centipawn_loss':loss,'category':'미평가','comment':'Stockfish 미연결: 휴리스틱 차이만 참고하세요. 수의 품질 판정은 제공하지 않습니다.','best_move':None,'source':'heuristic (not a move grade)'}
 loss=max(0,round(before_cp-played_cp))
 if bestmove==move:grade='최선';comment='엔진이 가장 높게 평가한 수입니다.'
 elif loss<=15:grade='훌륭';comment='최선에 매우 가까운 안정적인 수입니다.'
 elif loss<=45:grade='좋음';comment='유력한 수이지만 약간 더 나은 선택이 있습니다.'
 elif loss<=95:grade='부정확';comment='상대에게 다소 유리한 기회를 줄 수 있습니다.'
 elif loss<=220:grade='실수';comment='중요한 기회 또는 방어 수단을 놓쳤습니다.'
 else:grade='블런더';comment='상당한 평가 손실이 발생했습니다. 후보수와 상대의 강제수를 다시 살펴보세요.'
 return {'centipawn_loss':loss,'category':grade,'comment':comment,'best_move':bestmove.uci() if bestmove else None,'source':source}

@app.get('/api/games/review/{index}')
def game_review(index:int,authorization:str|None=Header(default=None)):
 code=auth(authorization);games=get_state(code).get('games',[])
 if index<0 or index>=len(games):raise HTTPException(404,'대국을 찾을 수 없습니다.')
 game=games[index];board=chess.Board();rows=[]
 # Cap synchronous analysis per request for free-instance performance.
 moves=game.get('moves',[])
 if len(moves)>200:raise HTTPException(400,'긴 대국은 분석 구간을 나누어야 합니다. 현재는 200수 이하만 지원합니다.')
 eng=None
 if STOCKFISH_PATH and Path(STOCKFISH_PATH).exists():
  try:eng=chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH,timeout=15)
  except Exception:pass
 try:
  return build_review_rows(eng,game,index,moves)
 finally:
  if eng:
   try:eng.quit()
   except Exception:pass

def build_review_rows(eng,game,index,moves):
 board=chess.Board();rows=[]
 for n,uci in enumerate(moves):
  try:m=chess.Move.from_uci(uci)
  except ValueError:break
  if m not in board.legal_moves:break
  fen_before=board.fen();san=board.san(m);side='백' if board.turn else '흑'
  assessment=review_annotation(board,m,eng)
  board.push(m)
  rows.append({'ply':n+1,'side':side,'uci':uci,'san':san,'before_fen':fen_before,'after_fen':board.fen(),**assessment})
 return {'index':index,'result':game.get('result'),'color':game.get('color','white'),'difficulty':game.get('difficulty',5),'moves':rows,'final_fen':board.fen(),'method':'신속 분석: 깊은 탐색보다 속도를 우선하며, 수 평가 라벨은 근사치입니다.'}

# Larger opening catalogue. Each line is verified for legality at startup.
ADDITIONAL_OPENINGS={
 'london_white':('런던 시스템 · 백','white',['d2d4','d7d5','c1f4','g8f6','e2e3','e7e6','g1f3','f8d6']),
 'london_black':('런던 시스템 · 흑','black',['d2d4','d7d5','c1f4','g8f6','e2e3','e7e6','g1f3','f8d6']),
 'carokann_white':('카로칸 디펜스 · 백','white',['e2e4','c7c6','d2d4','d7d5','b1c3','d5e4','c3e4']),
 'carokann_black':('카로칸 디펜스 · 흑','black',['e2e4','c7c6','d2d4','d7d5','b1c3','d5e4','c3e4']),
 'french_white':('프렌치 디펜스 · 백','white',['e2e4','e7e6','d2d4','d7d5','b1c3','g8f6']),
 'french_black':('프렌치 디펜스 · 흑','black',['e2e4','e7e6','d2d4','d7d5','b1c3','g8f6']),
 'scotch_white':('스카치 게임 · 백','white',['e2e4','e7e5','g1f3','b8c6','d2d4','e5d4','f3d4']),
 'scotch_black':('스카치 게임 · 흑','black',['e2e4','e7e5','g1f3','b8c6','d2d4','e5d4','f3d4']),
 'kingsindian_white':('킹즈 인디언 디펜스 · 백','white',['d2d4','g8f6','c2c4','g7g6','b1c3','f8g7']),
 'kingsindian_black':('킹즈 인디언 디펜스 · 흑','black',['d2d4','g8f6','c2c4','g7g6','b1c3','f8g7']),
 'ruylopez_white':('루이 로페즈 · 백','white',['e2e4','e7e5','g1f3','b8c6','f1b5','a7a6','b5a4']),
 'ruylopez_black':('루이 로페즈 · 흑','black',['e2e4','e7e5','g1f3','b8c6','f1b5','a7a6','b5a4']),
 'english_white':('잉글리시 오프닝 · 백','white',['c2c4','e7e5','b1c3','g8f6','g2g3','d7d5']),
 'english_black':('잉글리시 오프닝 · 흑','black',['c2c4','e7e5','b1c3','g8f6','g2g3','d7d5']),
}
OPENING_EDUCATION={
 'london':'d4와 Bf4로 안정적인 구조를 만들고 e3·Nf3로 전개합니다. 흑은 ...d5, ...Nf6, ...e6로 중앙 균형과 비숍 압박을 준비합니다.',
 'carokann':'흑은 ...c6으로 ...d5를 지지하며 중앙을 공격합니다. 백은 d4로 공간을 확보하고 Nc3로 e4를 지킵니다.',
 'french':'흑은 ...e6와 ...d5로 중앙에 압박을 가하지만 밝은칸 비숍이 제약됩니다. 백은 d4와 Nc3로 공간을 활용합니다.',
 'scotch':'백은 빠른 d4로 중앙을 열어 전개 우위를 시도합니다. 흑은 ...exd4로 중앙 긴장을 즉시 해소합니다.',
 'kingsindian':'흑은 ...Nf6·...g6·...Bg7로 피앙케토 후 중앙 반격을 노립니다. 백은 d4·c4·Nc3로 공간을 확보합니다.',
 'ruylopez':'백 B b5는 c6의 나이트와 e5 폰의 관계를 압박합니다. 흑의 ...a6 이후 비숍을 후퇴시키며 중앙 싸움을 지속합니다.',
 'english':'백은 c4로 d5를 통제하며 유연하게 전개합니다. 흑은 ...e5로 중앙과 공간에 맞섭니다.'}
for key,(name,color,moves) in ADDITIONAL_OPENINGS.items():
 b=chess.Board()
 for uci in moves:
  m=chess.Move.from_uci(uci)
  assert m in b.legal_moves,(key,uci)
  b.push(m)
 description=OPENING_EDUCATION[key.split('_')[0]]
 notes=[f'{"백" if i%2==0 else "흑"}의 {i//2+1}번째 착수: {description}' for i,_ in enumerate(moves)]
 OPENING_LINES[key]={'name':name,'color':color,'intro':description,'moves':moves,'notes':notes}

@app.get('/api/openings/hint')
def opening_hint(authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code);s=state.get('opening_practice')
 if not s:raise HTTPException(409,'먼저 오프닝을 시작해 주세요.')
 line=OPENING_LINES[s['line_id']];idx=s['index']
 if idx>=len(line['moves']):return {'done':True}
 return {'done':False,'move':line['moves'][idx],'explanation':line['notes'][idx],'opponent_next':line['moves'][idx+1] if idx+1<len(line['moves']) else None}

# scenario-based coaching, with distinct positions and actual legal-move checks
from lesson_scenarios import SCENARIOS
class ScenarioMove(BaseModel):
 lesson_id:str
 move:str

@app.post('/api/academy/scenario/start/{lesson_id}')
def scenario_start(lesson_id:str,authorization:str|None=Header(default=None)):
 code=auth(authorization)
 if lesson_id not in SCENARIOS:raise HTTPException(404,'교육 주제가 없습니다.')
 state=get_state(code)
 # Every lesson consists of distinct short board states, never one unrelated full game.
 order=list(range(len(SCENARIOS[lesson_id])));random.shuffle(order)
 state['scenario_v5']={'lesson_id':lesson_id,'order':order,'index':0,'attempts':0}
 save_state(code,state)
 return scenario_payload(state['scenario_v5'])

def scenario_payload(cur):
 if cur['index']>=len(cur['order']):return {'done':True,'lesson_id':cur['lesson_id']}
 p=SCENARIOS[cur['lesson_id']][cur['order'][cur['index']]];b=chess.Board(p['fen'])
 return {'done':False,'lesson_id':cur['lesson_id'],'index':cur['index'],'total':len(cur['order']),'fen':p['fen'],'prompt':p['prompt'],'legal':[m.uci() for m in b.legal_moves]}

@app.post('/api/academy/scenario/move')
def scenario_move(body:ScenarioMove,authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code);cur=state.get('scenario_v5')
 if not cur or cur['lesson_id']!=body.lesson_id:raise HTTPException(409,'실습을 먼저 시작하세요.')
 if cur['index']>=len(cur['order']):raise HTTPException(409,'이미 완료된 실습입니다.')
 p=SCENARIOS[body.lesson_id][cur['order'][cur['index']]]
 b=chess.Board(p['fen'])
 try:m=chess.Move.from_uci(body.move)
 except ValueError:m=None
 if m not in b.legal_moves:return {'correct':False,'message':'합법적이지 않은 착수입니다.'}
 if body.move!=p['answer']:
  cur['attempts']+=1;save_state(code,state)
  return {'correct':False,'message':'이번 실습의 목표와 다른 수입니다. 포지션과 설명을 다시 살펴보세요.'}
 b.push(m);after=b.fen();cur['index']+=1
 done=cur['index']==len(cur['order'])
 if done:
  state.setdefault('completed_lessons',[])
  if body.lesson_id not in state['completed_lessons']:state['completed_lessons'].append(body.lesson_id)
 save_state(code,state)
 return {'correct':True,'played_fen':after,'explanation':p['prompt'],'done':done,'next':None if done else scenario_payload(cur),'completed':cur['index'],'total':len(cur['order'])}

# Create mirrored board situations where safe: separate visual contexts for transfer practice.
# These are deliberately not passed off as independently authored lessons.
def _v5_expand_scenes():
 for subject,scenes in SCENARIOS.items():
  expanded=[]
  for p in scenes:
   expanded.append(p)
   b=chess.Board(p['fen'])
   if b.castling_rights:continue
   mirrored=b.transform(chess.flip_horizontal)
   old=p['answer'];translated=old.translate(str.maketrans('abcdefgh','hgfedcba'))
   try:
    candidate=chess.Move.from_uci(translated)
    if mirrored.is_valid() and candidate in mirrored.legal_moves:
     expanded.append({'fen':mirrored.fen(),'answer':translated,'prompt':p['prompt']+' (반대쪽 배치)'})
   except Exception:pass
  SCENARIOS[subject]=expanded
_v5_expand_scenes()

# V6 curriculum and assessment correctness layer — JSON progress schema unchanged.
from curriculum_v6 import COURSES as V6_COURSES, CATALOG as V6_CATALOG, classify as v6_classify

class V6Move(BaseModel):
 move:str

@app.get('/api/v6/courses')
def v6_courses(authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code)
 done=set(state.get('completed_lessons',[]))
 return [{'id':k,'name':v[0],'level':v[1],'description':v[2], 'count':len(V6_CATALOG[k]),'completed':('v6:'+k in done)} for k,v in V6_COURSES.items() if V6_CATALOG[k]]

@app.post('/api/v6/course/{course_id}/start')
def v6_course_start(course_id:str,authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code)
 if course_id not in V6_CATALOG or not V6_CATALOG[course_id]:raise HTTPException(404,'아직 검증된 실습 문제가 없습니다.')
 order=list(range(len(V6_CATALOG[course_id])));random.shuffle(order)
 state['v6_course']={'course':course_id,'order':order,'index':0,'correct_first':0,'attempted':False,'done':False}
 save_state(code,state)
 return v6_course_payload(state['v6_course'])

def v6_course_payload(s):
 scenes=V6_CATALOG[s['course']]
 if s['done'] or s['index']>=len(s['order']):return {'done':True,'course':s['course'],'total':len(s['order']),'first_try':s['correct_first']}
 p=scenes[s['order'][s['index']]];b=chess.Board(p['fen'])
 return {'done':False,'course':s['course'],'index':s['index'],'total':len(s['order']),'fen':p['fen'],'prompt':V6_COURSES[s['course']][2], 'objective':p['objective'],'legal':[m.uci() for m in b.legal_moves], 'topic':V6_COURSES[s['course']][0]}

@app.post('/api/v6/course/move')
def v6_course_move(body:V6Move,authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code);s=state.get('v6_course')
 if not s or s.get('done'):raise HTTPException(409,'진행 중인 과정이 없습니다.')
 p=V6_CATALOG[s['course']][s['order'][s['index']]];b=chess.Board(p['fen'])
 try:m=chess.Move.from_uci(body.move)
 except ValueError:raise HTTPException(400,'착수 좌표가 올바르지 않습니다.')
 accepted,hint=v6_classify(b,m,p['objective'])
 if not accepted:
  s['attempted']=True;save_state(code,state)
  return {'correct':False,'message':hint,'fen':p['fen'],'index':s['index'],'total':len(s['order'])}
 b.push(m)
 if not s['attempted']:s['correct_first']+=1
 s['attempted']=False;s['index']+=1
 s['done']=s['index']==len(s['order'])
 if s['done']:
  # Mastery progress belongs to the new granulated course, not a v5 broad category.
  if s['correct_first']>=max(3,int(len(s['order'])*.75)):
   key='v6:'+s['course']
   if key not in state.setdefault('completed_lessons',[]):state['completed_lessons'].append(key)
 save_state(code,state)
 return {'correct':True,'played_fen':b.fen(),'message':p['note'],'done':s['done'], 'passed':s['done'] and s['correct_first']>=max(3,int(len(s['order'])*.75)), 'next':None if s['done'] else v6_course_payload(s), 'first_try':s['correct_first'],'total':len(s['order'])}

@app.get('/api/v6/diagnostic/recommend')
def v6_recommendations(authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code);r=state.get('assessment') or {}
 mapping={'체크메이트':['mate','safecheck'],'전술·포획':['fork','pin','skewer','discovered','double','capture'],'오프닝 전개':['opening'],'킹·폰 엔드게임':['endgame'],'수읽기·강제수':['safecheck','fork','double']}
 weaknesses=r.get('weaknesses',[]) if isinstance(r,dict) else []
 suggestions=[]
 for domain in weaknesses:
  for key in mapping.get(domain,[]):
   suggestions.append({'domain':domain,'id':key,'name':V6_COURSES[key][0],'reason':f'{domain} 진단에서 보완이 필요한 분야입니다.'})
 if not suggestions:suggestions=[{'domain':'기초 확인','id':'safecheck','name':'합법적인 체크','reason':'진단을 완료하면 약점에 맞는 훈련이 추천됩니다.'}]
 return {'suggestions':suggestions,'skills':r.get('skills',{}),'stage':r.get('stage','진단 전'),'is_official_elo':False}

@app.post('/api/v6/assessment/advance')
def v6_assessment_advance(authorization:str|None=Header(default=None)):
 code=auth(authorization);state=get_state(code);t=state.get('assessment_v3')
 if not t or t['phase']!='questions' or not t.get('pending_feedback'):raise HTTPException(409,'채점 결과를 확인한 뒤 다음 문제로 넘어갈 수 있습니다.')
 t.pop('pending_feedback');t['index']+=1
 if t['index']<25:
  save_state(code,state);return {'done':False,**assessment_question(exam_bank(t['seed']),t['index'])}
 t['phase']='game';t['game_moves']=[];t['game_scores']=[]
 save_state(code,state)
 return {'done':False,'phase':'game','board':serialize_board(chess.Board()),'target_white_moves':12,'message':'25문항을 완료했습니다. 이제 중급 AI 대국을 시작합니다.'}

# V7 additive endpoints; keeps existing database and account tokens intact.
from v7_server import attach_v7
attach_v7(app,globals())

# V8 diagnostic: independent, server-timed examination with rating history.
from v8_server import attach_v8
attach_v8(app,globals())

# Guided mate-in-three drill (small curated set; not an infinite puzzle bank).
from mate3_v8 import attach_mate3
attach_mate3(app,globals())
