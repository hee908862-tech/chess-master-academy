"""Versioned diagnostic snapshots and transactional, resumable multi-ply responses."""
import copy
import json
import secrets
import gzip
import hashlib
import os
import threading
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Literal
import chess
from fastapi import Header, HTTPException
from pydantic import BaseModel
from competencies import VERSION, COMPETENCIES, position_key, line_positions
from v9_server import LIB, DATA_FILE
from mate_explanation import explain_mate
from journey_evidence import JOURNEY_VERSION, COVERAGE_POLICY, CUED, UNCUED, recheck_gate, additional_plan, build_report


def now(): return datetime.now(timezone.utc)
key = position_key

def footprint(item):
    # Inventory stores this alongside the already-validated immutable snapshot.
    return frozenset(item['position_keys']) if 'position_keys' in item else line_positions(item['fen'],item['line'])


def build_inventory():
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


INDEX_POLICY='journey-index-v1'
INDEX_PATH=Path(os.getenv('CMA_JOURNEY_INDEX',str(Path(__file__).with_name('journey-index.json.gz'))))
_inventory_lock=threading.Lock()
_prepared=None


def inventory():
    global _prepared
    if _prepared is not None:return _prepared
    if not _inventory_lock.acquire(timeout=.1):
        raise HTTPException(503,'진단 문제를 준비 중입니다. 잠시 후 저장 상태를 확인하고 다시 시작해 주세요.',headers={'Retry-After':'2'})
    try:
        if _prepared is not None:return _prepared
        try:
            with gzip.open(INDEX_PATH,'rt',encoding='utf8') as f:cached=json.load(f)
            digest=hashlib.sha256(DATA_FILE.read_bytes()).hexdigest()
            if cached['policy']!=INDEX_POLICY or cached['corpus_sha256']!=digest:raise ValueError('stale index')
            if set(cached['pools'])!={c for c,v in COMPETENCIES.items() if v['measured']}:raise ValueError('invalid index')
            _prepared={c:[cached['items'][pid] for pid in ids] for c,ids in cached['pools'].items()}
        except (OSError,ValueError,KeyError,TypeError):
            # Fallback performs no DB access and is single-flight. Deployment builds
            # the matching index ahead of serving traffic, so this is a recovery path.
            try:_prepared=build_inventory()
            except (OSError,ValueError) as exc:
                raise HTTPException(503,'진단 자료를 준비하지 못했습니다. 기존 기록은 유지됩니다. 잠시 후 다시 시도하세요.',headers={'Retry-After':'2'}) from exc
        return _prepared
    finally:_inventory_lock.release()


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
            if not ns['DATABASE_URL']: execute(conn,'BEGIN IMMEDIATE')
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

    def external_snapshot(code):
        legacy = ns['get_state'](code)
        with db() as conn:
            row = execute(conn,'SELECT state FROM learning_progress WHERE code=?',(code,)).fetchone()
            learning = json.loads(row['state']) if row else {}
        return dict(legacy),learning

    def external(code, snapshot=None):
        legacy,learning=snapshot if snapshot is not None else external_snapshot(code)
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
        if s.get('measurement_scope')==UNCUED and s['phase']=='question':
            for field in ('competency','label','rating','total_plies'):q.pop(field,None)
            q['goal']='이 국면에서 유효하다고 생각하는 수를 선택하고 상대 응수 뒤에도 계속 두세요.'
        out['measurement_scope']=s.get('measurement_scope','legacy_cued_execution')
        out['question']=q
        if s['phase']=='feedback': out['feedback']=copy.deepcopy(item['feedback'])
        return out

    def begin_item(s):
        item=s['items'][s['index']]
        item['shown_at']=now().isoformat()
        s.update(phase='question',fen=item['fen'],offset=0,correct=0,submitted=[],played=[],reply=item['prior'])

    @app.get('/api/journey')
    def status(authorization: str | None = Header(default=None)):
        code=auth(authorization);state=read(code)
        _,learning=external_snapshot(code)
        path=learning.get('path');active_training=learning.get('active')
        return {'preparing':_inventory_lock.locked(),'training':{'path_id':path['id'] if path else None,'path_done':path.get('done',False) if path else False,'active':bool(active_training and not active_training.get('done')),'has_path':bool(path)},
                'rechecks':{c:recheck_gate(learning,c,now()) for c,v in COMPETENCIES.items() if v['measured']},
                'additional':{c:additional_plan(state['results'],c,CUED) for c,v in COMPETENCIES.items() if v['measured']},
                'schema':'journey-v2','competencies':[{'id':k,**v} for k,v in COMPETENCIES.items()],
                'active':payload(state['active']) if state['active'] else None,
                'latest':state['results'][-1] if state['results'] else None,'results':state['results'],
                'legacy_notice':'이전 버전 진단 기록은 보존됩니다. 점수는 버전 간 비교하지 않습니다.'}

    @app.post('/api/journey/start')
    def start(body:Start, authorization: str | None = Header(default=None)):
        code=auth(authorization)
        if read(code)['active']:raise HTTPException(409,'저장된 진단을 먼저 이어서 완료하세요.')
        pools=inventory() # Always outside a user transaction, including cold fallback.
        snapshot=external_snapshot(code)
        ids,positions,uncertain,learning=external(code,snapshot)
        state=read(code)
        before=copy.deepcopy(state)
        if body.mode!='basic' and (body.competency not in COMPETENCIES or not COMPETENCIES[body.competency]['measured']):
            raise HTTPException(409,'검증된 자료가 없는 영역은 측정하지 않습니다.')
        if body.mode=='recheck':
            gate=recheck_gate(learning,body.competency,now())
            if not gate['eligible']:raise HTTPException(409,gate['reason'])
        if state['active']: raise HTTPException(409,'저장된 진단을 먼저 이어서 완료하세요.')
        for x in state['reserved']: ids.add(x['puzzle_id']); positions.add(key(x['fen']))
        items=[]
        measurement_scope=UNCUED if body.mode=='recheck' else CUED
        for c in ([body.competency] if body.mode!='basic' else list(pools)):
            for lo,hi in ([(600,1200),(1200,1800)] if body.mode=='basic' else [additional_plan(state['results'],c,measurement_scope)['band']]*3):
                choices=[p for p in pools[c] if p['puzzle_id'] not in ids and lo<=p['rating']<hi and not positions.intersection(footprint(p))]
                if not choices: continue
                p=copy.deepcopy(secrets.choice(choices)); p.update(id=secrets.token_hex(8),competency=c,band=[lo,hi],independent=not uncertain,app_new=True,prior_exposure_unknown=True,legacy_exposure_unknown=uncertain,helped=False,first_attempt=True)
                ids.add(p['puzzle_id']); positions.add(key(p['fen'])); items.append(p)
                board=chess.Board(p['fen'])
                for uci in p['line']:
                    board.push_uci(uci); positions.add(key(board.fen()))
        if not items: raise HTTPException(409,'조건에 맞는 미노출 국면이 없습니다. 기존 훈련을 이용하세요.')
        s={'session_id':secrets.token_hex(16),'revision':0,'version':JOURNEY_VERSION,'competency_version':VERSION,'coverage_policy':COVERAGE_POLICY,'measurement_scope':measurement_scope,'mode':body.mode,'index':0,'total':len(items),'items':items,'started_at':now().isoformat()}
        begin_item(s); state['active']=s
        for item in items:
            board=chess.Board(item['fen'])
            state['reserved'].append({'puzzle_id':item['puzzle_id'],'fen':board.fen()})
            for uci in item['line']:
                board.push_uci(uci)
                state['reserved'].append({'puzzle_id':item['puzzle_id'],'fen':board.fen()})
        with store(code) as current:
            if current!=before or external_snapshot(code)!=snapshot:
                raise HTTPException(409,'다른 화면에서 기록이 바뀌었습니다. 저장 상태를 확인한 뒤 다시 시작해 주세요.')
            current.update(state)
        return payload(s)

    def finish_item(s, complete, reason, skipped=False, outcome=None):
        item=s['items'][s['index']]; b=chess.Board(item['fen']); frames=[]
        for u in (s['played'] if complete else item['line']):
            m=chess.Move.from_uci(u); san=b.san(m); b.push(m); frames.append({'move':u,'san':san,'fen':b.fen()})
        item.update(first_correct=s['correct']>0,complete=complete,correct_plies=s['correct'],total_plies=(len(item['line'])+1)//2,
                    submitted=copy.deepcopy(s['submitted']),expected=item['line'][::2],reason=reason,skipped=skipped,completed_at=now().isoformat())
        item['outcome']=outcome or ('completed' if complete else 'partial_execution' if skipped and s['submitted'] else 'not_answered' if skipped else 'unverified_alternative')
        item['feedback']={k:copy.deepcopy(item[k]) for k in ('first_correct','complete','correct_plies','total_plies','submitted','expected','reason','outcome')}
        item['feedback'].update(fen=s['fen'],continuation=frames)
        if complete and chess.Board(s['fen']).is_checkmate():
            item['feedback']['mate_explanation']=explain_mate(chess.Board(s['fen']))
        s['phase']='feedback'

    def finish(s, previous):
        return build_report(s,previous,now())

    @app.post('/api/journey/action')
    def action(body:Action, authorization: str | None = Header(default=None)):
        code=auth(authorization)
        external_ids,external_positions,uncertain,_=external(code)
        with store(code) as state:
            s=state['active']
            if not s or s['session_id']!=body.session_id or s['revision']!=body.revision: raise HTTPException(409,'진단 상태가 변경되었습니다. 저장 상태를 다시 확인하세요.')
            for item in s['items']:
                if uncertain:item['independent']=False
                if item['puzzle_id'] in external_ids or external_positions.intersection(footprint(item)):
                    item['independent']=False
                    item['app_new']=False
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
                    if body.move!=expected and not b.is_checkmate():
                        if item['competency']=='mate' and b.is_stalemate():
                            finish_item(s,False,'스테일메이트로 끝났습니다. 체크메이트 목표와 다른 결과임을 규칙으로 확인했습니다.',outcome='verified_non_mate')
                        else:finish_item(s,False,'기준 수순과 다른 합법 수입니다. 미검증 대안으로 판단을 보류하며 실패나 약점 근거에 넣지 않습니다.',outcome='unverified_alternative')
                    else:
                        s['correct']+=1; s['offset']+=1
                        if b.is_checkmate() or s['offset']==len(item['line']): finish_item(s,True,'상대 응수를 포함한 전체 수순을 완료했습니다.')
                        else:
                            reply=item['line'][s['offset']]; b.push_uci(reply); s['played'].append(reply); s.update(offset=s['offset']+1,fen=b.fen(),reply=reply)
            s['revision']+=1
            return payload(s)
