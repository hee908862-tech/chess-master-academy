"""Versioned diagnostic snapshots and transactional, resumable multi-ply responses."""
import copy
import json
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Literal
import chess
from fastapi import Header, HTTPException
from pydantic import BaseModel
from competencies import VERSION, COMPETENCIES, position_key, line_positions
from v9_server import LIB
from mate_explanation import explain_mate


def now(): return datetime.now(timezone.utc)
key = position_key

def footprint(item):
    # Inventory stores this alongside the already-validated immutable snapshot.
    return frozenset(item['position_keys']) if 'position_keys' in item else line_positions(item['fen'],item['line'])


@lru_cache(maxsize=1)
def inventory():
    pools = {c: [] for c, v in COMPETENCIES.items() if v['measured']}
    for pid in sorted(LIB):
        p = LIB[pid]
        try:
            b = chess.Board(p['fen']); b.push_uci(p['moves'][0]); initial = b.copy()
            line = p['moves'][1:]
            if not line or len(line) % 2 != 1 or not b.is_valid(): continue
            promotion = False
            positions={key(initial.fen())}
            for i, u in enumerate(line):
                m = chess.Move.from_uci(u)
                if m not in b.legal_moves: raise ValueError()
                promotion |= i % 2 == 0 and bool(m.promotion)
                b.push(m)
                positions.add(key(b.fen()))
            tags = p['themes']
            categories = []
            if b.is_checkmate() and any(t.startswith('mateIn') for t in tags): categories.append('mate')
            if len(line) >= 3: categories.append('calculation')
            if initial.is_capture(chess.Move.from_uci(line[0])): categories.append('capture')
            if 'defensiveMove' in tags: categories.append('defense')
            if promotion: categories.append('promotion')
            if 'endgame' in tags and len(initial.piece_map()) <= 10: categories.append('endgame')
            snapshot = {'puzzle_id':pid, 'fen':initial.fen(), 'line':line, 'tags':tags,
                        'position_keys':sorted(positions), 'rating':p['rating'], 'prior':p['moves'][0], 'version':VERSION}
            for c in categories: pools[c].append(snapshot)
        except (ValueError, KeyError, IndexError): continue
    return pools


class Start(BaseModel):
    mode: Literal['basic','targeted','recheck'] = 'basic'
    competency: str | None = None


class Action(BaseModel):
    session_id: str
    revision: int
    action: Literal['move','skip','next']
    move: str | None = None


def attach_journey(app, ns):
    db, execute, auth = ns['db'], ns['execute'], ns['auth']
    with db() as conn:
        execute(conn, 'CREATE TABLE IF NOT EXISTS journey_progress (code TEXT PRIMARY KEY, state TEXT NOT NULL)')

    def read(code):
        with db() as conn:
            r = execute(conn, 'SELECT state FROM journey_progress WHERE code=?', (code,)).fetchone()
            return json.loads(r['state']) if r else {'active':None, 'results':[], 'reserved':[]}

    @contextmanager
    def store(code):
        with db() as conn:
            if not ns['DATABASE_URL']: conn.execute('BEGIN IMMEDIATE')
            else: execute(conn,'SELECT pg_advisory_xact_lock(hashtext(?))',('chess-evidence:'+code,))
            default = {'active':None, 'results':[], 'reserved':[]}
            execute(conn, 'INSERT INTO journey_progress(code,state) VALUES(?,?) ON CONFLICT(code) DO NOTHING', (code,json.dumps(default)))
            r = execute(conn, 'SELECT state FROM journey_progress WHERE code=?' + (' FOR UPDATE' if ns['DATABASE_URL'] else ''), (code,)).fetchone()
            state = json.loads(r['state'])
            yield state
            execute(conn, 'UPDATE journey_progress SET state=? WHERE code=?', (json.dumps(state,ensure_ascii=False),code))

    def report(code, report_id=None):
        reports = read(code)['results']
        return next((r for r in reversed(reports) if report_id is None or r['id']==report_id),None)
    ns['journey_report'] = report
    ns['journey_seen'] = lambda code: {x['puzzle_id'] for x in read(code)['reserved']}
    ns['journey_positions'] = lambda code: {key(x['fen']) for x in read(code)['reserved']}
    ns['journey_active'] = lambda code: bool(read(code)['active'])

    def external(code):
        legacy = ns['get_state'](code)
        with db() as conn:
            row = execute(conn,'SELECT state FROM learning_progress WHERE code=?',(code,)).fetchone()
            learning = json.loads(row['state']) if row else {}
        ids, positions = set(), set()
        def scan(value):
            if isinstance(value,dict):
                if isinstance(value.get('fen'),str) and isinstance(value.get('line'),list):
                    try:
                        b=chess.Board(value['fen']); positions.add(key(b.fen()))
                        for uci in value['line']:
                            b.push_uci(uci); positions.add(key(b.fen()))
                    except (ValueError,TypeError): pass
                for k,v in value.items():
                    if k in ('puzzle_id','id') and isinstance(v,str): ids.add(v.removeprefix('puzzle-'))
                    if k=='fen' and isinstance(v,str): positions.add(key(v))
                    scan(v)
            elif isinstance(value,list):
                for v in value: scan(v)
        scan(legacy); scan(learning)
        ids.update(learning.get('seen',[]))
        for game in legacy.get('games',[]):
            try:
                board=chess.Board(game.get('initial_fen',chess.STARTING_FEN))
                for move in game.get('moves',[]):
                    board.push_uci(move); positions.add(key(board.fen()))
            except (ValueError,TypeError,AttributeError): pass
        active_old=legacy.get('assessment_v8')
        if active_old and 'seed' in active_old:
            from assessment_v8 import questions
            scan(questions(active_old['seed']))
        # Old aggregate records cannot establish absence of earlier exposure.
        uncertain = bool(legacy.get('puzzle_results') or legacy.get('assessment_v8') or legacy.get('assessment_history') or legacy.get('assessment_v8_history') or legacy.get('assessment_v8_latest') or legacy.get('assessment') or legacy.get('games') or legacy.get('completed_lessons'))
        return ids,positions,uncertain,learning

    def payload(s):
        if s['phase']=='complete': return {k:copy.deepcopy(s[k]) for k in ('session_id','revision','phase','report')}
        item=s['items'][s['index']]; b=chess.Board(s['fen'])
        q={'id':item['id'],'fen':s['fen'],'legal':[m.uci() for m in b.legal_moves] if s['phase']=='question' else [],
           'side':'white' if chess.Board(item['fen']).turn else 'black','competency':item['competency'],
           'label':COMPETENCIES[item['competency']]['label'],'goal':'상대 응수 뒤 원본 전술 수순을 끝까지 실행하세요.',
           'rating':item['rating'],'opponent_last_move':s.get('reply',item['prior']),
           'ply':s['correct'],'total_plies':(len(item['line'])+1)//2}
        out={k:copy.deepcopy(s[k]) for k in ('session_id','revision','phase','index','total','version')}
        out['question']=q
        if s['phase']=='feedback': out['feedback']=copy.deepcopy(item['feedback'])
        return out

    def begin_item(s):
        item=s['items'][s['index']]
        item['shown_at']=now().isoformat()
        s.update(phase='question',fen=item['fen'],offset=0,correct=0,submitted=[],played=[],reply=item['prior'])

    @app.get('/api/journey')
    def status(authorization: str | None = Header(default=None)):
        state=read(auth(authorization))
        return {'schema':'journey-v2','competencies':[{'id':k,**v} for k,v in COMPETENCIES.items()],
                'active':payload(state['active']) if state['active'] else None,
                'latest':state['results'][-1] if state['results'] else None,'results':state['results'],
                'legacy_notice':'이전 버전 진단 기록은 보존됩니다. 점수는 버전 간 비교하지 않습니다.'}

    @app.post('/api/journey/start')
    def start(body:Start, authorization: str | None = Header(default=None)):
        code=auth(authorization)
        with store(code) as state:
            ids,positions,uncertain,learning=external(code)
            if body.mode!='basic' and (body.competency not in COMPETENCIES or not COMPETENCIES[body.competency]['measured']):
                raise HTTPException(409,'검증된 자료가 없는 영역은 측정하지 않습니다.')
            if body.mode=='recheck':
                cards=learning.get('cards',{})
                linked=[]
                for attempt in learning.get('attempts',[]):
                    source=cards.get((attempt.get('selection') or {}).get('source_card'),{})
                    if (source.get('diagnosis') and source.get('category')==body.competency
                        and attempt.get('mode')=='verify' and attempt.get('fresh')
                        and not attempt.get('helped') and attempt.get('assessment_scope')=='full_line'):
                        linked.append(attempt)
                if not linked: raise HTTPException(409,'진단 원본 연습 뒤 연결된 미노출 적용 문제를 먼저 시도하세요.')
                dates=[datetime.fromisoformat(a['at']) for a in linked if a.get('at')]
                sources={a['selection']['source_card'] for a in linked}
                related={cid for cid,card in cards.items() if cid in sources or (card.get('selection') or {}).get('source_card') in sources}
                dates.extend(datetime.fromisoformat(a['at']) for a in learning.get('attempts',[]) if a.get('card_id') in related and a.get('at'))
                for cid in related:
                    for day,exposure in cards[cid].get('exposure',{}).items():
                        # Legacy day-only exposure rounds up, never shortens the seven-day gap.
                        dates.append(datetime.fromisoformat(exposure['last_at']) if exposure.get('last_at') else datetime.fromisoformat(day).replace(tzinfo=timezone.utc)+timedelta(days=1))
                if not dates or now()<max(dates)+timedelta(days=7): raise HTTPException(409,'연결된 훈련의 마지막 노출 후 7일이 지나야 재평가할 수 있습니다.')
            if state['active']: raise HTTPException(409,'저장된 진단을 먼저 이어서 완료하세요.')
            for x in state['reserved']: ids.add(x['puzzle_id']); positions.add(key(x['fen']))
            items=[]
            for c in ([body.competency] if body.mode!='basic' else list(inventory())):
                for lo,hi in ([(600,1200),(1200,1800)] if body.mode=='basic' else [(600,1200),(1200,1800),(1800,2400)]):
                    choices=[p for p in inventory()[c] if p['puzzle_id'] not in ids and lo<=p['rating']<hi and not positions.intersection(footprint(p))]
                    if not choices: continue
                    p=copy.deepcopy(secrets.choice(choices)); p.update(id=secrets.token_hex(8),competency=c,band=[lo,hi],independent=not uncertain,helped=False,first_attempt=True)
                    ids.add(p['puzzle_id']); positions.add(key(p['fen'])); items.append(p)
                    board=chess.Board(p['fen'])
                    for uci in p['line']:
                        board.push_uci(uci); positions.add(key(board.fen()))
            if not items: raise HTTPException(409,'조건에 맞는 미노출 국면이 없습니다. 기존 훈련을 이용하세요.')
            s={'session_id':secrets.token_hex(16),'revision':0,'version':VERSION,'mode':body.mode,'index':0,'total':len(items),'items':items,'started_at':now().isoformat()}
            begin_item(s); state['active']=s
            for item in items:
                board=chess.Board(item['fen'])
                state['reserved'].append({'puzzle_id':item['puzzle_id'],'fen':board.fen()})
                for uci in item['line']:
                    board.push_uci(uci)
                    state['reserved'].append({'puzzle_id':item['puzzle_id'],'fen':board.fen()})
            return payload(s)

    def finish_item(s, complete, reason, skipped=False):
        item=s['items'][s['index']]; b=chess.Board(item['fen']); frames=[]
        for u in (s['played'] if complete else item['line']):
            m=chess.Move.from_uci(u); san=b.san(m); b.push(m); frames.append({'move':u,'san':san,'fen':b.fen()})
        item.update(first_correct=s['correct']>0,complete=complete,correct_plies=s['correct'],total_plies=(len(item['line'])+1)//2,
                    submitted=copy.deepcopy(s['submitted']),expected=item['line'][::2],reason=reason,skipped=skipped,completed_at=now().isoformat())
        item['feedback']={k:copy.deepcopy(item[k]) for k in ('first_correct','complete','correct_plies','total_plies','submitted','expected','reason')}
        item['feedback'].update(fen=s['fen'],continuation=frames)
        if complete and chess.Board(s['fen']).is_checkmate():
            item['feedback']['mate_explanation']=explain_mate(chess.Board(s['fen']))
        s['phase']='feedback'

    def finish(s, previous):
        items=s['items']; areas=[]
        earlier=[i for r in previous if r['version']==VERSION for i in r['items']]
        accumulated=earlier+items
        for c,v in COMPETENCIES.items():
            rows=[i for i in items if i['competency']==c]; independent=sum(i['independent'] and not i['skipped'] for i in rows)
            known={key(i['fen']):i for i in accumulated if i['competency']==c and i['independent'] and not i['skipped']}
            evidence={'independent':len(known),'first_success':sum(i['first_correct'] for i in known.values()),
                      'full_success':sum(i['complete'] for i in known.values()),'version':VERSION,
                      'latest_at':max((i['completed_at'] for i in known.values()),default=None)}
            areas.append({'evidence':evidence,'id':c,'label':v['label'],'count':len(rows),'independent':independent,
                'first_success':sum(i['first_correct'] for i in rows),'full_success':sum(i['complete'] for i in rows),
                'partial':sum(i['first_correct'] and not i['complete'] for i in rows),'confidence':'근거 부족' if independent<5 else '표본 추가 확인 필요',
                'priority':'추가 확인','reason':v['scope']+' · 이 진단만으로 강점·약점을 확정하지 않습니다.',
                'items':[{k:copy.deepcopy(i[k]) for k in ('id','puzzle_id','fen','tags','submitted','expected','first_correct','complete','correct_plies','total_plies','reason','competency','rating','band','independent','shown_at','completed_at','helped','first_attempt')} for i in rows]})
        return {'id':s['session_id'],'at':now().isoformat(),'version':VERSION,'mode':s['mode'],'areas':areas,'items':copy.deepcopy(items),
            'recommendations':[{'competency':i['competency'],'label':COMPETENCIES[i['competency']]['label'],'item_id':i['id'],'reason':i['reason']} for i in items if not i['complete']],
            'limitations':['첫 시도·힌트 없는 원본 수순 일치의 관찰입니다. 합법 대안 전체는 검증하지 않았습니다.',
                '과거 노출을 확인할 수 없는 기존 기록이 있으면 독립 국면으로 계산하지 않습니다.',
                '공개 전술 퍼즐로 장기 계획·일반 종반 숙련도·공식 Elo를 추정하지 않습니다.'],
            'comparison':('지연 재평가 · 이전 같은 버전 독립 국면 '+str(sum(i['independent'] and not i['skipped'] for i in earlier))+'개 / 이번 '+str(sum(i['independent'] and not i['skipped'] for i in items))+'개. ' if s['mode']=='recheck' else '')+'난도·표본의 차이가 있어 변화율과 교육 효과를 단정하지 않습니다.'}

    @app.post('/api/journey/action')
    def action(body:Action, authorization: str | None = Header(default=None)):
        code=auth(authorization)
        external_ids,external_positions,uncertain,_=external(code)
        with store(code) as state:
            s=state['active']
            if not s or s['session_id']!=body.session_id or s['revision']!=body.revision: raise HTTPException(409,'진단 상태가 변경되었습니다. 저장 상태를 다시 확인하세요.')
            for item in s['items']:
                if uncertain or item['puzzle_id'] in external_ids or external_positions.intersection(footprint(item)):
                    item['independent']=False
            if body.action=='next':
                if s['phase']!='feedback': raise HTTPException(409,'문항 풀이를 먼저 마치세요.')
                s['index']+=1
                if s['index']==s['total']:
                    r=finish(s,state['results']); state['results'].append(r); state['active']=None
                    s.update(phase='complete',report=r)
                else: begin_item(s)
            else:
                if s['phase']!='question': raise HTTPException(409,'이미 채점한 문항입니다.')
                if body.action=='skip': finish_item(s,False,'미응답 또는 후속 수순 미완료: 원본 수순을 연습하세요.',True)
                else:
                    b=chess.Board(s['fen'])
                    try: m=chess.Move.from_uci(body.move or '')
                    except ValueError: raise HTTPException(400,'올바른 착수 형식이 아닙니다.')
                    if m not in b.legal_moves: raise HTTPException(400,'현재 국면에서 합법적인 수가 아닙니다.')
                    item=s['items'][s['index']]; expected=item['line'][s['offset']]
                    s['submitted'].append(body.move)
                    item.setdefault('responses',[]).append({'at':now().isoformat(),'fen':b.fen(),'move':body.move,'expected':expected})
                    b.push(m); s['played'].append(body.move); s['fen']=b.fen()
                    state['reserved'].append({'puzzle_id':item['puzzle_id'],'fen':b.fen()})
                    if body.move!=expected and not b.is_checkmate(): finish_item(s,False,'기준 수순과 다른 합법 수입니다. 대안의 가치는 미검증이며 오답으로 단정하지 않습니다.')
                    else:
                        s['correct']+=1; s['offset']+=1
                        if b.is_checkmate() or s['offset']==len(item['line']): finish_item(s,True,'상대 응수를 포함한 전체 수순을 완료했습니다.')
                        else:
                            reply=item['line'][s['offset']]; b.push_uci(reply); s['played'].append(reply); s.update(offset=s['offset']+1,fen=b.fen(),reply=reply)
            s['revision']+=1
            return payload(s)
