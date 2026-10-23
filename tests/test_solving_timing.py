"""Synthetic server clocks; no accounts, engines, or score mutation."""
import copy
from datetime import datetime, timedelta, timezone
import pytest
from solving_timing import VERSION, MAX_ACTIVE_MS, prepare, accumulate, finish, mark_ready

ZERO = datetime(2026, 10, 23, tzinfo=timezone.utc)


def at(seconds):
    return ZERO + timedelta(seconds=seconds)


def event(seq=1, ms=1000, **changes):
    return dict(version=VERSION, stream_id='browser_stream_01', seq=seq,
                active_ms=ms, prepared=True, interrupted=False, limited=False, **changes)


def ready():
    item = {'shown_at': ZERO.isoformat(), 'score': 1501, 'thinking_time': {'version': 'thinking-time-v1', 'active_ms': 9999}}
    prepare(item, ZERO)
    return item


def test_prepare_is_idempotent_no_reset_and_no_legacy_mutation():
    item = ready(); before = copy.deepcopy(item)
    assert prepare(item, at(20)) == before['solving_time']
    assert item == before
    assert item['solving_time']['prepare_ms'] == 3000
    assert item['solving_time']['active_ms'] is None
    assert item['solving_time']['status'] == 'unmeasured'


def test_preparation_is_excluded_and_duplicate_cannot_add_or_lose_time():
    item = ready()
    record = accumulate(item, event(), at(4))
    assert record['active_ms'] == 1000 and record['status'] == 'valid'
    record = accumulate(item, event(2, 3000), at(6))
    assert record['active_ms'] == 3000
    before = copy.deepcopy(item)
    accumulate(item, event(2, 3000), at(99)); accumulate(item, event(), at(100)); accumulate(item,event(1,0),at(101))
    assert item == before
    assert item['score'] == 1501 and item['thinking_time']['active_ms'] == 9999


@pytest.mark.parametrize('seconds', [0, 2.999])
def test_early_answer_time_is_uncertain_without_rejecting_answer(seconds):
    item = ready(); record = accumulate(item, event(), at(seconds))
    assert record['status'] == 'uncertain' and record['active_ms'] is None
    assert 'preparation_not_finished' in record['flags']
    assert item['score'] == 1501


@pytest.mark.parametrize('payload', [None, {}, 'bad', [], {'version': 'thinking-time-v1'},
    event(ms=-1), event(ms=MAX_ACTIVE_MS+1), event(ms=float('nan')),
    event(seq=True), event(seq=0)])
def test_invalid_or_absent_telemetry_never_becomes_fast_bonus(payload):
    item = ready(); record = accumulate(item, payload, at(5))
    assert record['status'] == 'uncertain' and record['active_ms'] is None
    assert item['score'] == 1501


@pytest.mark.parametrize('field,value', [('prepared',False), ('interrupted','false'), ('limited',None), ('stream_id','bad!')])
def test_boolean_and_stream_contract_is_strict(field,value):
    payload=event();payload[field]=value
    assert accumulate(ready(),payload,at(5))['status']=='uncertain'


def test_interruption_sticky_and_uncertainty_has_priority():
    item=ready();payload=event();payload['interrupted']=True
    record=accumulate(item,payload,at(5))
    assert record['status']=='interrupted' and record['active_ms']==1000
    assert accumulate(item,event(2,2000),at(6))['status']=='interrupted'
    assert accumulate(item,{},at(7))['status']=='uncertain'
    payload=event(3,3000);payload['interrupted']=True
    assert accumulate(item,payload,at(8))['status']=='uncertain'


def test_limit_and_clock_clamps_never_qualify_for_bonus():
    item=ready();record=accumulate(item,event(ms=8000),at(4))
    assert record['active_ms']==1000 and record['status']=='uncertain'
    assert 'exceeds_server_elapsed' in record['flags']
    assert accumulate(item,event(2,9000),at(5))['active_ms']==2000
    record=accumulate(item,event(3,10000),at(4))
    assert 'server_clock_reversed' in record['flags'] and record['active_ms']==2000
    payload=event();payload['limited']=True
    assert accumulate(ready(),payload,at(5))['status']=='uncertain'


def test_exact_ready_boundary_is_not_zero_millisecond_valid_time():
    record=accumulate(ready(),event(ms=1),at(3))
    assert record['active_ms']==0 and record['status']=='uncertain'


def test_missing_preparation_and_invalid_server_time_are_uncertain():
    assert accumulate({},event(),at(10))['status']=='uncertain'
    item={};assert prepare(item,'bad')['status']=='uncertain'
    prepare(item,ZERO)
    assert accumulate(item,event(),at(5))['status']=='uncertain'
    assert accumulate(ready(),event(),'bad')['status']=='uncertain'


def test_concurrent_streams_bounded_and_non_monotonic_never_qualifies():
    item=ready();accumulate(item,event(),at(5))
    record=accumulate(item,event(2,999),at(6))
    assert record['active_ms']==1000 and record['status']=='uncertain'
    for i in range(1,6):
        payload=event();payload['stream_id']=f'browser_stream_{i+1:02}'
        record=accumulate(item,payload,at(6+i))
    assert len(record['streams'])==4 and record['active_ms']==4000
    assert 'multiple_streams' in record['flags'] and 'too_many_streams' in record['flags']


def test_freeze_and_final_outcome_protect_original_time():
    item=ready();accumulate(item,event(),at(5));finish(item)
    before=copy.deepcopy(item)
    accumulate(item,event(2,10000),at(50));prepare(item,at(100));finish(item)
    assert item==before
    item=ready();accumulate(item,event(),at(5));item['outcome']='completed';before=copy.deepcopy(item)
    accumulate(item,event(2,2000),at(9));assert item==before
    legacy={'thinking_time':{'active_ms':1234},'outcome':'completed'};before=copy.deepcopy(legacy)
    assert finish(legacy) is None and accumulate(legacy,event(),at(9)) is None
    assert legacy==before


def test_unmeasured_finish_unknown_not_zero():
    item=ready();record=finish(item)
    assert record['active_ms'] is None and record['status']=='uncertain' and record['frozen']


def test_late_prepare_is_uncertain_and_not_resettable():
    item={'shown_at':ZERO.isoformat()}
    record=prepare(item,at(6))
    assert record['prep_started_at']==at(6).isoformat() and record['status']=='uncertain'
    assert 'preparation_delay' in record['flags']
    assert prepare(item,at(8))==record
    assert accumulate(item,event(),at(10))['status']=='uncertain'

def test_low_reporting_is_uncertain_and_server_floor_recorded():
    item=ready();record=accumulate(item,event(ms=1),at(13))
    assert record['active_ms']==8000 and record['status']=='uncertain'
    assert 'underreported_time' in record['flags']
    payload=event(2,2);payload['interrupted']=True
    assert accumulate(item,payload,at(20))['status']=='uncertain'

def test_known_engine_wait_excluded_by_next_turn_open_timestamp():
    item=ready();record=accumulate(item,event(),at(4))
    assert record['active_ms']==1000 and record['status']=='valid'
    mark_ready(item,at(30.3))
    record=accumulate(item,event(2,2000),at(31.3))
    assert record['active_ms']==2000 and record['status']=='valid'
    before=copy.deepcopy(item);accumulate(item,event(2,2000),at(50));assert item==before

def test_prepare_delay_and_segment_tolerances_are_explicit_boundaries():
    item={'shown_at':ZERO.isoformat()};prepare(item,at(5))
    assert accumulate(item,event(ms=1000),at(11))['status']=='valid'
    item=ready();assert accumulate(item,event(ms=1000),at(6.001))['status']=='uncertain'


def test_known_long_pause_excludes_gap_without_inventing_uncertainty():
    item=ready();payload=event();payload['interrupted']=True
    record=accumulate(item,payload,at(24))
    assert record['active_ms']==1000 and record['status']=='interrupted'
    assert record['flags']==['interrupted']
    # Interruption remains known even if a later client omits its flag.
    record=accumulate(item,event(2,2000),at(45))
    assert record['active_ms']==2000 and record['status']=='interrupted'

def test_interruption_does_not_excuse_overreporting_but_new_stream_is_known_interruption():
    item=ready();payload=event(ms=10000);payload['interrupted']=True
    assert accumulate(item,payload,at(4))['status']=='uncertain'
    item=ready();payload=event();payload['interrupted']=True
    accumulate(item,payload,at(24))
    payload['stream_id']='another_stream_01'
    record=accumulate(item,payload,at(30))
    assert record['status']=='interrupted' and record['active_ms']==2000
    assert 'multiple_streams' in record['flags']
    assert record['streams']['another_stream_01']['accepted_ms']==1000


def test_zero_duration_is_explicitly_unresolved_not_missing_or_bonus():
    record=accumulate(ready(),event(ms=0),at(5))
    assert record['active_ms']==0 and record['status']=='uncertain'
    assert 'zero_duration_below_resolution' in record['flags']
