"""Read-only board exploration and separately saved opening study bookmarks.
No exploration endpoint calls game finish, rating, or learning credit functions.
"""
import csv
import hashlib
import json
import threading
import time
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
from typing import Literal
import chess
import chess.engine
from fastapi import Header, HTTPException, Query
from pydantic import BaseModel, Field
from engine_budget import open_engine, EngineBusy
from opening_courses import COURSES, FAMILIES

DATA=Path(__file__).parent/'data'/'openings'

def key(b):return b.epd(en_passant='legal')  # turn, castling and legal EP rights retained

def replay(fen,moves):
    try:
        b=chess.Board(fen)
        if not b.is_valid():raise ValueError()
        for u in moves:
            if b.is_game_over(claim_draw=True):raise ValueError('종료 위치')
            b.push_uci(u)
        return b
    except ValueError:raise HTTPException(400,'국면 또는 수순이 합법적이지 않습니다.')

def view(b):
    outcome=b.outcome(claim_draw=True)
    return {'fen':b.fen(),'legal':[] if outcome else [m.uci() for m in b.legal_moves],
            'terminal':bool(outcome),'result':outcome.result() if outcome else None,
            'ending':('체크메이트' if b.is_checkmate() else '스테일메이트' if b.is_stalemate() else '무승부 조건 충족 (반복·50수는 청구 가능한 경우 포함)') if outcome else None}

@lru_cache(maxsize=1)
def courses():
    result={}
    for row in COURSES:
        b=chess.Board();moves=[];positions=[key(b)];sans=[]
        for san in row['pgn'].split():
            m=b.parse_san(san);sans.append(b.san(m));moves.append(m.uci());b.push(m);positions.append(key(b))
        result[row['id']]={**row,'moves':moves,'sans':sans,'positions':positions}
    return result

@lru_cache(maxsize=1)
def references():
    rows=[]
    for p in sorted(DATA.glob('*.tsv')):
        for r in csv.DictReader(p.open(),delimiter='\t'):
            r['id']=hashlib.sha256((r['eco']+'|'+r['name']+'|'+r['pgn']).encode()).hexdigest()[:20];rows.append(r)
    return rows

def note(c,index):
    """Per-entry author notes plus literal board facts, never engine-generated theory."""
    b=replay(chess.STARTING_FEN,c['moves'][:index]);m=chess.Move.from_uci(c['moves'][index]);side='백' if b.turn else '흑'
    names={1:'폰',2:'나이트',3:'비숍',4:'룩',5:'퀸',6:'킹'}
    piece=names[b.piece_type_at(m.from_square)]
    particle='을' if (ord(piece[-1])-0xAC00)%28 else '를'
    facts=f"{side} {b.san(m)}: {piece}{particle} {chess.square_name(m.from_square)}에서 {chess.square_name(m.to_square)}로 옮깁니다."
    if b.is_castling(m):facts+=' 킹을 옆으로 피하고 룩을 중앙 파일에 배치합니다.'
    elif b.is_capture(m):facts+=' 교환 뒤 열리는 파일과 되잡는 기물의 위치를 확인하세요.'
    else:
        after=b.copy();after.push(m)
        central=[chess.square_name(s) for s in [chess.D4,chess.E4,chess.D5,chess.E5] if s in after.attacks(m.to_square)]
        if central:facts+=' 옮긴 기물은 중앙 '+', '.join(central)+' 칸을 공격하거나 지지합니다.'
        if b.piece_type_at(m.from_square) in (chess.KNIGHT,chess.BISHOP) and chess.square_rank(m.from_square) in (0,7):facts+=' 뒷줄 기물을 전개해 다른 기물의 길을 엽니다.'
    return {'facts':facts,'comment':c['notes'].get(index+1),'note_kind':'authored_key_move' if index+1 in c['notes'] else 'position_facts',
            'context':'이 설명은 선택한 강의의 진입 수순을 기준으로 합니다. 같은 위치라도 다른 순서에서는 위협을 다시 확인하세요.'}

class Position(BaseModel):
    fen:str=Field(default=chess.STARTING_FEN,max_length=120)
    moves:list[str]=Field(default_factory=list,max_length=240)
    engine:bool=False
    evaluate:bool=False

class OpeningPosition(BaseModel):
    course_id:str=Field(max_length=80)
    moves:list[str]=Field(default_factory=list,max_length=120)
    mode:Literal['explore','recall']='explore'

class Bookmark(OpeningPosition):
    revision:int=Field(ge=0)
    orientation:Literal['white','black']='white'


def opening_position(req):
    c=courses().get(req.course_id)
    if not c:raise HTTPException(404,'강의를 찾을 수 없습니다.')
    b=replay(chess.STARTING_FEN,req.moves);position=key(b);matches=[];options={}
    for other in courses().values():
        for i,p in enumerate(other['positions']):
            if p!=position:continue
            matches.append({'id':other['id'],'title':other['title'],'index':i,'end':i==len(other['moves'])})
            if i<len(other['moves']):
                u=other['moves'][i];options.setdefault(u,{'move':u,'san':other['sans'][i],'courses':[]})['courses'].append({'id':other['id'],'title':other['title']})
    indexes=[i for i,p in enumerate(c['positions']) if p==position];idx=indexes[-1] if indexes else None
    last_note=None
    if req.moves:
        previous=replay(chess.STARTING_FEN,req.moves[:-1]);pk=key(previous)
        for i,p in enumerate(c['positions'][:-1]):
            if p==pk and c['moves'][i]==req.moves[-1]:last_note=note(c,i);break
    own_end=idx==len(c['moves']);off=not matches
    data={**view(b),'course_id':c['id'],'mode':req.mode,'moves':req.moves,'on_course':idx is not None,'matches':matches,
          'theory_end':own_end,'unregistered':off,'message':'이 강의에 아직 해설이 없는 수입니다. 합법 수이며 오답이라는 뜻은 아닙니다.' if off else '다른 등록 변형의 위치입니다. 강의를 바꾸어 해설을 이어갈 수 있어요.' if idx is None else '강의 예시 수순을 마쳤어요. 이론 전체가 끝났다는 뜻은 아닙니다.' if own_end else '등록된 여러 수를 직접 비교해 보세요.',
          'transposed':idx is not None and req.moves!=c['moves'][:idx],
          'options':list(options.values()) if req.mode=='explore' else [],'note':last_note,
          'next_note':note(c,idx) if req.mode=='explore' and idx is not None and not own_end else None,
          'plans':c['ending'] if own_end else None,
          'structure':' · '.join(label+' 폰: '+', '.join(chess.square_name(s) for s in b.pieces(chess.PAWN,color)) for color,label in [(chess.WHITE,'백'),(chess.BLACK,'흑')]) if own_end else None,
          'family_overview':FAMILIES[c['family']][1] if idx is not None and not own_end and req.mode=='explore' else None}
    if req.mode=='recall':data.update(note=None,matches=[{k:v for k,v in m.items() if k!='index'} for m in matches] if own_end else [])
    return data


def attach_study(app,ns):
    from branch_exposure import attach_branch_exposure
    attach_branch_exposure(app,ns)
    auth=ns['auth']
    analysis_lock=threading.Lock(); analysis_cache=OrderedDict(); analysis_last=OrderedDict(); global_last=[0.0]
    @app.post('/api/study/position')
    def position(req:Position,authorization:str|None=Header(default=None)):
        code=auth(authorization);b=replay(req.fen,req.moves);result=view(b)
        if req.evaluate:
            # Explicit read-only fallback; no scoring or original game writes.
            if result['terminal']:
                return {**result,'evaluation':{'kind':'terminal-mate' if b.is_checkmate() else 'draw','value':(-1 if b.turn else 1) if b.is_checkmate() else 0}}
            position_key=b.fen(en_passant='fen');now=time.monotonic()
            with analysis_lock:
                cached=analysis_cache.get(position_key)
                if cached:return {**result,'evaluation':cached}
                if now-analysis_last.get(code,-100)<10 or now-global_last[0]<2:
                    raise HTTPException(429,'분석 요청 간격을 두세요. 직접 탐색은 계속할 수 있습니다.',headers={'Retry-After':'10'})
                analysis_last[code]=now;global_last[0]=now
                while len(analysis_last)>512:analysis_last.popitem(last=False)
            path=ns['STOCKFISH_PATH']
            if not path or not Path(path).is_file():raise HTTPException(503,'분석 엔진을 사용할 수 없습니다. 직접 탐색은 계속할 수 있습니다.')
            try:
                with open_engine(path,timeout=3) as e:
                    e.configure({'Threads':1,'Hash':16})
                    info=e.analyse(b,chess.engine.Limit(time=.2,depth=14,nodes=60000))
                    score=info['score'].white();depth=info.get('depth',0);pv=info.get('pv',[])
                    if depth<10:raise ValueError('insufficient depth')
                    value={'kind':'mate' if score.is_mate() else 'cp','value':score.mate() if score.is_mate() else score.score(),'depth':depth,
                           'best':pv[0].uci() if pv and pv[0] in b.legal_moves else None,'engine':e.id.get('name','Stockfish'),
                           'basis':'백 기준 · 서버 제한 탐색 0.2초/14깊이/6만 노드 · 준비 시간 별도 · 최선 수 보장 아님'}
            except EngineBusy:raise HTTPException(503,'다른 분석 중입니다. 직접 탐색을 계속하고 나중에 요청하세요.')
            except (chess.engine.EngineError,OSError,ValueError,TimeoutError,KeyError):raise HTTPException(503,'분석을 확인하지 못했습니다. 대등으로 해석하지 않습니다.')
            with analysis_lock:
                analysis_cache[position_key]=value
                while len(analysis_cache)>128:analysis_cache.popitem(last=False)
            return {**result,'evaluation':value}
        if req.engine and not result['terminal']:
            path=ns['STOCKFISH_PATH']
            if not path or not Path(path).is_file():raise HTTPException(503,'엔진을 사용할 수 없습니다. 직접 양쪽 수를 두어 탐색할 수 있어요.')
            try:
                with open_engine(path,timeout=3) as e:
                    e.configure({'Threads':1,'Hash':16});m=e.play(b,chess.engine.Limit(time=.2,depth=14)).move
                if not m or m not in b.legal_moves:raise ValueError()
                san=b.san(m);b.push(m);result={**view(b),'reply':m.uci(),'san':san}
            except EngineBusy:raise HTTPException(503,'다른 분석에서 엔진을 사용 중입니다. 잠시 후 다시 요청하세요.',headers={'Retry-After':'1'})
            except (chess.engine.EngineError,OSError,ValueError,TimeoutError):raise HTTPException(503,'응수를 계산하지 못했어요. 현재 분기는 유지됩니다.')
        return result

    @app.get('/api/study/openings')
    def catalog(authorization:str|None=Header(default=None)):
        code=auth(authorization)
        return {'families':[{'id':k,'title':v[0],'intro':v[1]} for k,v in FAMILIES.items()],
                'courses':[{k:c[k] for k in ('id','family','title','version')}|{'plies':len(c['moves']),'key_notes':len(c['notes'])} for c in courses().values()],
                'saved':ns['get_state'](code).get('opening_study',{'revision':0}),
                'source':json.loads((DATA/'SOURCE.json').read_text()),'reference_count':len(references())}
    @app.post('/api/study/openings/position')
    def opening(req:OpeningPosition,authorization:str|None=Header(default=None)):
        auth(authorization);return opening_position(req)
    @app.post('/api/study/openings/save')
    def save(req:Bookmark,authorization:str|None=Header(default=None)):
        code=auth(authorization);opening_position(req);state=ns['get_state'](code);old=state.get('opening_study',{'revision':0})
        if old['revision']!=req.revision:raise HTTPException(409,'다른 화면에서 학습 위치가 바뀌었습니다. 저장 위치를 다시 불러오세요.')
        state['opening_study']={**req.model_dump(),'revision':old['revision']+1}
        ns['save_state'](code,state);return state['opening_study']
    @app.get('/api/study/openings/references')
    def reference(q:str=Query(default='',max_length=100),reference_id:str|None=None,authorization:str|None=Header(default=None)):
        auth(authorization)
        if reference_id:
            row=next((r for r in references() if r['id']==reference_id),None)
            if not row:raise HTTPException(404,'참고 수순을 찾을 수 없습니다.')
            b=chess.Board();moves=[]
            for san in row['pgn'].split():
                if san[0].isdigit():continue
                m=b.parse_san(san);moves.append(m.uci());b.push(m)
            return {**row,'moves':moves,'fen':b.fen(),'epd':key(b),'notice':'CC0 참고 수순입니다. 직접 작성한 강의 해설이나 유일 정답 판정이 아닙니다.'}
        selected=[r for r in references() if q.casefold() in (r['name']+' '+r['eco']).casefold()]
        return {'total':len(selected),'rows':selected[:40],'notice':'ECO 또는 원문 이름으로 검색 · 최대40개 표시 · 강의 해설 없음'}
