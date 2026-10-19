"""Evidence-based learning, isolated from legacy progress JSON writes.
New records use one locked row per account (SQLite BEGIN IMMEDIATE / PostgreSQL
FOR UPDATE). No accounts, old records, or corpus entries are rewritten.
"""
import copy
import hashlib
import json
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import chess
import chess.engine
from fastapi import Header, HTTPException
from pydantic import BaseModel, Field
from v9_server import LIB, THEMES

CATEGORIES = {'calculation': '수읽기', 'endgame': '엔드게임', 'promotion': '승격',
              'mate': '메이트', 'capture': '포획·교환', 'defense': '위협 방어'}
CONCEPTS = {
 'calculation': '후보수마다 상대의 체크·포획을 먼저 확인하고 응수를 한 수 더 읽으세요.',
 'endgame': '킹의 활동과 폰의 승격 경로를 함께 확인하세요. 이 훈련은 테이블베이스 판정이 아닙니다.',
 'promotion': '승격 기물을 고르기 전에 체크메이트와 스테일메이트 여부를 확인하세요.',
 'mate': '체크 이후 상대 킹의 도망갈 칸, 잡기, 막기를 모두 확인하세요.',
 'capture': '잡은 뒤 상대의 되잡기와 체크를 계산하세요. 기물 가치만으로 결론 내리지 마세요.',
 'defense': '체크 중이면 킹 이동·공격 기물 포획·가로막기 중 합법적인 대응을 확인하세요.'}


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


class Action(BaseModel):
    session_id: str
    revision: int
    action: Literal['move', 'hint', 'reveal', 'refutation', 'undo']
    move: str | None = None


class PathAction(BaseModel):
    action: Literal['continue', 'acknowledge', 'new'] = 'continue'
    path_id: str | None = None
    revision: int | None = None


class Settings(BaseModel):
    intervals: list[int] = Field(min_length=1, max_length=5)


def attach_learning(app, ns):
    execute, db, auth = ns['execute'], ns['db'], ns['auth']
    with db() as conn:
        execute(conn, 'CREATE TABLE IF NOT EXISTS learning_progress (code TEXT PRIMARY KEY, state TEXT NOT NULL)')

    @contextmanager
    def store(code):
        with db() as conn:
            if not ns['DATABASE_URL']: conn.execute('BEGIN IMMEDIATE')
            default = {'schema': 1, 'cards': {}, 'attempts': [], 'seen': [], 'intervals': [1, 3, 7], 'active': None}
            execute(conn, 'INSERT INTO learning_progress(code,state) VALUES(?,?) ON CONFLICT(code) DO NOTHING', (code, json.dumps(default)))
            suffix = ' FOR UPDATE' if ns['DATABASE_URL'] else ''
            row = execute(conn, 'SELECT state FROM learning_progress WHERE code=?' + suffix, (code,)).fetchone()
            state = json.loads(row['state'])
            for card in state['cards'].values():
                if 'tags' not in card:
                    puzzle = LIB.get(card['id'].removeprefix('puzzle-')) if card['id'].startswith('puzzle-') else None
                    card['tags'] = sorted(set(puzzle['themes']) & set(THEMES)) if puzzle else proven_tags(card)
                    card['tag_evidence'] = 'Lichess 원본 학습 태그' if puzzle else 'python-chess 규칙으로 확인된 특징'
            yield state
            execute(conn, 'UPDATE learning_progress SET state=? WHERE code=?', (json.dumps(state, ensure_ascii=False), code))

    @contextmanager
    def engine():
        path = ns['STOCKFISH_PATH']
        if not path or not Path(path).is_file():
            raise HTTPException(503, 'Stockfish가 연결되지 않았습니다. 실전 실수 분석·대안 수 평가·상황 대국은 사용할 수 없습니다. 원본 수순 퍼즐은 이용할 수 있습니다.')
        eng = None
        try:
            eng = chess.engine.SimpleEngine.popen_uci(path, timeout=5)
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
        return {k: card[k] for k in ('id', 'title', 'category', 'source', 'due', 'successes', 'tags', 'tag_evidence')}

    def payload(state):
        s = state['active']
        if not s: return None
        card = state['cards'][s['card_id']]
        b = chess.Board(s['fen'])
        verify = 'verify' in s['mode']
        return {'session_id': s['id'], 'revision': s['revision'], 'card_id': card['id'],
                'fen': s['fen'], 'legal': [] if s['done'] else [m.uci() for m in b.legal_moves],
                'side': s['side'], 'mode': s['mode'], 'done': s['done'], 'turns': s['turns'],
                'category': None if verify and not s['done'] else CATEGORIES[card['category']],
                'concept': None if verify and not s['done'] else CONCEPTS[card['category']],
                'source': card['source'], 'goal': s['goal'], 'message': s.get('message', ''),
                'opponent_last_move': s.get('opponent_last_move'), 'hint_level': s['hints'],
                'context': card.get('context', '직전 위치 기록이 없어 변화의 의미를 추측하지 않습니다.'),
                'explanation': s.get('explanation'), 'playback': s.get('playback', []),
                'outcome': s.get('outcome'), 'selection': None if verify and not s['done'] else s.get('selection'), 'path_id': s.get('path_id'), 'premove': False}

    def finish(state, s, success):
        if s['done']: return
        card = state['cards'][s['card_id']]
        stamp = now()
        day = stamp.date().isoformat()
        exposure = card.setdefault('exposure', {}).setdefault(day, {'hints': 0, 'revealed': False, 'wrong': 0})
        delayed = any(date < day for date in card.get('exposure', {})) or any(a['card_id'] == card['id'] and a['at'][:10] < day for a in state['attempts'])
        completed_today = any(a['card_id'] == card['id'] and a['at'][:10] == day and a['success'] for a in state['attempts'])
        revealed = s['revealed'] or exposure['revealed']
        helped = bool(s['hints'] or s['undone'] or exposure['hints'])
        wrong = max(s['wrong'], exposure['wrong'])
        status = ('revealed_success' if revealed else 'hinted_success' if helped
                  else 'unaided_repeat_success' if completed_today else 'retry_success' if wrong
                  else 'later_unaided_success' if delayed else 'unaided_first_success' if s.get('first_exposure', s['fresh']) else 'unaided_repeat_success') if success else 'unverified_alternative' if success is None else 'not_yet'
        attempt = {'card_id': card['id'], 'at': stamp.isoformat(), 'category': card['category'],
                   'mode': s['mode'], 'success': success, 'status': status,
                   'position': ' '.join(card['fen'].split()[:4]),
                   'selection': s.get('selection'), 'path_id': s.get('path_id'),
                   'hint_level': max(s['hints'], exposure['hints']), 'helped': bool(helped or revealed), 'wrong': wrong, 'fresh': s['fresh']}
        eligible_result = status in ('unaided_first_success', 'later_unaided_success') or success is False
        prior = [a for a in state['attempts'] if a['card_id'] == card['id']]
        independent_kind = None
        if eligible_result and not helped and not revealed and wrong <= (0 if success else 1):
            if s['fresh'] and not prior: independent_kind = 'novel'
            elif delayed and not any(a['at'][:10] == day for a in prior): independent_kind = 'delayed'
        attempt['independent_kind'] = independent_kind
        state['attempts'].append(attempt)
        credited_today = card.get('credited_date') == day
        eligible = bool(success) and status in ('unaided_first_success', 'later_unaided_success') and not credited_today
        if eligible:
            card['successes'] += 1
            card['credited_date'] = day
        days = state['intervals'][min(max(card['successes'] - 1, 0), len(state['intervals']) - 1)] if success else 1
        if not credited_today:
            card['due'] = (stamp + timedelta(days=days)).isoformat()
        s.update(done=True, outcome=attempt, message='학습 기록을 저장했습니다.' if success else '아직 목표에 도달하지 못했습니다. 기록을 저장했습니다.')

    @app.get('/api/learning/dashboard')
    def dashboard(authorization: str | None = Header(default=None)):
        code = auth(authorization)
        with store(code) as state:
            due = [public_card(c) for c in state['cards'].values() if c['due'] <= now().isoformat()]
            skills = []
            for key, label in CATEGORIES.items():
                rows = [a for a in state['attempts'] if a['category'] == key]
                independent = [a for a in rows if a.get('independent_kind') in ('novel', 'delayed')]
                distinct = len({a.get('position', a['card_id']) for a in independent})
                rates = lambda r: round(100 * sum(a['success'] for a in r) / len(r)) if r else None
                skills.append({'id': key, 'name': label, 'count': len(rows), 'independent': len(independent),
                               'recent': rates(independent[-5:]), 'previous': rates(independent[-10:-5]),
                               'insufficient': distinct < 5, 'distinct': distinct,
                               'novel': sum(a['independent_kind'] == 'novel' for a in independent),
                               'delayed': sum(a['independent_kind'] == 'delayed' for a in independent),
                               'practice_count': sum(a['mode'] in ('practice', 'situation_practice') for a in rows),
                               'verification_count': sum(a['mode'] in ('verify', 'situation_verify') for a in rows),
                               'transfer': sum(bool((a.get('selection') or {}).get('overlap')) and a['fresh'] and a['mode'] == 'verify' and a['status'] == 'unaided_first_success' for a in rows)})
            weakest = min(skills, key=lambda x: (x['recent'] if x['recent'] is not None else 101, x['count']))
            return {'due': due, 'cards': [public_card(c) for c in state['cards'].values()],
                    'attempts': state['attempts'][-50:][::-1], 'skills': skills, 'intervals': state['intervals'],
                    'active': payload(state), 'path': public_path(state), 'recommended': weakest['id'],
                    'reason': '최근 무도움 시도에서 성공 비율이 낮은 영역' if weakest['recent'] is not None else '아직 학습 근거가 없어 기초부터 시작',
                    'engine': bool(ns['STOCKFISH_PATH'] and Path(ns['STOCKFISH_PATH']).is_file()),
                    'notice': '새 학습 경로의 기록만 집계합니다. 미출제는 저장된 문제 ID 기준이며 ID 없는 과거 진단까지 보장하지 않습니다. 기존 진단·대국 통계는 기록 메뉴에 보존됩니다. 실제 레이팅이 아닙니다.'}

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

    def new_puzzle(state, wanted, legacy, similar_to=None):
        source = state['cards'].get(similar_to) if similar_to else None
        if similar_to and not source: raise HTTPException(404, '비교할 학습 항목이 없습니다.')
        tags = set(source.get('tags', [])) if source else set()
        if source and not tags: raise HTTPException(409, '원본에서 확인된 학습 태그가 없어 유사 문제를 선택할 수 없습니다.')
        seen = set(state['seen'])
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
        seen_positions = {' '.join(c['fen'].split()[:4]) for c in state['cards'].values()}
        for pid in seen:
            old = LIB.get(pid)
            if old:
                old_board = chess.Board(old['fen']); old_board.push_uci(old['moves'][0])
                seen_positions.add(' '.join(old_board.fen().split()[:4]))
        choices = []
        for p in LIB.values():
            if p['id'] in seen: continue
            b = chess.Board(p['fen']); b.push_uci(p['moves'][0])
            if ' '.join(b.fen().split()[:4]) in seen_positions: continue
            cat = category(b, chess.Move.from_uci(p['moves'][1]), p['themes'])
            overlap = sorted(tags & set(p['themes']))
            if source and not overlap: continue
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
             'selection': {'source_card': similar_to, 'overlap': overlap, 'method': 'shared_learning_tags' if source else 'independent',
                           'evidence': source['tag_evidence'] + ' ↔ Lichess 원본 학습 태그' if source else '독립 새 문제 · 유사 문제 집계 제외'},
             'prior': p['moves'][0], 'category': cat, 'source': 'Lichess CC0 검증 수순 · 대안은 메이트 또는 엔진 확인',
             'due': now().isoformat(), 'successes': 0}
        state['cards'][key] = c; state['seen'].append(p['id'])
        return c

    @app.post('/api/learning/start')
    def start(body: Start, authorization: str | None = Header(default=None)):
        code = auth(authorization)
        legacy = ns['get_state'](code)
        with store(code) as state:
            if body.fresh or body.similar_to or not body.card_id: card = new_puzzle(state, body.category, legacy, body.similar_to)
            else:
                card = state['cards'].get(body.card_id)
                if not card: raise HTTPException(404, '학습 항목을 찾을 수 없습니다.')
            return begin(state, card, body.mode, body.fresh or not body.card_id or bool(body.similar_to))

    def begin(state, card, mode, fresh=False):
        b = chess.Board(card['fen'])
        if not b.is_valid() or b.is_game_over(): raise HTTPException(409, '이 위치에서 시작할 수 없습니다.')
        baseline = None
        if mode.startswith('situation'):
            with engine() as eng: baseline, _ = analyse(eng, b, b.turn)
        goal = ('6번의 내 착수 동안 시작 평가에서 100cp 이내를 유지하세요. 우세 유지·방어 연습이며 승리 보장이 아닙니다.'
                if baseline is not None else '상대 응수를 고려해 유효한 첫 수를 찾으세요. 첫 수 판단 훈련입니다.')
        first_exposure = not card.get('exposure') and not any(a['card_id'] == card['id'] for a in state['attempts'])
        exposure = card.setdefault('exposure', {}).setdefault(now().date().isoformat(), {'hints': 0, 'revealed': False, 'wrong': 0})
        exposure['starts'] = exposure.get('starts', 0) + 1
        state['active'] = {'first_exposure': first_exposure, 'id': secrets.token_hex(16), 'revision': 0, 'card_id': card['id'],
            'mode': mode, 'fen': b.fen(), 'side': 'white' if b.turn else 'black', 'done': False,
            'turns': 0, 'hints': 0, 'revealed': False, 'wrong': 0, 'undone': False,
            'selection': card.get('selection') if fresh else None, 'fresh': fresh, 'goal': goal, 'baseline': baseline,
            'opponent_last_move': card.get('prior'), 'history': [], 'moves': []}
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

    def create_path(state):
        previous = state.get('path')
        if previous: state.setdefault('path_history', []).append(previous)
        due = [c for c in state['cards'].values() if c['due'] <= now().isoformat()]
        latest_verifications = {}
        for attempt in state['attempts'][-30:]:
            if attempt['mode'] in ('verify', 'situation_verify') and attempt['success'] is not None:
                latest_verifications[attempt['card_id']] = attempt['success']
        failed_verifications = {key for key, success in latest_verifications.items() if not success}
        due.sort(key=lambda c: (c['id'] not in failed_verifications, c['due'], c['id']))
        card = due[0] if due else None
        state['path'] = {'id': secrets.token_hex(16), 'date': now().date().isoformat(), 'revision': 0,
                         'current': 0, 'done': False, 'source_card': card['id'] if card else None,
                         'selection_reason': '복습 예정 카드 중 최근 검증 미달성을 우선 선택' if card else '복습 예정 카드 없음 · 자유 훈련이나 복기에서 기록을 먼저 만드세요.',
                         'steps': [{'id': key, 'status': 'pending', 'card_id': card['id'] if card else None,
                                    'reason': '', 'mode': mode} for key, mode in
                                   [('review', 'practice'), ('concept', None), ('transfer', 'verify'), ('situation', 'situation_practice')]]}

    @app.post('/api/learning/path')
    def path_action(body: PathAction, authorization: str | None = Header(default=None)):
        code = auth(authorization); legacy = ns['get_state'](code)
        with store(code) as state:
            path = state.get('path')
            if body.path_id is not None and (not path or body.path_id != path['id'] or body.revision != path['revision']):
                raise HTTPException(409, '학습 경로가 변경되었습니다. 새로고침 후 이어가세요.')
            if body.action == 'new':
                if path and not path['done']: raise HTTPException(409, '진행 중인 경로를 먼저 완료하세요.')
                create_path(state)
            elif not path: create_path(state)
            elif path['done'] and path['date'] < now().date().isoformat(): create_path(state)
            path = state['path']
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
                    step.update(status='active', reason='개념을 읽고 확인 버튼을 눌러 완료하세요.')
                    path['revision'] += 1
                    return {'path': public_path(state), 'active': None}
                if step.get('session'):
                    state['active'] = copy.deepcopy(step['session'])
                    return {'path': public_path(state), 'active': payload(state)}
                if index == 2:
                    try: card = new_puzzle(state, None, legacy, path['source_card'])
                    except HTTPException as exc:
                        if exc.status_code != 409: raise
                        step.update(status='skipped', reason=exc.detail); path['current'] += 1; path['revision'] += 1
                        continue
                    step['selection'] = card['selection']
                begin(state, card, step['mode'], fresh=index == 2)
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
            s['revision'] += 1
            s.pop('playback', None)
            if body.action == 'undo':
                if not situation or not s['history']: raise HTTPException(409, '무를 수 있는 상황 대국 착수가 없습니다.')
                previous = s['history'].pop(); s.update(previous); s['undone'] = True
                exposure['hints'] = max(1, exposure['hints'])
                s['message'] = '연습 착수를 무릅니다. 도움을 사용한 기록으로 남습니다.'
            elif body.action in ('hint', 'reveal', 'refutation'):
                line = card['line']
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
                accepted = m.uci() == card['line'][0] or b.is_checkmate()
                loss = None; reply = []
                if situation or (not accepted and ns['STOCKFISH_PATH'] and Path(ns['STOCKFISH_PATH']).is_file()):
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
