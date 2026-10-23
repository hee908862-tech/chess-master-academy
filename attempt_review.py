"""Explicit, owned, bounded review of an immutable saved response.

No answer, original grade, frozen baseline or learning session is rewritten.
"""
import copy
import threading
import uuid
from datetime import datetime, timezone
from fastapi import Header, HTTPException
from pydantic import BaseModel, Field
from attempt_evidence import summarize_attempts, resolve_attempt, item_fingerprint

MAX_ATTEMPTS = 3
MAX_RECORDS = 512
COOLDOWN_SECONDS = 10
_slot = threading.BoundedSemaphore(1)


class Revalidate(BaseModel):
    report_id: str = Field(min_length=1, max_length=128)
    item_id: str = Field(min_length=1, max_length=128)
    request_id: str = Field(min_length=16, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')


def find_item(state, report_id, item_id):
    report = next((r for r in state.get('results', []) if r.get('id') == report_id), None)
    item = next((i for i in (report or {}).get('items', []) if i.get('id') == item_id), None)
    if not item:
        raise HTTPException(404, '이 계정에 저장된 완료 회차의 문항이 없습니다.')
    return report, item


def view(reports, records):
    result = summarize_attempts(reports, corrections=records)
    result['revalidation_records'] = copy.deepcopy(records)
    result['revalidation_limit'] = MAX_ATTEMPTS
    return result


def initial_view(state, corpus=None):
    import initial_profile
    result = initial_profile.status(state, corpus)
    cutoff = result.get('frozen_at')
    reports = [r for r in state.get('results', [])
               if initial_profile.compatible(r, result.get('corpus'))
               and (not cutoff or not r.get('at') or r['at'] <= cutoff)]
    active = state.get('active')
    if active and not cutoff and initial_profile.compatible(active, result.get('corpus')):
        reports.append({**active, 'id': active['session_id']})
    ids = {r['id'] for r in reports}
    evidence = view(reports, [r for r in state.get('attempt_revalidations', []) if r['report_id'] in ids])
    evidence['original'] = {'score': (result.get('internal_skill') or {}).get('score'),
                            'max': 3000, 'version': result.get('score_version'),
                            'label': '기존 선택 관찰 수행점수 · 전체 시도 성적과 별도'}
    evidence['baseline_reviewed'] = bool(result.get('reviewed'))
    result['attempt_evidence'] = evidence
    return result


def attach_attempt_review(app, auth, read, store, now):
    @app.get('/api/journey/attempt-evidence/{report_id}')
    def evidence(report_id: str, authorization: str | None = Header(default=None)):
        state = read(auth(authorization))
        report = next((r for r in state['results'] if r.get('id') == report_id), None)
        if not report:
            raise HTTPException(404, '이 계정의 진단 회차가 없습니다.')
        return view([report], [r for r in state.get('attempt_revalidations', []) if r['report_id'] == report_id])

    @app.post('/api/journey/revalidate')
    def revalidate(body: Revalidate, authorization: str | None = Header(default=None)):
        code = auth(authorization)
        # Lookup before admission prevents unauthorized/nonexistent requests using proof capacity.
        state = read(code)
        report, item = find_item(state, body.report_id, body.item_id)
        if item.get('outcome') not in ('unverified_alternative', 'equivalent_alternative'):
            raise HTTPException(409, '저장된 판단 보류 답안만 재검증합니다. 새 답안을 제출하지 않습니다.')
        if not _slot.acquire(blocking=False):
            raise HTTPException(429, '다른 재검증을 처리 중입니다. 원본은 그대로이며 잠시 뒤 다시 확인하세요.')
        try:
            with store(code) as state:
                report, item = find_item(state, body.report_id, body.item_id)
                records = state.setdefault('attempt_revalidations', [])
                existing = next((r for r in records if r['request_id'] == body.request_id), None)
                if existing:
                    if existing['report_id'] != body.report_id or existing['item_id'] != body.item_id:
                        raise HTTPException(409, '요청 식별자가 다른 문항에 사용되었습니다.')
                    return copy.deepcopy(existing)
                fingerprint = item_fingerprint(item)
                prior = [r for r in records if r['report_id'] == body.report_id and r['item_id'] == body.item_id and r['item_fingerprint'] == fingerprint]
                final = next((r for r in reversed(prior) if (r.get('resolution', {}).get('suggestion') or {}).get('final_verified')), None)
                if final:
                    return copy.deepcopy(final)
                if len(prior) >= MAX_ATTEMPTS or len(records) >= MAX_RECORDS:
                    raise HTTPException(409, '재검증 횟수 상한에 도달했습니다. 미확정을 오답이나 성공으로 바꾸지 않습니다.')
                current = now()
                for r in records:
                    elapsed = (current - datetime.fromisoformat(r['requested_at'])).total_seconds()
                    if elapsed < COOLDOWN_SECONDS or (r['status'] == 'pending' and elapsed < 30):
                        raise HTTPException(429, '앞선 재검증 결과를 먼저 확인하세요. 중복 분석하지 않습니다.')
                saved_item = copy.deepcopy(item)
                source_policy = report.get('answer_policy', 'reference-line-v1')
                record = {'id': uuid.uuid4().hex, 'request_id': body.request_id,
                          'report_id': body.report_id, 'item_id': body.item_id,
                          'item_fingerprint': fingerprint, 'requested_at': current.isoformat(),
                          'status': 'pending', 'attempt': len(prior) + 1, 'limit': MAX_ATTEMPTS}
                records.append(record)
                record_id = record['id']
            try:
                resolution = resolve_attempt(saved_item, report_policy=source_policy, max_nodes=6000, seconds=.15)
            except Exception:
                resolution = {'status': 'unknown', 'reason': 'review_execution_failure', 'suggestion': None}
            with store(code) as state:
                _, original = find_item(state, body.report_id, body.item_id)
                saved = next(r for r in state['attempt_revalidations'] if r['id'] == record_id)
                if item_fingerprint(original) != fingerprint:
                    resolution = {'status': 'unknown', 'reason': 'original_changed', 'suggestion': None}
                saved.update(status='completed', finished_at=now().isoformat(), resolution=resolution)
                return copy.deepcopy(saved)
        finally:
            _slot.release()
