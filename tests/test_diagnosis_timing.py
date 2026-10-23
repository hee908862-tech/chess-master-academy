"""Synthetic timestamps only; timing never participates in score calculations."""
import copy
from datetime import datetime,timedelta,timezone
import pytest
from diagnosis_timing import VERSION,MAX_ACTIVE_MS,accumulate,public_timing,timing_trend

ZERO=datetime(2026,10,23,tzinfo=timezone.utc)


def event(seq=1,active=5000,stream='browser_stream_01',**extra):
    return dict(version=VERSION,stream_id=stream,seq=seq,active_ms=active,**extra)


def item():return {'shown_at':ZERO.isoformat(),'outcome':'completed','score':3000}


def test_cumulative_deltas_duplicate_and_old_response_are_idempotent():
    value=item();before=copy.deepcopy(value)
    first=accumulate(value,event(),ZERO+timedelta(seconds=8))
    assert first['active_ms']==5000 and first['usable_for_trend'] and not first['trusted']
    second=accumulate(value,event(2,8000),ZERO+timedelta(seconds=12))
    assert second['active_ms']==8000
    snapshot=copy.deepcopy(value)
    assert accumulate(value,event(2,8000),ZERO+timedelta(seconds=20))==second
    assert accumulate(value,event(1,5000),ZERO+timedelta(seconds=21))==second
    assert value==snapshot and value['score']==before['score'] and value['outcome']==before['outcome']


@pytest.mark.parametrize('bad',[{},'bad',event(active=-1),event(active=MAX_ACTIVE_MS+1),event(active=float('nan')),event(seq=True),event(seq=0),event(stream='bad!')])
def test_invalid_telemetry_does_not_reject_answer_or_invent_seconds(bad):
    value=item();record=accumulate(value,bad,ZERO+timedelta(seconds=10))
    assert record['active_ms'] is None and not record['usable_for_trend']
    assert record['flags']==['invalid_payload']
    assert value['score']==3000 and value['outcome']=='completed'


def test_missing_legacy_is_unknown_not_zero_and_read_is_nonmutating():
    value=item();before=copy.deepcopy(value)
    assert accumulate(value,None,ZERO) is None
    assert public_timing(value)['active_ms'] is None
    assert value==before


def test_forged_elapsed_clamped_and_regression_invalidates_fluency_only():
    value=item();r=accumulate(value,event(active=10000),ZERO+timedelta(seconds=2))
    assert r['active_ms']==2000 and 'exceeds_server_elapsed' in r['flags'] and not r['usable_for_trend']
    r=accumulate(value,event(2,9000),ZERO+timedelta(seconds=5))
    assert r['active_ms']==2000 and 'non_monotonic_client_time' in r['flags']
    assert value['score']==3000


def test_reload_same_stream_no_absence_credit_and_clock_bounds():
    value=item();accumulate(value,event(active=1000),ZERO+timedelta(seconds=2))
    # One hour absent but only 2 seconds foreground after return.
    r=accumulate(value,event(2,3000),ZERO+timedelta(hours=1))
    assert r['active_ms']==3000 and r['usable_for_trend']
    r=accumulate(value,event(3,4000),ZERO+timedelta(seconds=30))
    assert r['active_ms']==3000 and 'server_clock_reversed' in r['flags']
    invalid={'shown_at':'unknown'};assert accumulate(invalid,event(),ZERO)['active_ms'] is None


def test_concurrent_streams_bounded_and_not_comparable():
    value=item()
    for i in range(6):r=accumulate(value,event(active=1000,stream=f'browser_stream_{i:02}'),ZERO+timedelta(seconds=i+2))
    assert len(r['streams'])==4 and r['active_ms']<=6000 and not r['usable_for_trend']
    assert 'multiple_streams' in r['flags'] and 'too_many_streams' in r['flags']
    assert accumulate(item(),event(limited=True),ZERO+timedelta(seconds=10))['usable_for_trend'] is False


def row(i,duration=5000):
    return {'puzzle_id':str(i),'fen':f'position-{i} w - - 0 1','outcome':'completed','independent':True,
            'app_new':True,'first_attempt':True,'helped':False,'competency':'mate','band':[600,1200],
            'rating':950,'tags':['mateIn2','short'],'answer_policy':'goal-alternatives-v1','measurement_scope':'broad_area_execution_v1',
            'score_version':'skill-index-v1','total_plies':2,'completed_at':(ZERO+timedelta(minutes=i)).isoformat(),
            'thinking_time':{'version':VERSION,'active_ms':duration,'usable_for_trend':True}}


def test_timing_summary_requires_three_and_trend_requires_two_groups_of_three():
    rows=[row(i,1000*(i+1)) for i in range(6)]
    assert timing_trend(rows[:2])['status']=='insufficient'
    one=timing_trend(rows[:3])['groups'][0]
    assert one['median_active_ms']==2000 and one['status']=='reference' and one['change_ms'] is None
    both=timing_trend(rows)['groups'][0]
    assert both['median_active_ms']==5000 and both['previous_median_ms']==2000 and both['change_ms']==3000
    assert both['status']=='descriptive_comparison'


@pytest.mark.parametrize('field,value',[('outcome','verified_error'),('helped',True),('app_new',False),('first_attempt',False),('independent',False),('measurement_scope',None),('score_version',None)])
def test_timing_only_accurate_independent_same_known_conditions(field,value):
    rows=[row(i) for i in range(3)];rows[-1][field]=value
    assert timing_trend(rows)['status']=='insufficient'


def test_timing_deduplicates_and_separates_policy_depth_and_band():
    rows=[row(i) for i in range(3)]
    repeated=copy.deepcopy(rows[0]);repeated['puzzle_id']='same-position';repeated['fen']=repeated['fen'].replace('0 1','10 50')
    assert timing_trend([rows[0],repeated,rows[1]])['status']=='insufficient'
    for key,value in [('answer_policy','reference-line-v1'),('total_plies',4),('band',[1200,1800]),('rating',951),('tags',['mateIn2','long'])]:
        changed=copy.deepcopy(rows);changed[-1][key]=value
        assert timing_trend(changed)['status']=='insufficient'


def test_explicit_pause_excludes_trend_without_changing_score():
    value=item();record=accumulate(value,event(explicit_pause_used=True),ZERO+timedelta(seconds=10))
    assert record['active_ms']==5000 and not record['usable_for_trend']
    assert 'explicit_pause_used' in record['flags'] and value['score']==3000

def test_same_tags_order_is_equivalent_and_unknown_source_rating_is_insufficient():
    rows=[row(i) for i in range(3)];rows[-1]['tags'].reverse()
    assert timing_trend(rows)['status']=='available'
    rows[-1].pop('rating')
    assert timing_trend(rows)['status']=='insufficient'
