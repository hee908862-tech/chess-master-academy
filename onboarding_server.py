"""Versioned account onboarding; additive to progress, never resets learning state."""
from datetime import datetime, timezone
from typing import Literal
from fastapi import Header
from pydantic import BaseModel, Field

VERSION = 1


class OnboardingUpdate(BaseModel):
    status: Literal['in_progress', 'completed', 'skipped']
    step: int = Field(default=0, ge=0, le=3)


def attach_onboarding(app, ns):
    def payload(state, code):
        saved = state.get('onboarding_v1', {})
        current = saved if saved.get('version') == VERSION else {}
        game = state.get('active_game')
        old = state.get('assessment_v8')
        journey_active = ns.get('journey_active')
        defer = bool(game or old or (journey_active and journey_active(code)))
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
