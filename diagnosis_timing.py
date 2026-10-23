"""Untrusted active-thinking telemetry. Never changes an answer or score.

The browser measures foreground thinking segments; server timestamps only bound
what can be accepted. They cannot prove attention or remove every interruption.
"""
from copy import deepcopy
from datetime import datetime, timezone
import statistics
import re

VERSION = 'thinking-time-v1'
MAX_ACTIVE_MS = 30 * 60 * 1000
MAX_STREAMS = 4
MAX_SEQUENCE = 1_000_000
CLOCK_TOLERANCE_MS = 250
MIN_TREND_OBSERVATIONS = 3
_STREAM = re.compile(r'^[A-Za-z0-9_-]{8,64}$')


def _at(value):
    try:
        result = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def _record(item):
    old = item.get('thinking_time')
    if isinstance(old, dict) and old.get('version') == VERSION:
        return old
    result = {'version': VERSION, 'source': 'client_active_segments', 'trusted': False,
              'availability': 'unmeasured', 'active_ms': None, 'usable_for_trend': False,
              'streams': {}, 'flags': [], 'accepted_events': 0, 'ignored_events': 0,
              'note': '브라우저가 보고한 활동 시간입니다. 실력 점수·정확도·집중력을 뜻하지 않습니다.'}
    item['thinking_time'] = result
    return result


def _flag(record, reason):
    if reason not in record['flags'] and len(record['flags']) < 12:
        record['flags'].append(reason)
    record['usable_for_trend'] = False
    record['ignored_events'] = min(1000, record.get('ignored_events', 0) + 1)


def accumulate(item, payload, now):
    """Apply one optional cumulative stream event inside the answer transaction.

    Missing telemetry remains unknown, including legacy items. Invalid telemetry
    is ignored/flagged and NEVER raises to reject an otherwise valid chess move.
    Replayed or older sequence numbers are no-ops. Caller owns persistence and
    authentication, and must not call this after the item's outcome is finalized.
    """
    if payload is None:
        return deepcopy(item.get('thinking_time'))
    record = _record(item)
    if (not isinstance(payload, dict) or payload.get('version') != VERSION
            or not isinstance(payload.get('stream_id'), str)
            or not _STREAM.fullmatch(payload['stream_id'])
            or not _integer(payload.get('seq'), 1, MAX_SEQUENCE)
            or not _integer(payload.get('active_ms'), 0, MAX_ACTIVE_MS)):
        _flag(record, 'invalid_payload')
        return deepcopy(record)
    stream_id, seq, client_ms = payload['stream_id'], payload['seq'], payload['active_ms']
    previous = record['streams'].get(stream_id)
    if previous and seq <= previous['seq']:
        return deepcopy(record)
    if previous and client_ms < previous['client_ms']:
        _flag(record, 'non_monotonic_client_time')
        return deepcopy(record)
    if previous is None and len(record['streams']) >= MAX_STREAMS:
        _flag(record, 'too_many_streams')
        return deepcopy(record)
    current, shown = _at(now), _at(item.get('shown_at'))
    if current is None or shown is None or current < shown:
        _flag(record, 'server_clock_unavailable')
        return deepcopy(record)
    last_at = _at(record.get('last_server_at')) or shown
    if current < last_at:
        _flag(record, 'server_clock_reversed')
        return deepcopy(record)
    if previous is None and record['streams']:
        _flag(record, 'multiple_streams')
    delta = client_ms - (previous['client_ms'] if previous else 0)
    elapsed = max(0, int((current - last_at).total_seconds() * 1000))
    total_elapsed = max(0, int((current - shown).total_seconds() * 1000))
    total = record['active_ms'] or 0
    # Absolute wall time and per-event wall time bound concurrent/forged clients.
    room = max(0, min(MAX_ACTIVE_MS - total, total_elapsed - total))
    accepted = min(delta, elapsed, room)
    if delta > elapsed + CLOCK_TOLERANCE_MS or delta > room + CLOCK_TOLERANCE_MS:
        _flag(record, 'exceeds_server_elapsed')
    record['streams'][stream_id] = {'seq': seq, 'client_ms': client_ms,
                                    'accepted_ms': (previous or {}).get('accepted_ms', 0) + accepted}
    if payload.get('limited') is True:_flag(record, 'client_measurement_limited')
    if payload.get('explicit_pause_used') is True:_flag(record, 'explicit_pause_used')
    record['active_ms'] = total + accepted
    record['availability'] = 'observed' if record['active_ms'] > 0 else 'unmeasured'
    record['last_server_at'] = current.isoformat()
    record['accepted_events'] = min(MAX_SEQUENCE, record['accepted_events'] + 1)
    record['usable_for_trend'] = record['active_ms'] > 0 and not record['flags']
    return deepcopy(record)


def public_timing(item):
    """Unknown is None, not zero seconds. Stream cursors enable reload reconciliation."""
    value = item.get('thinking_time')
    if not isinstance(value, dict) or value.get('version') != VERSION:
        return {'version': VERSION, 'availability': 'unmeasured', 'active_ms': None,
                'trusted': False, 'usable_for_trend': False, 'streams': {},
                'note': '이 문항에는 활동 시간 측정 기록이 없습니다.'}
    return deepcopy(value)


def timing_trend(items):
    """Separate descriptive fluency, never a rating or causal improvement claim.

    A comparison group requires >=3 independent accurate observations. A trend
    needs two such groups (>=6), in chronological source order and one contract.
    """
    groups = {}
    for item in items:
        value = item.get('thinking_time') or {}
        duration = value.get('active_ms')
        if (item.get('outcome') != 'completed' or item.get('independent') is not True
                or item.get('app_new') is not True or item.get('first_attempt') is not True
                or item.get('helped') or value.get('version') != VERSION
                or not value.get('usable_for_trend') or not _integer(duration, 1, MAX_ACTIVE_MS)):
            continue
        tags=item.get('tags') or item.get('themes')
        if isinstance(tags,str):tags=tags.split()
        if not isinstance(tags,(list,tuple)) or not tags or any(not isinstance(tag,str) for tag in tags):continue
        if not _integer(item.get('rating'),1,10000):continue
        required=item.get('total_plies') or len(item.get('expected') or []) or ((len(item.get('line') or [])+1)//2)
        if (not item.get('competency') or len(item.get('band') or [])!=2 or not item.get('fen')
                or item.get('measurement_scope') in (None,'unrecorded') or item.get('score_version') in (None,'unrecorded')
                or not _integer(required,1,100)):continue
        key = (item.get('competency'), tuple(item.get('band') or []),
               item.get('answer_policy', 'reference-line-v1'),
               item['measurement_scope'], item['score_version'], required, item['rating'], tuple(sorted(set(tags))))
        group = groups.setdefault(key, [])
        identity = item.get('puzzle_id')
        if not identity or any(row['puzzle_id'] == identity or ' '.join(row['fen'].split()[:4]) == ' '.join(item['fen'].split()[:4]) for row in group):
            continue
        group.append(item)
    result = []
    for key, rows in groups.items():
        rows.sort(key=lambda row: str(row.get('completed_at') or row.get('shown_at') or ''))
        count = len(rows)
        point = {'competency': key[0], 'band': list(key[1]), 'answer_policy': key[2],
                 'measurement_scope': key[3], 'score_version': key[4], 'required_own_moves':key[5], 'source_rating':key[6], 'themes':list(key[7]), 'count': count,
                 'status': 'insufficient' if count < MIN_TREND_OBSERVATIONS else 'reference',
                 'median_active_ms': None, 'previous_median_ms': None, 'change_ms': None,
                 'note': '정확하게 완료한 독립 관찰의 활동 시간 참고입니다. 속도는 실력 점수에 합산하지 않습니다.'}
        if count >= MIN_TREND_OBSERVATIONS:
            recent = rows[-MIN_TREND_OBSERVATIONS:]
            point['median_active_ms'] = int(statistics.median(row['thinking_time']['active_ms'] for row in recent))
        if count >= 2 * MIN_TREND_OBSERVATIONS:
            previous = rows[-2 * MIN_TREND_OBSERVATIONS:-MIN_TREND_OBSERVATIONS]
            point['previous_median_ms'] = int(statistics.median(row['thinking_time']['active_ms'] for row in previous))
            point['change_ms'] = point['median_active_ms'] - point['previous_median_ms']
            point['status'] = 'descriptive_comparison'
        result.append(point)
    return {'version': VERSION, 'trusted': False, 'minimum_observations': MIN_TREND_OBSERVATIONS,
            'status': 'available' if any(row['status'] != 'insufficient' for row in result) else 'insufficient',
            'groups': result, 'note': '같은 분야·외부 난도 수치·주제·필요 착수 수·평가 조건의 정확한 독립 관찰 3개 미만은 시간 요약을 보류합니다. 전후 비교에는 각각 3개가 필요하며 인과적 성장 근거가 아닙니다. 같은 외부 난도 수치도 동일한 실제 난이도를 보장하지 않습니다.'}
