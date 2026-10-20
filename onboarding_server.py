"""Versioned account onboarding; additive to progress, never resets learning state."""
from datetime import datetime, timezone
from typing import Literal
from fastapi import Header, HTTPException
import chess
from pydantic import BaseModel, Field

VERSION = 1


class OnboardingUpdate(BaseModel):
    status: Literal['in_progress', 'completed', 'skipped']
    step: int = Field(default=0, ge=0, le=3)


class StartingLevel(BaseModel):
    choice: Literal['rules', 'beginner', 'experienced', 'unsure', 'later']
    revision: int = Field(ge=0)


class RuleMove(BaseModel):
    revision: int = Field(ge=0)
    step: int = Field(ge=0, le=3)
    move: str


# Deliberately small, rule-only exercises. No rating, diagnosis, or completion credit.
RULES = [
    ('말 이동', '룩은 가로와 세로로 움직여요. a1의 룩을 a4로 옮겨 보세요.',
     '7k/8/8/8/8/8/8/R5K1 w - - 0 1', 'a1a4'),
    ('말 잡기', '룩으로 같은 줄의 상대 말을 잡을 수 있어요. a1의 룩으로 a4의 나이트를 잡아 보세요.',
     '7k/8/8/8/n7/8/8/R5K1 w - - 0 1', 'a1a4'),
    ('체크', '상대 왕을 공격하면 체크예요. a1의 룩을 a8로 옮겨 체크해 보세요.',
     '7k/8/8/8/8/8/8/R5K1 w - - 0 1', 'a1a8'),
    ('왕 안전', '왕이 공격받고 있어요. 공격받는 칸으로는 갈 수 없어요. g1의 왕을 f2로 피하세요.',
     'k5r1/8/8/8/8/8/8/6K1 w - - 0 1', 'g1f2'),
]


def attach_onboarding(app, ns):
    def level_payload(state, code):
        saved = state.get('learner_start', {})
        step = saved.get('rules_step', 0)
        exercise = None
        if step < len(RULES):
            title, hint, fen, _ = RULES[step]
            exercise = {'title': title, 'hint': hint, 'fen': fen,
                        'legal': [m.uci() for m in chess.Board(fen).legal_moves]}
        return {**saved, 'choice': saved.get('choice'), 'revision': saved.get('revision', 0),
                'rules_step': step, 'exercise': exercise,
                'defer_auto': payload(state, code)['defer_auto'],
                'notice': '자기 선택은 시작 난도와 안내에만 사용합니다. 실제 실력이나 Elo가 아닙니다.'}

    @app.get('/api/starting-level')
    def read_level(authorization: str | None = Header(default=None)):
        code = ns['auth'](authorization)
        return level_payload(ns['get_state'](code), code)

    @app.post('/api/starting-level')
    def write_level(body: StartingLevel, authorization: str | None = Header(default=None)):
        code = ns['auth'](authorization); state = ns['get_state'](code)
        previous = state.get('learner_start', {})
        if previous.get('revision', 0) != body.revision:
            raise HTTPException(409, '선택이 다른 화면에서 바뀌었습니다. 다시 열어 확인하세요.')
        state['learner_start'] = {**previous, 'choice': body.choice, 'revision': body.revision + 1,
                                 'updated_at': datetime.now(timezone.utc).isoformat()}
        ns['save_state'](code, state)
        return level_payload(state, code)

    @app.post('/api/starting-level/move')
    def rule_move(body: RuleMove, authorization: str | None = Header(default=None)):
        code = ns['auth'](authorization); state = ns['get_state'](code)
        previous = state.get('learner_start', {})
        if (previous.get('revision', 0) != body.revision or previous.get('rules_step', 0) != body.step
                or previous.get('choice') != 'rules'):
            raise HTTPException(409, '입문 안내 상태가 바뀌었습니다. 다시 열어 확인하세요.')
        correct = body.move == RULES[body.step][3]
        state['learner_start'] = {**previous, 'revision': body.revision + 1,
                                 'rules_step': body.step + int(correct)}
        ns['save_state'](code, state)
        return {**level_payload(state, code), 'correct': correct,
                'feedback': '잘했어요. 다음 단계로 가요.' if correct else '괜찮아요. 설명을 보고 다시 해 보세요. 감점은 없어요.'}

    def payload(state, code):
        saved = state.get('onboarding_v1', {})
        current = saved if saved.get('version') == VERSION else {}
        game = state.get('active_game')
        old = state.get('assessment_v8')
        journey_active = ns.get('journey_active')
        course = state.get('v9_course')
        # Learning lives in its own table; this guard is supplied by the learning module.
        learning_active = ns.get('learning_active')
        defer = bool(game or old or (course and not course.get('done')) or (journey_active and journey_active(code))
                     or (learning_active and learning_active(code)))
        return {'version': VERSION, 'status': current.get('status', 'not_started'),
                'step': current.get('step', 0), 'updated_at': current.get('updated_at'),
                'defer_auto': defer,
                'clock_notice': '안내를 열어도 진행 중인 대국 시계는 멈추지 않습니다.'}

    @app.get('/api/onboarding')
    def read(authorization: str | None = Header(default=None)):
        code = ns['auth'](authorization)
        return payload(ns['get_state'](code), code)

    @app.post('/api/onboarding')
    def write(body: OnboardingUpdate, authorization: str | None = Header(default=None)):
        code = ns['auth'](authorization)
        state = ns['get_state'](code)
        previous = state.get('onboarding_v1', {})
        # Replay does not turn a completed/skipped introduction back into an unfinished one.
        if not (previous.get('version') == VERSION and previous.get('status') in ('completed', 'skipped')):
            state['onboarding_v1'] = {'version': VERSION, 'status': body.status, 'step': body.step,
                                      'updated_at': datetime.now(timezone.utc).isoformat()}
            ns['save_state'](code, state)
        return payload(state, code)
