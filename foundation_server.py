"""Account-isolated, CAS-saved rule practice. No assessment or training credit."""
import copy
from datetime import datetime, timezone
from typing import Literal
import chess
from fastapi import Header, HTTPException
from pydantic import BaseModel, Field
from foundation_content import COURSES, BY_ID, CHOICES

KEY='foundation_v1'
NAMES={chess.PAWN:'폰',chess.KNIGHT:'나이트',chess.BISHOP:'비숍',chess.ROOK:'룩',chess.QUEEN:'퀸',chess.KING:'킹'}

class FoundationAction(BaseModel):
    action: Literal['start','move','answer','next','review']
    revision: int = Field(ge=0)
    course_id: str
    step: int = Field(default=0,ge=0)
    value: str = Field(default='',max_length=40)


def board_for(step, progress):
    board=chess.Board(step['fen'])
    for u in step.get('line',[])[:progress.get('ply',0)]:board.push_uci(u)
    return board


def bad_move_reason(board, m):
    piece=board.piece_at(m.from_square)
    if not piece or piece.color!=board.turn:return '지금 차례의 말을 선택해 주세요.'
    target=board.piece_at(m.to_square)
    if target and target.color==piece.color:return '내 말이 있는 칸으로는 이동할 수 없어요.'
    if board.is_pseudo_legal(m):return '내 킹이 체크에 남거나 공격에 노출되는 수는 둘 수 없어요.'
    if piece.piece_type in (chess.ROOK,chess.BISHOP,chess.QUEEN):return '이 말의 이동 방향과 중간에 막고 있는 말이 있는지 확인하세요. 다른 말을 뛰어넘을 수 없어요.'
    if piece.piece_type==chess.PAWN:return '폰의 전진은 빈 앞칸, 잡기는 대각선 앞칸입니다. 두 칸 전진·앙파상·승격에는 별도 조건이 있어요.'
    if piece.piece_type==chess.KNIGHT:return '나이트는 한 방향 두 칸과 옆 한 칸의 L자로 움직여요. 자기 말 위에는 착지할 수 없어요.'
    return '킹은 안전한 주변 한 칸으로 이동합니다. 캐슬링은 이동 이력과 빈칸·공격 조건을 모두 확인하세요.'



def visual_context(course_id, step_index, step, progress, board):
    """Read-only rule facts for explicitly guided foundation lessons, never scoring."""
    arrows=[];solved=bool(progress.get('solved'));ply=progress.get('ply',0)
    if step['kind']=='move' and not solved and ply<len(step['line']):
        u=step['line'][ply]
        arrows.append({'from':u[:2],'to':u[2:4],'kind':'guide','label':'이동 안내: '+u[:2]+' → '+u[2:4]})
    if course_id=='value-protection':
        if step_index==1 and not solved:
            a,t=chess.A8,chess.A4
            if board.is_attacked_by(chess.BLACK,t) and a in board.attackers(chess.BLACK,t):
                arrows.append({'from':'a8','to':'a4','kind':'threat','label':'상대 공격: a8 룩 → a4 비숍 (이동 지시 아님)'})
        if step_index==0 and solved and chess.D1 in board.attackers(chess.WHITE,chess.D4):
            arrows.append({'from':'d1','to':'d4','kind':'protect','label':'보호: d1 룩 → d4 나이트 · 무조건 안전하다는 뜻은 아님'})
    checkers=[chess.square_name(q) for q in board.checkers()]
    king=chess.square_name(board.king(board.turn)) if board.is_check() else None
    demonstration=None
    if course_id=='en-passant' and step_index==0 and not solved and ply==0:
        prior=chess.Board('7k/3p4/8/4P3/8/8/8/6K1 b - - 0 1');before=prior.fen();prior.push_uci('d7d5')
        if prior.fen()==board.fen():
            demonstration={'label':'교육 예시 · 저장된 실제 대국의 직전 수가 아닙니다','before_fen':before,'move':'d7d5','after_fen':prior.fen()}
    return {'fen':board.fen(),'arrows':arrows,'check_king':king,'checkers':checkers,
            'ending':('checkmate' if board.is_checkmate() else 'stalemate' if board.is_stalemate() else None) if solved else None,
            'demonstration':demonstration}


def attach_foundations(app, ns):
    def payload(state):
        saved=state.get(KEY,{})
        courses=[]
        for c in COURSES:
            p=saved.get('courses',{}).get(c['id'],{})
            courses.append({k:c[k] for k in ('id','title','goal')}|{'total':len(c['steps']),'started':bool(p),'completed':len(p.get('completed_steps',[])), 'done':bool(p.get('done'))})
        active=saved.get('active')
        recommended=next((c['id'] for c in courses if not c['done']),None)
        task=None
        if active in BY_ID:
            c=BY_ID[active];p=saved['courses'][active];s=c['steps'][p['index']];b=board_for(s,p)
            task={k:s[k] for k in ('kind','title','text')}|{'course_id':active,'course_title':c['title'],'step':p['index'],'total':len(c['steps']),'fen':b.fen(),'side':'white' if chess.Board(s['fen']).turn else 'black','solved':p.get('solved',False),'feedback':p.get('feedback',''),'done':p.get('done',False),'legal':[m.uci() for m in b.legal_moves] if not p.get('solved') and s['kind']=='move' else [],'pieces':[{'square':chess.square_name(sq),'name':NAMES[pc.piece_type]} for sq,pc in sorted(b.piece_map().items()) if pc.color==b.turn]}
            task['visual']=visual_context(active,p['index'],s,p,b)
            if s['kind']=='judge':
                keys=['mate','stalemate','playing'] if s['answer'] in ('mate','stalemate') else ['castle','no_castle'] if 'castle' in s['answer'] else ['ep','no_ep']
                task['choices']=[{'id':key,'label':CHOICES[key]} for key in keys]
        return {'version':1,'rules_first':state.get('learner_start',{}).get('choice')=='rules','revision':saved.get('revision',0),'courses':courses,'active':task,'recommended':recommended,'completed':sum(c['done'] for c in courses),'total':len(courses),'scope':'설명을 보며 하는 기초 연습 · 진단 점수와 훈련 크레딧에 포함하지 않습니다.'}

    @app.get('/api/foundations')
    def read(authorization: str|None=Header(default=None)):
        return payload(ns['get_state'](ns['auth'](authorization)))

    @app.post('/api/foundations/action')
    def action(body:FoundationAction,authorization:str|None=Header(default=None)):
        code=ns['auth'](authorization);state=ns['get_state'](code)
        saved=copy.deepcopy(state.get(KEY,{'revision':0,'courses':{}}))
        if saved['revision']!=body.revision:raise HTTPException(409,'다른 화면에서 기초 진행이 바뀌었습니다. 저장 상태를 다시 불러오세요.')
        if body.course_id not in BY_ID:raise HTTPException(404,'기초 과정을 찾을 수 없습니다.')
        c=BY_ID[body.course_id];interaction='ready'
        if body.action in ('start','review'):
            p=saved['courses'].setdefault(body.course_id,{'index':0,'ply':0,'completed_steps':[]})
            if body.action=='review':p.update(index=0,ply=0,solved=False,feedback='복습을 시작합니다. 기존 완료 기록은 보존됩니다.')
            saved['active']=body.course_id
        else:
            if saved.get('active')!=body.course_id:raise HTTPException(409,'선택한 기초 과정이 바뀌었습니다. 저장 상태를 확인하세요.')
            p=saved['courses'][body.course_id]
            if p['index']!=body.step:raise HTTPException(409,'이미 다음 단계로 이동했습니다. 저장 상태를 확인하세요.')
            s=c['steps'][p['index']];b=board_for(s,p)
            if body.action=='next':
                if not p.get('solved'):raise HTTPException(409,'먼저 보드 연습을 해 보세요. 설명과 함께 다시 시도할 수 있습니다.')
                if p['index']+1>=len(c['steps']):raise HTTPException(409,'이 과정의 마지막 단계입니다. 다음 과정을 선택하세요.')
                p.update(index=p['index']+1,ply=0,solved=False,feedback='')
            else:
                if p.get('solved'):raise HTTPException(409,'이미 확인한 단계입니다. 다음 단계 또는 복습을 선택하세요.')
                correct=False;interaction='try_again'
                if body.action=='move' and s['kind']=='move':
                    try:m=chess.Move.from_uci(body.value)
                    except ValueError:raise HTTPException(400,'기물과 도착 칸을 다시 선택하세요.')
                    if m not in b.legal_moves:p['feedback']=bad_move_reason(b,m)+' 감점 없이 다시 시도할 수 있어요.'
                    elif body.value!=s['line'][p.get('ply',0)]:
                        interaction='legal_alternative';p['feedback']='합법적인 수지만 이번 연습의 목표와 달라요. '+s['text']+' 다른 합법 수를 나쁜 수로 채점하지 않습니다.'
                    else:
                        interaction='correct_move';p['ply']=p.get('ply',0)+1;b.push(m)
                        reply=''
                        if p['ply']<len(s['line']):
                            r=chess.Move.from_uci(s['line'][p['ply']]);reply=' 상대의 예시 응수: '+NAMES[b.piece_at(r.from_square).piece_type]+' '+chess.square_name(r.from_square)+' → '+chess.square_name(r.to_square)+'.';b.push(r);p['ply']+=1
                        correct=p['ply']==len(s['line']);p['feedback']=s['reason'] if correct else '목표 수를 두었어요.'+reply+' 설명의 다음 내 수를 이어 두세요.'
                elif body.action=='answer' and s['kind']=='judge':
                    correct=body.value==s['answer'];p['feedback']=s['reason'] if correct else '다시 확인해 보세요. '+s['reason']+' 설명을 보고 다시 선택해도 감점은 없습니다.'
                else:raise HTTPException(400,'현재 단계에 맞는 행동을 선택하세요.')
                if correct:
                    interaction='step_complete';p['solved']=True
                    p['completed_steps']=sorted(set(p.get('completed_steps',[]))|{p['index']})
                    if len(p['completed_steps'])==len(c['steps']):p['done']=True
        saved['revision']+=1;saved['updated_at']=datetime.now(timezone.utc).isoformat();state[KEY]=saved
        ns['save_state'](code,state)
        return payload(state)|{'interaction':interaction}
