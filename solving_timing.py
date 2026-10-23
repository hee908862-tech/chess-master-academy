"""Bounded, untrusted solving-time telemetry; independent of legacy thinking time.

The authenticated caller persists changes in the same answer transaction and
supplies server time captured before engine work. Wall-clock bounds cannot prove
attention or prevent a dishonest client from reporting a shorter duration.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import re

VERSION = 'solving-time-v1'
PREPARE_MS = 3000
MAX_ACTIVE_MS = 30 * 60 * 1000
MAX_SEQUENCE = 1_000_000
MAX_STREAMS = 4
CLOCK_TOLERANCE_MS = 250
PREPARATION_DELAY_MS = 5000
SEGMENT_TOLERANCE_MS = 2000
_STREAM = re.compile(r'^[A-Za-z0-9_-]{8,64}$')


def _at(value):
    try:
        result = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def _record(item):
    if isinstance(item.get('solving_time'), dict):
        return item['solving_time']
    item['solving_time'] = {
        'version': VERSION, 'prepare_ms': PREPARE_MS, 'prep_started_at': None,
        'active_ms': None, 'status': 'unmeasured', 'flags': [], 'streams': {},
        'accepted_events': 0, 'trusted': False, 'frozen': False,
        'note': '브라우저가 보고한 풀이 시간이며 실제 집중이나 부정행위 여부를 보장하지 않습니다.',
    }
    return item['solving_time']


def _uncertain(record, reason):
    if reason not in record['flags'] and len(record['flags']) < 16:
        record['flags'].append(reason)
    record['status'] = 'uncertain'


def prepare(item, now):
    """Start the server preparation clock once; repeated requests never reset it."""
    if item.get('outcome'):
        return deepcopy(item.get('solving_time'))
    record = _record(item)
    if record.get('frozen') or record.get('prep_started_at'):
        return deepcopy(record)
    current = _at(now)
    if current is None:
        _uncertain(record, 'server_clock_unavailable')
    else:
        record['prep_started_at'] = current.isoformat()
        shown = _at(item.get('shown_at'))
        if shown is None or current < shown:
            _uncertain(record, 'preparation_origin_unavailable')
        elif (current - shown).total_seconds() * 1000 > PREPARATION_DELAY_MS:
            _uncertain(record, 'preparation_delay')
    return deepcopy(record)


def accumulate(item, payload, now):
    """Consume cumulative telemetry without ever rejecting a valid chess answer.

    Sequence replay is a no-op. Missing, malformed, uncertain or interrupted
    measurements cannot qualify for a speed bonus. This module does not score.
    Call before setting outcome; finalized records are protected as well.
    """
    if item.get('outcome') or (item.get('solving_time') or {}).get('frozen'):
        return deepcopy(item.get('solving_time'))
    record = _record(item)
    if payload is None:
        _uncertain(record, 'missing_telemetry')
        return deepcopy(record)
    if (not isinstance(payload, dict) or payload.get('version') != VERSION
            or not isinstance(payload.get('stream_id'), str)
            or not _STREAM.fullmatch(payload['stream_id'])
            or not _integer(payload.get('seq'), 1, MAX_SEQUENCE)
            or not _integer(payload.get('active_ms'), 0, MAX_ACTIVE_MS)
            or payload.get('prepared') is not True
            or type(payload.get('interrupted')) is not bool
            or type(payload.get('limited')) is not bool):
        _uncertain(record, 'invalid_telemetry')
        return deepcopy(record)
    stream_id, seq, client_ms = payload['stream_id'], payload['seq'], payload['active_ms']
    previous = record['streams'].get(stream_id)
    if previous and seq <= previous['seq']:
        return deepcopy(record)
    if client_ms==0:
        record['active_ms']=record.get('active_ms') or 0
        _uncertain(record, 'zero_duration_below_resolution')
        return deepcopy(record)
    if previous and client_ms < previous['client_ms']:
        _uncertain(record, 'non_monotonic_client_time')
        return deepcopy(record)
    if previous is None and len(record['streams']) >= MAX_STREAMS:
        _uncertain(record, 'too_many_streams')
        return deepcopy(record)
    current, prepared_at = _at(now), _at(record.get('prep_started_at'))
    if prepared_at is None:
        _uncertain(record, 'preparation_not_started')
        return deepcopy(record)
    ready_at = prepared_at + timedelta(milliseconds=PREPARE_MS)
    if current is None or current < prepared_at:
        _uncertain(record, 'server_clock_unavailable')
        return deepcopy(record)
    if current < ready_at:
        _uncertain(record, 'preparation_not_finished')
        return deepcopy(record)
    last_at = _at(record.get('turn_opened_at')) or _at(record.get('last_server_at')) or ready_at
    if current < last_at:
        _uncertain(record, 'server_clock_reversed')
        return deepcopy(record)
    if previous is None and record['streams']:
        if payload['interrupted'] or 'interrupted' in record['flags']:
            if 'multiple_streams' not in record['flags']:
                record['flags'].append('multiple_streams')
        else:
            _uncertain(record, 'multiple_streams')
    delta = client_ms - (previous['client_ms'] if previous else 0)
    elapsed = max(0, int((current - last_at).total_seconds() * 1000))
    total_elapsed = max(0, int((current - ready_at).total_seconds() * 1000))
    total = record['active_ms'] or 0
    room = max(0, min(MAX_ACTIVE_MS - total, total_elapsed - total))
    # A reported interruption explains excluded wall time. Preserve its B=0
    # classification instead of inferring corrupt telemetry from that gap.
    interrupted = payload['interrupted'] or 'interrupted' in record['flags']
    if not interrupted and delta < max(0, elapsed - SEGMENT_TOLERANCE_MS):
        _uncertain(record, 'underreported_time')
    floor = 0 if interrupted else elapsed - SEGMENT_TOLERANCE_MS
    accepted = min(max(delta, floor), elapsed, room)
    if delta > elapsed + CLOCK_TOLERANCE_MS or delta > room + CLOCK_TOLERANCE_MS:
        _uncertain(record, 'exceeds_server_elapsed')
    if payload['limited']:
        _uncertain(record, 'client_measurement_limited')
    if payload['interrupted']:
        if 'interrupted' not in record['flags']:
            record['flags'].append('interrupted')
        if record['status'] != 'uncertain':
            record['status'] = 'interrupted'
    record['streams'][stream_id] = {
        'seq': seq, 'client_ms': client_ms,
        'accepted_ms': (previous or {}).get('accepted_ms', 0) + accepted,
    }
    record['active_ms'] = total + accepted
    record['last_server_at'] = current.isoformat()
    record['turn_opened_at'] = current.isoformat()
    record['accepted_events'] = min(MAX_SEQUENCE, record['accepted_events'] + 1)
    if record['active_ms'] <= 0:
        _uncertain(record, 'no_observed_time')
    elif record['status'] not in ('uncertain', 'interrupted'):
        record['status'] = 'valid'
    return deepcopy(record)


def mark_ready(item, now):
    """Open the next thinking segment after engine work (caller adds animation allowance).

    Call once after an accepted non-final move, inside its persistence transaction.
    Never call for duplicate requests, mere refreshes, or polling responses.
    """
    record = item.get('solving_time')
    if not isinstance(record, dict) or record.get('frozen') or item.get('outcome'):
        return deepcopy(record)
    current = _at(now)
    previous = _at(record.get('last_server_at'))
    if current is None or previous is None or current < previous:
        _uncertain(record, 'ready_clock_unavailable')
    else:
        record['turn_opened_at'] = current.isoformat()
    return deepcopy(record)


def finish(item):
    """Freeze only an existing new-version record; legacy time stays untouched."""
    record = item.get('solving_time')
    if not isinstance(record, dict):
        return None
    if record.get('version') == VERSION:
        if record.get('status') == 'unmeasured':
            _uncertain(record, 'missing_telemetry')
        record['frozen'] = True
    return deepcopy(record)
