import copy
from decimal import Decimal

import pytest

from solving_score import item_score, report_score, target, _points


def item(**updates):
    value = dict(id='one', fen='7k/8/5K2/8/6Q1/8/8/8 w - - 0 1',
                 line=['g4g3', 'h8h7', 'g3g7'], rating=1200, competency='mate',
                 outcome='completed', correct_plies=2, submitted=['g4g3', 'g3g7'],
                 independent=True, helped=False, first_attempt=True, app_new=True,
                 solving_time={'version':'solving-time-v1', 'status':'valid', 'active_ms':1000, 'flags':[]})
    value.update(updates)
    return value


def second(**updates):
    fields=dict(id='two', fen='7k/8/8/8/8/8/P7/K7 w - - 0 1', line=['a2a3'],
                submitted=['a2a3'], correct_plies=1)
    fields.update(updates)
    return item(**fields)


def test_full_score_and_original_preserved():
    source=item(score=71); before=copy.deepcopy(source)
    result=item_score(source)
    assert result['final_score']==3000 and result['base_points']==2850 and result['time_adjustment']==150
    assert source==before
    assert result['execution']['original_choices']==2


def test_rating_continuous_and_counts_target():
    assert target(item(rating=600))['target_seconds']==45
    assert target(item(rating=1200))['target_seconds']==67.5
    assert target(item(rating=1201))['target_seconds']>67.5
    assert target(item(rating=10))['target_seconds']==target(item(rating=600))['target_seconds']
    assert target(item(rating=9000))=={**target(item(rating=2400)), 'rating':9000}
    assert target(item(competency='calculation'))['type_factor']==1.2
    assert target(item(competency='endgame'))['target_seconds']==87.75


def test_target_cap():
    line=['e2e4','e7e5','g1f3','b8c6','f1b5','a7a6','b5a4','g8f6','e1g1','f8e7','f1e1','b7b5','a4b3']
    import chess
    result=target(item(fen=chess.STARTING_FEN,line=line,rating=2400,competency='endgame'))
    assert result['available'] and result['target_seconds']==300


@pytest.mark.parametrize('change',[{'rating':None},{'rating':True},{'rating':float('nan')},{'fen':'bad'}, {'competency':'unknown'}, {'line':['e2e9']}])
def test_bad_target_is_held_not_invented(change):
    result=item_score(item(**change))
    assert result['final_score'] is None and result['base_points']==2850


def test_partial_choices_are_execution_not_difficulty_multiplier():
    low=item_score(item(outcome='partial_execution',correct_plies=1,submitted=['g4g3'],rating=600))
    high=item_score(item(outcome='partial_execution',correct_plies=1,submitted=['g4g3'],rating=2400))
    assert low['A']==high['A']==.25 and low['final_score']==high['final_score']==713
    assert high['final_score']<item_score(item(rating=600))['final_score']
    assert not high['execution']['is_key_skill_estimate']


def test_alternative_prefix_is_not_guessed():
    result=item_score(item(outcome='partial_execution',correct_plies=1,submitted=['f6g6']))
    assert result['A'] is None and result['final_score'] is None
    assert 'alternative_prefix_not_reconstructed' in result['reasons']


def test_forced_moves_gain_no_partial_or_speed_credit():
    forced=item(fen='7k/8/5K1R/8/8/8/8/8 b - - 0 1',line=['h8g8'],submitted=['h8g8'],correct_plies=1,competency='defense',solving_time=None)
    done=item_score(forced)
    assert done['target']['forced_count']==1 and done['target']['choice_count']==0
    assert done['A']==1 and done['B']==0 and done['final_score']==2850
    forced['outcome']='partial_execution'
    assert item_score(forced)['final_score']==1


def test_fast_wrong_loses_to_slow_correct():
    wrong=item_score(item(outcome='verified_error',correct_plies=0,submitted=['g4g5']))
    slow=item_score(item(solving_time={'version':'solving-time-v1','status':'valid','active_ms':999999,'flags':[]}))
    assert wrong['final_score']==1 and slow['final_score']==2850


@pytest.mark.parametrize('duration',[None,0,-1,True,1.2,'1000'])
def test_corrupt_or_missing_time_is_not_silent_penalty(duration):
    result=item_score(item(solving_time={'version':'solving-time-v1','status':'valid','active_ms':duration,'flags':[]}))
    assert result['final_score'] is None and result['base_points']==2850


@pytest.mark.parametrize('status',['uncertain','unmeasured'])
def test_unusable_time_holds(status):
    assert item_score(item(solving_time={'version':'solving-time-v1','status':status,'active_ms':1000}))['final_score'] is None


def test_interruption_explicit_zero_bonus():
    result=item_score(item(solving_time={'version':'solving-time-v1','status':'interrupted','active_ms':1000,'flags':['paused']}))
    assert result['final_score']==2850 and result['B']==0
    assert result['time']['reason']=='explicit_interruption_no_time_bonus'


@pytest.mark.parametrize('change',[{'helped':True},{'app_new':False},{'first_attempt':False},{'independent':False}])
def test_assistance_or_exposure_practice_only(change):
    result=item_score(item(**change))
    assert result['final_score'] is None and result['base_points']==2850 and result['status']=='practice'


@pytest.mark.parametrize('outcome',['unverified_alternative','equivalent_alternative',None])
def test_unresolved_held(outcome):
    result=item_score(item(outcome=outcome))
    assert result['final_score'] is None and result['A'] is None


def test_half_up_combined_and_equal_denominator():
    assert _points(Decimal('.5'))==1426
    assert _points(Decimal(1), Decimal('.01'))==2852
    done=item(solving_time={'version':'solving-time-v1','status':'interrupted','active_ms':1000})
    wrong=second(outcome='verified_error',correct_plies=0,submitted=['a2a4'])
    result=report_score({'items':[done,wrong]})
    assert result['A']==.5 and result['B']==0 and result['final_score']==1426
    assert result['item_count']==2


def test_unknown_retained_in_report_no_optimistic_final():
    result=report_score({'items':[item(),second(outcome='unverified_alternative')]})
    assert result['item_count']==2 and result['final_score'] is None and result['A'] is None


def test_duplicates_not_independent_or_double_weighted():
    first=item(); duplicate=copy.deepcopy(first)
    result=report_score({'items':[first,duplicate]})
    assert result['item_count']==1 and result['duplicate_assignments']==1 and result['final_score']==3000
    duplicate['id']='another'
    result=report_score({'items':[first,duplicate]})
    assert result['item_count']==2 and result['final_score'] is None
    assert 'repeated_position_in_report' in result['items'][1]['reasons']
    duplicate['id']='one';duplicate['outcome']='verified_error'
    assert 'conflicting_duplicate_assignment' in report_score({'items':[first,duplicate]})['reasons']


def test_time_monotonic_and_bounds():
    values=[]
    for duration in [1,67500,70000,101250,135000,999999]:
        values.append(item_score(item(solving_time={'version':'solving-time-v1','status':'valid','active_ms':duration,'flags':[]}))['final_score'])
    assert values==sorted(values,reverse=True)
    assert all(2850<=n<=3000 for n in values)
    assert values[3]==2925


def test_recorded_time_is_retained_when_bonus_ineligible():
    result=item_score(item(outcome='verified_error',correct_plies=0,submitted=['g4g5']))
    assert result['time']['active_ms']==1000 and result['time']['measurement_status']=='valid'
    assert result['B']==0 and result['time']['reason']=='goal_not_completed'


def test_time_version_flags_and_missing_goal_are_held():
    for value in [None, {'version':'old','status':'valid','active_ms':1000},
                  {'version':'solving-time-v1','status':'valid','active_ms':1000,'flags':['clock_conflict']}]:
        assert item_score(item(solving_time=value))['final_score'] is None
    assert item_score(item(competency=[]))['final_score'] is None


def test_saved_prefix_conflict_is_held_and_empty_report_not_zero():
    result=item_score(item(outcome='partial_execution',correct_plies=1,submitted=['g4g3'],
                           responses=[{'fen':'7k/8/8/8/8/8/P7/K7 w - - 0 1','move':'g4g3'}]))
    assert result['A'] is None and 'saved_prefix_conflict' in result['reasons']
    assert report_score({'items':[]})['final_score'] is None


def test_explicit_skip_zero_is_observation_not_unknown():
    result=item_score(item(outcome='not_answered',correct_plies=0,submitted=[]))
    assert result['A']==0 and result['B']==0 and result['final_score']==1


def test_target_policy_and_zero_resolution_distinct_from_missing():
    zero=item_score(item(solving_time={'version':'solving-time-v1','status':'valid','active_ms':0}))
    missing=item_score(item(solving_time={'version':'solving-time-v1','status':'valid','active_ms':None}))
    positive=item_score(item(solving_time={'version':'solving-time-v1','status':'valid','active_ms':1}))
    assert zero['time']['reason']=='zero_duration_below_resolution'
    assert missing['time']['reason']!='zero_duration_below_resolution'
    assert zero['final_score'] is None and missing['final_score'] is None
    assert positive['final_score']==3000
    assert positive['target']['version']==positive['target_policy_version']=='authored-target-v1'
    assert report_score({'items':[item()]})['target_policy_version']=='authored-target-v1'
