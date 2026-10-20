from engine_budget import open_engine, EngineBusy
"""Evidence-based learning, isolated from legacy progress JSON writes.
New records use one locked row per account (SQLite BEGIN IMMEDIATE / PostgreSQL
FOR UPDATE). No accounts, old records, or corpus entries are rewritten.
"""
import copy
from growth_model import credit_cycle, latest_cycle_report, cycle_status
import hashlib
import json
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import chess
import chess.engine
from fastapi import Header, HTTPException, Query
from pydantic import BaseModel, Field
from v9_server import LIB, THEMES
from competencies import VERSION as COMPETENCY_VERSION, COMPETENCIES, supports, line_positions

CATEGORIES = {key: value['label'] for key, value in COMPETENCIES.items()}
CONCEPTS = {
 'strategy': '장기 계획 과제는 아직 검증된 자료가 없어 측정하지 않습니다.',
 'calculation': '후보수마다 상대의 체크·포획을 먼저 확인하고 응수를 한 수 더 읽으세요.',
 'endgame': '킹의 활동과 폰의 승격 경로를 함께 확인하세요. 이 훈련은 테이블베이스 판정이 아닙니다.',
 'promotion': '승격 기물을 고르기 전에 체크메이트와 스테일메이트 여부를 확인하세요.',
 'mate': '체크 이후 상대 킹의 도망갈 칸, 잡기, 막기를 모두 확인하세요.',
 'capture': '잡은 뒤 상대의 되잡기와 체크를 계산하세요. 기물 가치만으로 결론 내리지 마세요.',
 'defense': '체크 중이면 킹 이동·공격 기물 포획·가로막기 중 합법적인 대응을 확인하세요.'}


def training_band(report, competency):
    rows=[i for i in report.get('items',[]) if i.get('competency')==competency and i.get('submitted') and i.get('rating') and i.get('outcome') in ('completed','partial_execution','verified_error','verified_non_mate')]
    if len(rows)<2:return (600,1200)
    solved=[i['rating'] for i in rows if i.get('complete')]
    anchor=sorted(solved)[len(solved)//2] if solved else min(i['rating'] for i in rows)-200
    anchor=max(800,min(1600,anchor))
    return (max(600,anchor-300),min(1800,anchor+150))


def now():
    return datetime.now(timezone.utc)


def category(board, move=None, themes=()):
    if any(t.startswith('mate') for t in themes): return 'mate'
    if 'promotion' in themes or 'underPromotion' in themes or (move and move.promotion): return 'promotion'
    if board.is_check() or 'defensiveMove' in themes: return 'defense'
    if 'endgame' in themes or len(board.piece_map()) <= 8: return 'endgame'
    if move and board.is_capture(move): return 'capture'
    return 'calculation'


def frames(board, moves):
    result = []
    b = board.copy()
    for u in moves:
        m = chess.Move.from_uci(u)
        if m not in b.legal_moves: break
        san = b.san(m)
        b.push(m)
        result.append({'move': u, 'san': san, 'fen': b.fen()})
    return result


def explain(board, move):
    """Only facts proven by the rules; no inferred tactical narrative."""
    facts = []
    if board.is_check():facts.append('현재 체크: '+', '.join(chess.square_name(s) for s in board.checkers())+'의 공격에 대응합니다')
    if board.is_capture(move): facts.append('기물을 포획합니다' + (' (앙파상)' if board.is_en_passant(move) else ''))
    if board.is_castling(move): facts.append('캐슬링으로 킹과 룩을 이동합니다')
    if move.promotion: facts.append(chess.piece_name(move.promotion) + '으로 승격합니다')
    b = board.copy(); b.push(move)
    if b.is_checkmate(): facts.append('상대의 합법적인 체크 회피 수가 없어 메이트입니다')
    elif b.is_check(): facts.append('상대 킹을 체크합니다')
    elif b.is_stalemate(): facts.append('상대가 체크 없이 둘 수 있는 수가 없어 스테일메이트입니다')
    if not facts: facts.append(f'{chess.square_name(move.from_square)}에서 {chess.square_name(move.to_square)}로 이동합니다')
    return ' · '.join(facts)


class Start(BaseModel):
    card_id: str | None = None
    mode: Literal['practice', 'verify', 'situation_practice', 'situation_verify'] = 'practice'
    fresh: bool = False
    category: str | None = None
    similar_to: str | None = None
    pause_session_id: str | None = None
    pause_revision: int | None = None


class Resume(BaseModel):
    session_id: str
    active_id: str | None = None
    active_revision: int | None = None


class Action(BaseModel):
    session_id: str
    revision: int
    action: Literal['move', 'hint', 'reveal', 'refutation', 'undo']
    move: str | None = None


class PathAction(BaseModel):
    pause_session_id: str | None = None
    pause_revision: int | None = None
    action: Literal['continue', 'acknowledge', 'new'] = 'continue'
    path_id: str | None = None
    revision: int | None = None


class DiagnosisSource(BaseModel):
    report_id: str
    item_id: str


class ReplaceTask(DiagnosisSource):
    card_id: str
    session_id: str
    revision: int


class Settings(BaseModel):
    intervals: list[int] = Field(min_length=1, max_length=5)


def evidence_groups(rows):
    """Never compare first-move, full-line, engine-play or unversioned evidence."""
    buckets={}
    for row in rows:
        version=row.get('competency_version') or 'unrecorded'
        scope=('engine_situation' if row.get('mode','').startswith('situation')
               else row.get('assessment_scope') or 'unrecorded')
        buckets.setdefault((version,scope),[]).append(row)
    result=[]
    for (version,scope),attempts in sorted(buckets.items()):
        independent=[a for a in attempts if a.get('independent_kind') in ('novel','delayed')
                     and isinstance(a.get('success'),bool) and not a.get('helped')]
        latest={}
        for a in sorted(independent,key=lambda x:x.get('at','')):
            position=a.get('position') or a['card_id']
            latest.pop(position,None); latest[position]=a
        comparable=list(latest.values())
        rate=lambda rows: round(100*sum(a['success'] for a in rows)/len(rows)) if len(rows)==5 else None
        known=version!='unrecorded' and scope!='unrecorded'
        result.append({'version':version,'assessment_scope':scope,'count':len(attempts),
            'independent':len(independent),'distinct':len(comparable),
            'novel':sum(a['independent_kind']=='novel' for a in independent),
            'delayed':sum(a['independent_kind']=='delayed' for a in independent),
            'recent':rate(comparable[-5:]) if known else None,
            'previous':rate(comparable[-10:-5]) if known else None,
            'recent_n':min(5,len(comparable)) if known else 0,
            'previous_n':min(5,max(0,len(comparable)-5)) if known else 0,
            'insufficient':not known or len(comparable)<5,
            'trend_available':known and len(comparable)>=10,
            'reference_only':version!=COMPETENCY_VERSION or scope!='full_line'})
    return result


def attach_learning(app, ns):
    execute, db, auth = ns['execute'], ns['db'], ns['auth']
    with db() as conn:
        execute(conn, 'CREATE TABLE IF NOT EXISTS learning_progress (code TEXT PRIMARY KEY, state TEXT NOT NULL)')

    def learning_active(code):
        with db() as conn:
            row=execute(conn,'SELECT state FROM learning_progress WHERE code=?',(code,)).fetchone()
        active=json.loads(row['state']).get('active') if row else None
        return bool(active and not active.get('done'))
    ns['learning_active']=learning_active

    def normalize_cards(state):
        for card in state['cards'].values():
            if 'tags' not in card:
                puzzle = LIB.get(card['id'].removeprefix('puzzle-')) if card['id'].startswith('puzzle-') else None
                card['tags'] = sorted(set(puzzle['themes']) & set(THEMES)) if puzzle else proven_tags(card)
                card['tag_evidence'] = 'Lichess 원본 학습 태그' if puzzle else 'python-chess 규칙으로 확인된 특징'

    @contextmanager
    def store(code):
        with db() as conn:
            if not ns['DATABASE_URL']: execute(conn,'BEGIN IMMEDIATE')
            else: execute(conn,'SELECT pg_advisory_xact_lock(hashtext(?))',('chess-evidence:'+code,))
            default = {'schema': 1, 'cards': {}, 'attempts': [], 'seen': [], 'intervals': [1, 3, 7], 'active': None}
            execute(conn, 'INSERT INTO learning_progress(code,state) VALUES(?,?) ON CONFLICT(code) DO NOTHING', (code, json.dumps(default)))
            suffix = ' FOR UPDATE' if ns['DATABASE_URL'] else ''
            row = execute(conn, 'SELECT state FROM learning_progress WHERE code=?' + suffix, (code,)).fetchone()
            state = json.loads(row['state'])
            normalize_cards(state)
            yield state
            execute(conn, 'UPDATE learning_progress SET state=? WHERE code=?', (json.dumps(state, ensure_ascii=False), code))

    def context(code):
        # Called under the shared evidence transaction lock before selecting a new position.
        legacy = copy.deepcopy(ns['get_state'](code))
        legacy['_journey_seen'] = list(ns.get('journey_seen', lambda _: set())(code))
        legacy['_journey_positions'] = list(ns.get('journey_positions', lambda _: set())(code))
        legacy['_journey_report'] = ns.get('journey_report', lambda *_: None)(code)
        return legacy

    def diagnosis_card(state, report, item):
        if item.get('competency') not in CATEGORIES or not COMPETENCIES[item['competency']]['measured']:
            raise HTTPException(409, '이 영역의 검증된 훈련 자료가 아직 없습니다.')
        try:
            board = chess.Board(item['fen'])
            if not board.is_valid() or board.is_game_over() or not item['line']: raise ValueError()
            for uci in item['line']:
                move = chess.Move.from_uci(uci)
                if move not in board.legal_moves: raise ValueError()
                board.push(move)
        except (KeyError, ValueError, TypeError):
            raise HTTPException(409, '진단에 저장된 원본 위치·수순을 확인할 수 없어 훈련을 만들지 않았습니다.')
        key = 'diagnosis-' + hashlib.sha256((str(report['id']) + ':' + str(item['id'])).encode()).hexdigest()[:24]
        if key in state['cards']: return state['cards'][key]
        provenance = {'report_id': report['id'], 'item_id': item['id'], 'version': report.get('version'),
                      'reason': item.get('reason', ''), 'first_correct': item.get('first_correct'),
                      'complete': item.get('complete'), 'correct_plies': item.get('correct_plies'),
                      'total_plies': item.get('total_plies'), 'submitted': copy.deepcopy(item.get('submitted', []))}
        card = {'id': key, 'puzzle_id': item.get('puzzle_id'), 'title': '진단에서 이어지는 수순 연습',
                'fen': item['fen'], 'line': list(item['line']), 'category': item['competency'],
                'tags': sorted(set(item.get('tags', []))), 'tag_evidence': '진단에 보존된 원본 태그',
                'source': '완료 진단의 검증된 위치·수순', 'context': '이 위치는 진단에서 이미 노출되었습니다. 반복 성공은 새 독립 진단이 아닙니다.',
                'rating':item.get('rating'), 'created_at':now().isoformat(), 'diagnosis': provenance, 'full_line': True, 'prior_exposed': True,
                'due': now().isoformat(), 'successes': 0}
        state['cards'][key] = card
        return card

    @app.post('/api/learning/from-diagnosis')
    def from_diagnosis(body: DiagnosisSource, authorization: str | None = Header(default=None)):
        code = auth(authorization)
        report = ns.get('journey_report', lambda *_: None)(code, body.report_id)
        if not report or report.get('id') != body.report_id: raise HTTPException(404, '완료한 진단 결과를 찾을 수 없습니다.')
        item = next((i for i in report.get('items', []) if i.get('id') == body.item_id), None)
        if not item: raise HTTPException(404, '이 진단의 문항 근거를 찾을 수 없습니다.')
        with store(code) as state:
            legacy = context(code)
            path = state.get('path')
            if path and not path['done']:
                existing = state['cards'].get(path.get('source_card'), {}).get('diagnosis', {})
                if existing.get('report_id') == body.report_id and existing.get('item_id') == body.item_id:
                    active=state.get('active')
                    if active and not active['done'] and active.get('path_id')!=path['id']:
                        raise HTTPException(409, '진행 중인 다른 훈련의 착수를 보존했습니다. 먼저 완료해 주세요.')
                    if path['current']==0 and path['steps'][0]['status']=='pending':
                        begin(state,state['cards'][path['source_card']],'practice')
                        state['active'].update(path_id=path['id'],path_step=0)
                        path['steps'][0]['status']='active'
                        sync_path(state)
                    if state.get('active'):record_exposure(state['cards'][state['active']['card_id']])
                    return {'path': public_path(state), 'active': payload(state), 'diagnosis': existing}
                raise HTTPException(409, {'code':'active_learning_path','path_id':path['id'],'message':'진행 중인 경로를 보존했습니다. 이어서 완료한 뒤 선택한 진단 훈련을 시작하세요.'})
            if state.get('active') and not state['active']['done']:
                raise HTTPException(409, '진행 중인 훈련을 먼저 마쳐 주세요. 현재 착수는 보존했습니다.')
            card = diagnosis_card(state, report, item)
            create_path(state, legacy, card)
            begin(state, card, 'practice')
            state['active'].update(path_id=state['path']['id'], path_step=0)
            state['path']['steps'][0]['status']='active'
            sync_path(state)
            return {'path': public_path(state), 'active': payload(state), 'diagnosis': card['diagnosis']}

    @app.post('/api/learning/cycle/start')
    def cycle_start(body: DiagnosisSource, authorization: str | None = Header(default=None)):
        code=auth(authorization)
        with store(code) as state:
            report=ns.get('journey_report',lambda *_:None)(code,body.report_id)
            latest=ns.get('journey_cycle_report',lambda *_:None)(code)
            if not report or not latest or latest['id']!=report['id']:
                raise HTTPException(409,'현재 진단의 추천 훈련을 선택해 주세요.')
            task=next((t for t in report.get('training_plan',[]) if t['id']==body.item_id),None)
            if not task:raise HTTPException(404,'추천 과제를 찾을 수 없습니다.')
            cycle=state.setdefault('cycles',{}).setdefault(report['id'],{'cards':{},'completed':{}})
            active=state.get('active')
            reference={'report_id':report['id'],'task_id':task['id']}
            paused=next((v for v in state.get('paused',{}).values() if v.get('growth_task')==reference),None)
            if paused:raise HTTPException(409,'보존된 추천 훈련이 있습니다. 훈련실의 저장된 훈련 이어하기를 선택하세요.')
            if active and not active['done']:
                if active.get('growth_task')==reference:
                    record_exposure(state['cards'][active['card_id']])
                    return payload(state)
                raise HTTPException(409,'진행 중인 훈련을 먼저 마쳐 주세요. 착수는 저장되어 있습니다.')
            if task['id'] in cycle['completed']:raise HTTPException(409,'이미 마친 추천 과제예요. 다음 과제를 선택해 주세요.')
            card=state['cards'].get(cycle['cards'].get(task['id']))
            if not card:
                item=next(i for i in report['items'] if i['id']==task['item_id'])
                source=diagnosis_card(state,report,item)
                card=source if task['kind']=='original' else new_puzzle(state,task['competency'],context(code),source['id'],rating_band=training_band(report,task['competency']))
                card['full_line']=True
                cycle['cards'][task['id']]=card['id']
            begin(state,card,'practice',fresh=task['kind']=='application')
            state['active']['growth_task']=reference
            return payload(state)

    @app.post('/api/learning/retention/start')
    def retention_start(body: DiagnosisSource, authorization: str | None = Header(default=None)):
        code=auth(authorization)
        with store(code) as state:
            if state.get('active') and not state['active']['done']:
                raise HTTPException(409,'진행 중인 훈련을 보존했습니다. 먼저 이어서 마쳐 주세요.')
            report=ns.get('journey_report',lambda *_:None)(code,body.report_id)
            item=next((i for i in (report or {}).get('items',[]) if i['id']==body.item_id),None)
            if not item:raise HTTPException(404,'진단 근거를 찾을 수 없습니다.')
            source=diagnosis_card(state,report,item)
            card=new_puzzle(state,item['competency'],context(code),source['id'],rating_band=training_band(report,item['competency']))
            card['full_line']=True
            return begin(state,card,'verify',fresh=True)

    @app.post('/api/learning/cycle/easier')
    def easier(body: ReplaceTask, authorization: str | None = Header(default=None)):
        code=auth(authorization)
        with store(code) as state:
            report=ns.get('journey_cycle_report',lambda *_:None)(code)
            cycle=state.get('cycles',{}).get(body.report_id)
            task=next((t for t in (report or {}).get('training_plan',[]) if t['id']==body.item_id),None)
            active=state.get('active')
            if not report or report['id']!=body.report_id or not cycle or not task or task['kind']!='application':
                raise HTTPException(409,'현재 추천의 새 적용 과제만 교체할 수 있습니다.')
            if body.item_id in cycle.get('completed',{}):raise HTTPException(409,'완료 과제는 교체할 수 없습니다.')
            if not active or active['done'] or active['id']!=body.session_id or active['revision']!=body.revision or active['card_id']!=body.card_id or active.get('growth_task')!={'report_id':body.report_id,'task_id':body.item_id}:
                raise HTTPException(409,'훈련 위치가 변경되었습니다. 저장 상태를 다시 확인하세요.')
            old=state['cards'][body.card_id]
            source_id=old.get('selection',{}).get('source_card')
            rating=old.get('rating')
            if not source_id or not rating:raise HTTPException(409,'난도 근거가 없어 안전하게 교체하지 않았습니다.')
            try:card=new_puzzle(state,task['competency'],context(code),source_id,rating_band=(max(400,rating-500),rating-1))
            except HTTPException as exc:
                if exc.status_code!=409:raise
                raise HTTPException(409,'같은 학습 목표의 더 낮은 난도 미노출 문제가 없어 교체하지 않았습니다. 현재 착수와 도움 기록은 그대로입니다.') from exc
            card['full_line']=True
            cycle.setdefault('replacements',[]).append({'task_id':body.item_id,'at':now().isoformat(),'session':copy.deepcopy(active)})
            cycle['cards'][body.item_id]=card['id']
            begin(state,card,'practice',fresh=True)
            state['active']['growth_task']={'report_id':body.report_id,'task_id':body.item_id}
            return payload(state)

    @contextmanager
    def engine():
        path = ns['STOCKFISH_PATH']
        if not path or not Path(path).is_file():
            raise HTTPException(503, 'Stockfish가 연결되지 않았습니다. 실전 실수 분석·대안 수 평가·상황 대국은 사용할 수 없습니다. 원본 수순 퍼즐은 이용할 수 있습니다.')
        eng = None
        try:
            eng = open_engine(path, timeout=5)
            eng.configure({'Threads': 1, 'Hash': 16})
            yield eng
        except (chess.engine.EngineError, TimeoutError, OSError) as exc:
            raise HTTPException(503, '엔진 분석에 실패했습니다. 기록은 변경하지 않았습니다. 다시 시도하세요.') from exc
        finally:
            if eng:
                try: eng.quit()
                except Exception: pass

    def analyse(eng, board, side):
        info = eng.analyse(board, chess.engine.Limit(time=.12))
        pv = [m.uci() for m in info.get('pv', [])][:8]
        return info['score'].pov(side).score(mate_score=10000), pv

    def proven_tags(card):
        b = chess.Board(card['fen']); m = chess.Move.from_uci(card['line'][0])
        tags = []
        if m not in b.legal_moves: return tags
        if b.is_check(): tags.append('defensiveMove')
        if m.promotion:
            tags.append('promotion')
            if m.promotion != chess.QUEEN: tags.append('underPromotion')
        b.push(m)
        if b.is_checkmate(): tags.append('mateIn1')
        return tags

    def public_card(card):
        return {**{k: card[k] for k in ('id', 'title', 'category', 'source', 'due', 'successes', 'tags', 'tag_evidence')}, 'diagnosis': card.get('diagnosis'), 'rating':card.get('rating'), 'puzzle_id':card.get('puzzle_id'), 'created_at':card.get('created_at'), 'last_outcome':card.get('last_outcome'), 'full_line':bool(card.get('full_line')), 'category_label':COMPETENCIES.get(card['category'],{}).get('label',card['category'])}

    def payload(state):
        s = state['active']
        if not s: return None
        card = state['cards'][s['card_id']]
        b = chess.Board(s['fen'])
        verify = 'verify' in s['mode']
        return {'session_id': s['id'], 'revision': s['revision'], 'card_id': card['id'],
                'fen': s['fen'], 'legal': [] if s['done'] else [m.uci() for m in b.legal_moves],
                'assessment_scope':'full_line' if card.get('full_line') else 'first_move', 'rating':None if verify and not s['done'] else card.get('rating'), 'side': s['side'], 'mode': s['mode'], 'done': s['done'], 'turns': s['turns'],
                'category': None if verify and not s['done'] else CATEGORIES[card['category']],
                'concept': None if verify and not s['done'] else CONCEPTS[card['category']],
                'source': card['source'], 'goal': s['goal'], 'message': s.get('message', ''),
                'opponent_last_move': s.get('opponent_last_move'), 'hint_level': s['hints'],
                'context': card.get('context', '직전 위치 기록이 없어 변화의 의미를 추측하지 않습니다.'),
                'explanation': s.get('explanation'), 'playback': s.get('playback', []),
                'growth_task':s.get('growth_task'), 'outcome': s.get('outcome'), 'selection': None if verify and not s['done'] else s.get('selection'), 'path_id': s.get('path_id'), 'premove': False}

    def finish(state, s, success):
        if s['done']: return
        card = state['cards'][s['card_id']]
        stamp = now()
        day = stamp.date().isoformat()
        exposure = card.setdefault('exposure', {}).setdefault(day, {'hints': 0, 'revealed': False, 'wrong': 0})
        delayed = any(date < day for date in card.get('exposure', {})) or any(a['card_id'] == card['id'] and a['at'][:10] < day for a in state['attempts'])
        completed_today = any(a['card_id'] == card['id'] and a['at'][:10] == day and a['success'] for a in state['attempts'])
        current_helped=bool(s['hints'] or s['undone'] or s['revealed'])
        previous=s.get('prior_help',{})
        revealed = s['revealed'] or exposure['revealed']
        helped = bool(s['hints'] or s['undone'] or exposure['hints'])
        wrong = max(s['wrong'], exposure['wrong'])
        status = ('revealed_success' if revealed else 'hinted_success' if helped
                  else 'unaided_repeat_success' if completed_today else 'retry_success' if wrong
                  else 'later_unaided_success' if delayed else 'unaided_first_success' if s.get('first_exposure', s['fresh']) else 'unaided_repeat_success') if success else 'unverified_alternative' if success is None else 'not_yet'
        attempt = {'card_id': card['id'], 'at': stamp.isoformat(), 'category': card['category'],
                   'competency_version': COMPETENCY_VERSION, 'diagnosis': card.get('diagnosis'), 'assessment_scope': 'full_line' if card.get('full_line') else 'first_move',
                   'mode': s['mode'], 'success': success, 'status': status,
                   'position': ' '.join(card['fen'].split()[:4]),
                   'selection': s.get('selection'), 'path_id': s.get('path_id'),
                   'current_helped':current_helped, 'current_hint_level':s['hints'],
                   'prior_helped':bool(previous.get('hints') or previous.get('revealed')),
                   'prior_help_known':'prior_help' in s,
                   'completion_basis':'evaluation_maintenance' if s['mode'].startswith('situation') else 'reference_line',
                   'turns':s['turns'], 'hint_level': max(s['hints'], exposure['hints']), 'helped': bool(helped or revealed), 'wrong': wrong, 'fresh': s['fresh']}
        eligible_result = status in ('unaided_first_success', 'later_unaided_success') or success is False
        prior = [a for a in state['attempts'] if a['card_id'] == card['id']]
        independent_kind = None
        if not card.get('prior_exposed') and eligible_result and not helped and not revealed and wrong <= (0 if success else 1):
            if s['fresh'] and not prior: independent_kind = 'novel'
            elif delayed and not any(a['at'][:10] == day for a in prior): independent_kind = 'delayed'
        attempt['independent_kind'] = independent_kind
        state['attempts'].append(attempt)
        card['last_outcome']={'at':attempt['at'],'status':attempt['status'],'success':success,'scope':attempt['assessment_scope']}
        credited_today = card.get('credited_date') == day
        eligible = not card.get('prior_exposed') and bool(success) and status in ('unaided_first_success', 'later_unaided_success') and not credited_today
        if eligible:
            card['successes'] += 1
            card['credited_date'] = day
        days = state['intervals'][min(max(card['successes'] - 1, 0), len(state['intervals']) - 1)] if success else 1
        if not credited_today:
            card['due'] = (stamp + timedelta(days=days)).isoformat()
        credit_cycle(state,s,attempt)
        s.update(done=True, outcome=attempt, message='학습 기록을 저장했습니다.' if success else '아직 목표에 도달하지 못했습니다. 기록을 저장했습니다.')

    @app.get('/api/learning/dashboard')
    def dashboard(authorization: str | None = Header(default=None), offset: int = Query(0, ge=0)):
        code = auth(authorization)
        with db() as conn:
            row=execute(conn,'SELECT state FROM learning_progress WHERE code=?',(code,)).fetchone()
        state=json.loads(row['state']) if row else {'cards':{},'attempts':[],'intervals':[1,3,7],'active':None}
        normalize_cards(state) # Read compatibility only; the next write persists additive fields.
        due = [public_card(c) for c in state['cards'].values() if c['due'] <= now().isoformat()]
        skills = []
        for key, label in CATEGORIES.items():
            rows = [a for a in state['attempts'] if a['category'] == key]
            groups=evidence_groups(rows)
            primary=next((g for g in groups if not g['reference_only']),
                {'independent':0,'distinct':0,'recent':None,'previous':None,'novel':0,'delayed':0,
                 'insufficient':True,'trend_available':False,'recent_n':0,'previous_n':0})
            skills.append({'id':key,'name':label,'count':len(rows),'groups':groups,
                'rate_version':COMPETENCY_VERSION,'rate_scope':'full_line',
                **{k:primary[k] for k in ('independent','distinct','recent','previous','novel','delayed','insufficient','trend_available','recent_n','previous_n')},
                'measured':COMPETENCIES[key]['measured'],'scope':COMPETENCIES[key]['scope'],
                'first_move_count':sum(a.get('assessment_scope')=='first_move' for a in rows),
                'full_line_count':sum(a.get('assessment_scope')=='full_line' for a in rows),
                'practice_count':sum(a['mode'] in ('practice','situation_practice') for a in rows),
                'verification_count':sum(a['mode'] in ('verify','situation_verify') for a in rows),
                'transfer':sum(bool((a.get('selection') or {}).get('overlap')) and a['fresh'] and a['mode']=='verify' and a['status']=='unaided_first_success' for a in rows)})
        eligible=[s for s in skills if s['measured'] and not s['insufficient'] and s['recent']<100]
        lowest=min((s['recent'] for s in eligible),default=None)
        priorities=[s for s in eligible if s['recent']==lowest]
        weakest=priorities[0] if len(priorities)==1 else None
        return {'competency_version': COMPETENCY_VERSION, 'due': due[:50], 'due_count':len(due), 'cards': [public_card(c) for c in list(state['cards'].values())[::-1][offset:offset+50]][::-1],
                'cards_total':len(state['cards']), 'cards_next':offset+50 if offset+50<len(state['cards']) else None,
                'attempts': state['attempts'][-50:][::-1], 'skills': skills, 'intervals': state['intervals'],
                'active': payload(state), 'paused':[payload({**state,'active':v}) for v in state.get('paused',{}).values()], 'path': public_path(state), 'recommended': weakest['id'] if weakest else None,
                'reason': '최근 풀이에서 끝까지 잇지 못한 수순을 먼저 연습해요.' if weakest else '아직 뚜렷한 차이가 없어요. 새로운 문제로 여러 분야를 고르게 연습해 보세요.',
                'engine': bool(ns['STOCKFISH_PATH'] and Path(ns['STOCKFISH_PATH']).is_file()),
                'notice': '공통 역량 이름을 사용하지만 이 지도는 훈련 기록입니다. 성공률과 추천은 같은 버전·같은 측정 범위 안에서만 계산합니다. 구형·미기록 버전과 첫 수 판단은 별도 참고이며 전체 수순 근거로 합산하지 않습니다. 각 비교 구간에 독립 국면 5개가 없으면 추세를 표시하지 않습니다. 미출제는 기록된 문제 ID와 전체 원본 수순의 국면 기준이며, 식별 기록이 없는 과거·외부 노출까지 보장하지 않습니다. 기존 진단·대국 통계는 기록 메뉴에 보존됩니다. 실제 레이팅이 아닙니다.'}

    @app.post('/api/learning/settings')
    def settings(body: Settings, authorization: str | None = Header(default=None)):
        if any(d < 1 or d > 365 for d in body.intervals) or sorted(set(body.intervals)) != body.intervals:
            raise HTTPException(400, '복습 간격은 1~365일 사이의 증가하는 정수로 입력하세요.')
        with store(auth(authorization)) as state: state['intervals'] = body.intervals
        return {'intervals': body.intervals}

    @app.post('/api/learning/import/{index}')
    def import_game(index: int, authorization: str | None = Header(default=None)):
        code = auth(authorization)
        games = ns['get_state'](code).get('games', [])
        if not 0 <= index < len(games): raise HTTPException(404, '대국을 찾을 수 없습니다.')
        game = games[index]
        moves = game.get('moves', [])
        if len(moves) > 200: raise HTTPException(400, '200반수 이하의 대국만 지원합니다.')
        side = game.get('color', 'white') == 'white'
        candidates = []
        with engine() as eng:
            rows = ns['build_review_rows'](eng, game, index, moves)['moves']
            for row in sorted(rows, key=lambda r: r['centipawn_loss'], reverse=True):
                b = chess.Board(row['before_fen'])
                if b.turn != side or row['centipawn_loss'] < 96 or not row['best_move']: continue
                score, pv = analyse(eng, b, side)
                if not pv or row['uci'] == pv[0]: continue
                played = b.copy(); played.push_uci(row['uci'])
                after, refutation = analyse(eng, played, side)
                if score - after < 96: continue
                key = 'game-' + hashlib.sha256((json.dumps(moves) + str(row['ply'])).encode()).hexdigest()[:24]
                previous = moves[row['ply'] - 2] if row['ply'] > 1 else None
                context = '대국의 첫 위치입니다.'
                if previous:
                    prior_board = chess.Board()
                    for u in moves[:row['ply'] - 2]: prior_board.push_uci(u)
                    context = '상대 직전 수: ' + explain(prior_board, chess.Move.from_uci(previous))
                candidates.append({'id': key, 'title': f'내 대국 {row["ply"]}반수 재도전', 'fen': b.fen(),
                    'line': pv, 'played': row['uci'], 'refutation': refutation, 'prior': previous,
                    'context': context,
                    'category': category(b, chess.Move.from_uci(pv[0])), 'source': 'Stockfish 0.12초 재분석 (근사치)',
                    'score': score, 'loss': round(score - after), 'due': now().isoformat(), 'successes': 0})
                if len(candidates) == 3: break
        with store(code) as state:
            for c in candidates:
                c['tags'] = proven_tags(c)
                c['tag_evidence'] = 'python-chess 규칙으로 확인된 특징'
                state['cards'].setdefault(c['id'], c)
        return {'count': len(candidates), 'message': f'{len(candidates)}개 실수 위치를 오답노트에 준비했습니다.' if candidates else '분석 기준에 맞는 내 실수를 찾지 못했습니다. 임의로 만들지 않습니다.'}

    def new_puzzle(state, wanted, legacy, similar_to=None, beginner=False, rating_band=None):
        source = state['cards'].get(similar_to) if similar_to else None
        if similar_to and not source: raise HTTPException(404, '비교할 학습 항목이 없습니다.')
        tags = set(source.get('tags', [])) if source else set()
        if source and not tags: raise HTTPException(409, '원본에서 확인된 학습 태그가 없어 유사 문제를 선택할 수 없습니다.')
        seen = set(state['seen']) | set(legacy.get('_journey_seen', []))
        seen.update(str(r.get('id', r.get('puzzle_id', ''))) for r in legacy.get('puzzle_results', []))
        # Also exclude questions already served by the current legacy course/diagnostic.
        for key in ('v9_puzzle', 'v9_course'):
            seen.update(legacy.get(key, {}).get('ids', []) if legacy.get(key) else [])
        for record in legacy.get('assessment_v8_history', []):
            seen.update(r.get('puzzle_id', '') for r in record.get('item_log', []))
        current = legacy.get('assessment_v8')
        if current and 'seed' in current:
            from assessment_v8 import questions
            seen.update(q['puzzle_id'] for q in questions(current['seed'])[:current.get('index', 0) + 1])
        seen_positions = {' '.join(c['fen'].split()[:4]) for c in state['cards'].values()} | set(legacy.get('_journey_positions', []))
        for card in state['cards'].values():
            try:
                board=chess.Board(card['fen'])
                for uci in card.get('line',[]):
                    board.push_uci(uci); seen_positions.add(' '.join(board.fen().split()[:4]))
            except (ValueError,TypeError): pass
        for pid in seen:
            old = LIB.get(pid)
            if old:
                old_board = chess.Board(old['fen']); old_board.push_uci(old['moves'][0])
                seen_positions.update(line_positions(old_board.fen(),old['moves'][1:]))
        choices = []
        for p in LIB.values():
            if p['id'] in seen: continue
            if rating_band and not rating_band[0] <= p['rating'] <= rating_band[1]:continue
            if beginner and not (600 <= p['rating'] <= 1200 and 'mateIn1' in p['themes']): continue
            b = chess.Board(p['fen']); b.push_uci(p['moves'][0])
            if seen_positions.intersection(line_positions(b.fen(),p['moves'][1:])): continue
            cat = category(b, chess.Move.from_uci(p['moves'][1]), p['themes'])
            overlap = sorted(tags & set(p['themes']))
            if source and not overlap: continue
            if source and source.get('full_line'):
                if not supports(source['category'],b.fen(),p['moves'][1:],p['themes']): continue
                cat=source['category']
            if not source and wanted and cat != wanted: continue
            choices.append((p, b, cat, overlap))
            if len(choices) >= 100: break
        if not choices: raise HTTPException(409, '공통 학습 태그가 있는 미노출 문제가 없습니다.' if source else '이 영역의 미출제 문제를 찾지 못했습니다. 다른 영역을 선택하세요.')
        best_overlap = max(len(choice[3]) for choice in choices)
        p, b, cat, overlap = secrets.choice([choice for choice in choices if len(choice[3]) == best_overlap])
        key = 'puzzle-' + p['id']
        c = {'id': key, 'title': '새 실전 적용 문제', 'fen': b.fen(), 'line': p['moves'][1:],
             'context': '상대 직전 수: ' + explain(chess.Board(p['fen']), chess.Move.from_uci(p['moves'][0])),
             'tags': sorted(set(p['themes']) & set(THEMES)), 'tag_evidence': 'Lichess 원본 학습 태그',
             'selection': {'source_card': similar_to, 'overlap': overlap, 'method': 'shared_learning_tags' if source else 'independent', 'rating_band':list(rating_band) if rating_band else None,
                           'evidence': source['tag_evidence'] + ' ↔ Lichess 원본 학습 태그' if source else '독립 새 문제 · 유사 문제 집계 제외'},
             'full_line': bool(source and source.get('full_line')), 'rating':p['rating'], 'puzzle_id':p['id'], 'created_at':now().isoformat(),
             'prior': p['moves'][0], 'category': cat, 'source': 'Lichess CC0 검증 수순 · 대안은 메이트 또는 엔진 확인',
             'due': now().isoformat(), 'successes': 0}
        state['cards'][key] = c; state['seen'].append(p['id'])
        return c

    def record_exposure(card):
        exposure=card.setdefault('exposure',{}).setdefault(now().date().isoformat(),{'hints':0,'revealed':False,'wrong':0})
        exposure['last_at']=now().isoformat()
        return exposure

    @app.post('/api/learning/exposure')
    def expose(body: Resume, authorization: str | None = Header(default=None)):
        with store(auth(authorization)) as state:
            active=state.get('active')
            if not active or active['id']!=body.session_id or active['revision']!=body.active_revision:
                raise HTTPException(409,'훈련 위치가 바뀌었습니다. 저장 상태를 확인하세요.')
            record_exposure(state['cards'][active['card_id']])
            return {'recorded':True}

    @app.post('/api/learning/start')
    def start(body: Start, authorization: str | None = Header(default=None)):
        code = auth(authorization)
        with store(code) as state:
            active=state.get('active')
            if active and not active['done']:
                if body.card_id==active['card_id'] and body.mode==active['mode'] and not body.fresh and not body.similar_to:
                    record_exposure(state['cards'][active['card_id']])
                    return payload(state)
                if body.pause_session_id!=active['id'] or body.pause_revision!=active['revision']:
                    raise HTTPException(409,'진행 중인 훈련을 보존했습니다. 이어서 완료하거나 저장 후 전환을 확인하세요.')
                state.setdefault('paused',{})[active['id']]={**copy.deepcopy(active),'revision':active['revision']+1}
                state['active']=None
            legacy = context(code)
            if body.fresh or body.similar_to or not body.card_id: card = new_puzzle(state, body.category, legacy, body.similar_to)
            else:
                card = state['cards'].get(body.card_id)
                if not card: raise HTTPException(404, '학습 항목을 찾을 수 없습니다.')
            return begin(state, card, body.mode, body.fresh or not body.card_id or bool(body.similar_to))

    @app.post('/api/learning/resume')
    def resume(body: Resume, authorization: str | None = Header(default=None)):
        with store(auth(authorization)) as state:
            active=state.get('active')
            if active and active['id']==body.session_id:
                record_exposure(state['cards'][active['card_id']])
                return payload(state)
            if (active and (active['id']!=body.active_id or active['revision']!=body.active_revision)) or (not active and body.active_id):
                raise HTTPException(409,'현재 훈련이 변경되었습니다. 저장 상태를 확인하세요.')
            saved=state.get('paused',{}).get(body.session_id)
            if not saved:raise HTTPException(404,'보존된 훈련을 찾을 수 없습니다.')
            if active and not active['done']:state.setdefault('paused',{})[active['id']]={**copy.deepcopy(active),'revision':active['revision']+1}
            state['active']=state['paused'].pop(body.session_id)
            state['active']['revision']+=1
            sync_path(state)
            record_exposure(state['cards'][state['active']['card_id']])
            return payload(state)

    def begin(state, card, mode, fresh=False):
        b = chess.Board(card['fen'])
        if not b.is_valid() or b.is_game_over(): raise HTTPException(409, '이 위치에서 시작할 수 없습니다.')
        baseline = None
        if mode.startswith('situation'):
            with engine() as eng: baseline, _ = analyse(eng, b, b.turn)
        goal = ('6번의 내 착수 동안 시작 평가에서 100cp 이내를 유지하세요. 우세 유지·방어 연습이며 승리 보장이 아닙니다.'
                if baseline is not None else '저장된 상대 응수를 확인하며 내 후속 수까지 끝까지 계산하세요.' if card.get('full_line') else '상대 응수를 고려해 유효한 첫 수를 찾으세요. 첫 수 판단 훈련입니다.')
        first_exposure = not card.get('prior_exposed') and not card.get('exposure') and not any(a['card_id'] == card['id'] for a in state['attempts'])
        exposure = card.setdefault('exposure', {}).setdefault(now().date().isoformat(), {'hints': 0, 'revealed': False, 'wrong': 0})
        exposure['starts'] = exposure.get('starts', 0) + 1
        exposure['last_at'] = now().isoformat()
        state['active'] = {'first_exposure': first_exposure, 'id': secrets.token_hex(16), 'revision': 0, 'card_id': card['id'],
            'mode': mode, 'fen': b.fen(), 'side': 'white' if b.turn else 'black', 'done': False,
            'prior_help':{'hints':exposure['hints'],'revealed':exposure['revealed']},
            'turns': 0, 'hints': 0, 'revealed': False, 'wrong': 0, 'undone': False,
            'selection': card.get('selection') if fresh else None, 'fresh': fresh, 'goal': goal, 'baseline': baseline,
            'opponent_last_move': card.get('prior'), 'history': [], 'moves': [], 'line_index': 0}
        return payload(state)

    def sync_path(state):
        s = state['active']; path = state.get('path')
        if not s or not path or s.get('path_id') != path['id']: return
        step = path['steps'][s['path_step']]
        step['session'] = copy.deepcopy(s)
        if s['done']:
            step.update(status='completed', outcome=copy.deepcopy(s['outcome']),
                        reason='시도 결과 저장 완료 · 성공 여부는 별도 기록')
            path['current'] = s['path_step'] + 1
        path['revision'] += 1
        path['done'] = path['current'] >= 4

    def public_path(state):
        path = state.get('path')
        if not path: return None
        result = {k: path[k] for k in ('id', 'date', 'revision', 'current', 'done', 'source_card', 'selection_reason')}
        result['fresh'] = path.get('fresh', False)
        source = state['cards'].get(path.get('source_card'), {})
        result['diagnosis'] = source.get('diagnosis')
        if path['current'] == 1:
            result['concept_position'] = {'fen': source.get('fen'), 'side': 'white' if chess.Board(source['fen']).turn else 'black'} if source else None
        result['source_title'] = state['cards'][path['source_card']]['title'] if path['source_card'] else None
        result['steps'] = [{k: v for k, v in step.items() if k != 'session'} for step in path['steps']]
        # Keep the verification theme hidden until that step finishes.
        if result['current'] == 2 and not result['done']:
            result['steps'][2].pop('selection', None)
        if path['source_card'] and (path['current'] != 2 or path['done']):
            card = state['cards'][path['source_card']]
            result['concept'] = CONCEPTS[card['category']]
            result['tags'] = [THEMES[t] for t in card['tags'] if t in THEMES]
        return result

    def create_path(state, legacy, selected=None):
        previous = state.get('path')
        if previous: state.setdefault('path_history', []).append(previous)
        due = [c for c in state['cards'].values() if c['due'] <= now().isoformat()]
        latest_verifications = {}
        eligible_verifications=[a for a in state['attempts'] if a['mode']=='verify'
            and a.get('competency_version')==COMPETENCY_VERSION
            and a.get('assessment_scope')=='full_line' and isinstance(a['success'],bool)]
        for attempt in eligible_verifications[-30:]:
            latest_verifications[attempt['card_id']] = attempt['success']
        failed_verifications = {key for key, success in latest_verifications.items() if not success}
        due.sort(key=lambda c: (c['id'] not in failed_verifications, c['due'], c['id']))
        card = selected
        report = legacy.get('_journey_report')
        if card is None and report:
            for item in report.get('items', []):
                if not item.get('complete'):
                    try: card = diagnosis_card(state, report, item)
                    except HTTPException: continue
                    if card['due'] <= now().isoformat(): break
                    card = None
        if card is None: card = due[0] if due else None
        fresh = False
        if card is None:
            try:
                card = new_puzzle(state, None, legacy, beginner=True); fresh = True
                card['title'] = '입문 · 한 수 메이트'
            except HTTPException as exc:
                if exc.status_code != 409: raise
        state['path'] = {'id': secrets.token_hex(16), 'date': now().date().isoformat(), 'revision': 0,
                         'current': 0, 'done': False, 'fresh': fresh, 'source_card': card['id'] if card else None,
                         'selection_reason': (('진단에서 완주한 수순을 복습합니다. ' if card['diagnosis'].get('complete') else '완료 진단의 미완성 수순을 연습합니다. ') + str(card['diagnosis'].get('reason', ''))) if card and card.get('diagnosis') else '복습 예정 카드가 없어 입문 새 문제로 시작합니다.' if fresh else ('복습 예정 카드 중 최근 검증 미달성을 우선 선택' if card else '준비된 입문 문제가 없습니다. 자료 확인 후 다시 시도하세요. 학습을 완료한 상태가 아닙니다.'),
                         'steps': [{'id': key, 'status': 'pending', 'card_id': card['id'] if card else None,
                                    'reason': '', 'mode': mode} for key, mode in
                                   [('review', 'practice'), ('concept', None), ('transfer', 'verify'), ('situation', 'situation_practice')]]}

    @app.post('/api/learning/path')
    def path_action(body: PathAction, authorization: str | None = Header(default=None)):
        code = auth(authorization)
        with store(code) as state:
            legacy = context(code)
            path = state.get('path')
            active=state.get('active')
            if active and not active['done'] and (not path or active.get('path_id')!=path['id']):
                if body.pause_session_id!=active['id'] or body.pause_revision!=active['revision']:
                    raise HTTPException(409,'진행 중인 훈련을 보존했습니다. 저장 후 전환을 확인하세요.')
                state.setdefault('paused',{})[active['id']]={**copy.deepcopy(active),'revision':active['revision']+1}
                state['active']=None
            if body.path_id is not None and (not path or body.path_id != path['id'] or body.revision != path['revision']):
                raise HTTPException(409, '학습 경로가 변경되었습니다. 새로고침 후 이어가세요.')
            if body.action == 'new':
                if path and not path['done']: raise HTTPException(409, '진행 중인 경로를 먼저 완료하세요.')
                create_path(state, legacy)
            elif not path: create_path(state, legacy)
            elif path['done'] and path['date'] < now().date().isoformat(): create_path(state, legacy)
            path = state['path']
            if not path['source_card']:
                create_path(state, legacy); path = state['path']
                if not path['source_card']: return {'path': public_path(state), 'active': None}
            if body.action == 'acknowledge':
                if path['current'] != 1 or path['steps'][1]['status'] != 'active':
                    raise HTTPException(409, '개념 단계를 먼저 열어 주세요.')
                path['steps'][1].update(status='completed', reason='개념 읽기 확인 완료')
                path['current'] = 2; path['revision'] += 1
                return {'path': public_path(state), 'active': None}
            while path['current'] < 4:
                index = path['current']; step = path['steps'][index]
                card = state['cards'].get(path['source_card'])
                reason = None
                if not card: reason = '선택할 복습 카드가 없습니다.'
                elif index == 3 and not (ns['STOCKFISH_PATH'] and Path(ns['STOCKFISH_PATH']).is_file()):
                    reason = 'Stockfish 미연결로 상황 대국을 시작할 수 없습니다.'
                if reason:
                    step.update(status='skipped', reason=reason); path['current'] += 1; path['revision'] += 1
                    continue
                if index == 1:
                    state['active'] = None
                    step.update(status='active', reason='개념을 읽고 확인 버튼을 눌러 완료하세요.')
                    path['revision'] += 1
                    return {'path': public_path(state), 'active': None}
                if step.get('session'):
                    stored=state.get('paused',{}).pop(step['session']['id'],None)
                    state['active'] = copy.deepcopy(stored or step['session'])
                    state['active']['revision']+=1
                    sync_path(state)
                    record_exposure(state['cards'][state['active']['card_id']])
                    return {'path': public_path(state), 'active': payload(state)}
                if index == 2:
                    try: card = new_puzzle(state, None, legacy, path['source_card'])
                    except HTTPException as exc:
                        if exc.status_code != 409: raise
                        step.update(status='skipped', reason=exc.detail); path['current'] += 1; path['revision'] += 1
                        continue
                    step['selection'] = card['selection']
                begin(state, card, step['mode'], fresh=index == 2 or (index == 0 and path.get('fresh', False)))
                state['active'].update(path_id=path['id'], path_step=index)
                step.update(status='active', card_id=card['id'], reason='착수 시도 결과를 저장하면 완료됩니다. 성공률과는 별도입니다.')
                sync_path(state)
                return {'path': public_path(state), 'active': payload(state)}
            path['done'] = True
            return {'path': public_path(state), 'active': None}

    @app.post('/api/learning/action')
    def action(body: Action, authorization: str | None = Header(default=None)):
        with store(auth(authorization)) as state:
            s = state['active']
            if not s or s['id'] != body.session_id or s['revision'] != body.revision:
                raise HTTPException(409, '다른 요청에서 학습 상태가 변경되었습니다. 학습 화면을 다시 열어 주세요.')
            card = state['cards'][s['card_id']]
            b = chess.Board(card['fen'])
            for u in s.get('moves', []): b.push_uci(u)
            side = s['side'] == 'white'
            verify = 'verify' in s['mode']; situation = s['mode'].startswith('situation')
            if s['done']: raise HTTPException(409, '완료된 학습입니다. 새 시도를 시작하세요.')
            if verify and body.action != 'move': raise HTTPException(403, '검증 모드에서는 도움을 사용할 수 없습니다.')
            exposure = card.setdefault('exposure', {}).setdefault(now().date().isoformat(), {'hints': 0, 'revealed': False, 'wrong': 0})
            exposure['last_at'] = now().isoformat()
            s['revision'] += 1
            s.pop('playback', None)
            if body.action == 'undo':
                if not situation or not s['history']: raise HTTPException(409, '무를 수 있는 상황 대국 착수가 없습니다.')
                previous = s['history'].pop(); s.update(previous); s['undone'] = True
                exposure['hints'] = max(1, exposure['hints'])
                s['message'] = '연습 착수를 무릅니다. 도움을 사용한 기록으로 남습니다.'
            elif body.action in ('hint', 'reveal', 'refutation'):
                line = card['line'][s.get('line_index', 0):] if card.get('full_line') else card['line']
                if situation:
                    with engine() as eng: _, line = analyse(eng, b, side)
                if not line: raise HTTPException(409, '제공할 수순이 없습니다.')
                best = chess.Move.from_uci(line[0])
                if body.action == 'hint':
                    s['hints'] = min(3, s['hints'] + 1)
                    exposure['hints'] = max(exposure['hints'], s['hints'])
                    s['message'] = [CONCEPTS[card['category']], f'{chess.square_name(best.from_square)}의 기물을 살펴보세요.', f'후보 수: {b.san(best)} · {explain(b, best)}'][s['hints'] - 1]
                else:
                    s['revealed'] = True
                    exposure['revealed'] = True
                    if body.action == 'refutation' and card.get('played') and not situation:
                        s['playback'] = frames(b, [card['played']] + card['refutation'])
                        s['message'] = '실제 실수 뒤 엔진의 응수입니다. 짧은 탐색의 후보 수순이며 강제 수순 보장은 아닙니다.'
                    else:
                        s['playback'] = frames(b, line)
                        s['message'] = '답안 수순을 공개했습니다. 이후 성공은 정답 공개 후 성공으로 구분합니다.'
            else:
                try: m = chess.Move.from_uci(body.move or '')
                except ValueError: raise HTTPException(400, '착수 형식이 올바르지 않습니다.')
                if m not in b.legal_moves: raise HTTPException(400, '현재 위치에서 합법적인 수가 아닙니다.')
                before = b.copy(); b.push(m)
                accepted = m.uci() == card['line'][s.get('line_index', 0)] or b.is_checkmate()
                loss = None; reply = []
                if situation or (not card.get('full_line') and not accepted and ns['STOCKFISH_PATH'] and Path(ns['STOCKFISH_PATH']).is_file()):
                    with engine() as eng:
                        best_score, _ = analyse(eng, before, side)
                        score, reply = analyse(eng, b, side)
                        loss = max(0, round(best_score - score))
                        # Preserve proven mating objectives: non-mating alternative needs full proof, not a cp guess.
                        accepted = b.is_checkmate() or (loss <= 45 and best_score < 9000)
                        if situation:
                            accepted = score >= s['baseline'] - 100
                            if not b.is_game_over() and reply: b.push_uci(reply[0])
                s['explanation'] = explain(before, m) + (f' · 엔진 최선 대비 약 {loss}cp 손실 (짧은 탐색)' if loss is not None else ' · 실제 메이트 판정' if b.is_checkmate() else ' · 원본 수순과 일치' if accepted else ' · 대안 수의 품질은 미검증')
                if situation:
                    s['history'].append({'fen': s['fen'], 'turns': s['turns'], 'moves': list(s['moves']), 'opponent_last_move': s.get('opponent_last_move')})
                    s['fen'] = b.fen(); s['moves'] = [m.uci() for m in b.move_stack]; s['turns'] += 1
                    s['opponent_last_move'] = reply[0] if reply and not before.is_game_over() and len(b.move_stack) > 1 else None
                    if not accepted or b.is_game_over() or s['turns'] >= 6:
                        terminal = b.outcome()
                        success = accepted and (terminal is None or terminal.winner == side or (terminal.winner is None and s['baseline'] <= 100))
                        finish(state, s, success)
                    else: s['message'] = f'{s["turns"]}/6수 · 목표 평가 범위를 유지하고 있습니다.'
                elif accepted and card.get('full_line'):
                    s['moves'].append(m.uci()); s['line_index'] += 1; s['turns'] += 1
                    if not b.is_game_over() and s['line_index'] < len(card['line']):
                        reply_move = card['line'][s['line_index']]
                        response=chess.Move.from_uci(reply_move)
                        s['explanation']+=' · 원본 상대 응수 '+b.san(response)+': '+explain(b,response)
                        b.push_uci(reply_move); s['moves'].append(reply_move); s['line_index'] += 1
                        s['opponent_last_move'] = reply_move
                    s['fen'] = b.fen()
                    if b.is_game_over() or s['line_index'] >= len(card['line']):
                        finish(state, s, True)
                        s['playback'] = frames(chess.Board(card['fen']), s['moves'])
                    else: s['message'] = '첫 수만으로 완료하지 않습니다. 상대 응수 뒤 내 후속 수를 계산하세요.'
                elif accepted:
                    s['fen'] = b.fen(); s['turns'] = 1; finish(state, s, True)
                    s['playback'] = frames(chess.Board(card['fen']), card['line'])
                else:
                    s['wrong'] += 1
                    exposure['wrong'] += 1
                    s['message'] = '이 수는 검증된 답안에 포함되지 않습니다.' + (' 엔진 미연결로 동등한 대안 여부는 확인하지 못했습니다.' if loss is None else ' 상대의 강한 응수를 다시 고려하세요.')
                    if verify:
                        message = s['message']
                        finish(state, s, False if loss is not None else None)
                        if loss is None: s['message'] = message + ' 미검증 대안으로 기록하며 능력 성공률 계산에서 제외합니다.'
            sync_path(state)
            return payload(state)
