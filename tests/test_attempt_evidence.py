"""Pure synthetic originals, no DB, account identifiers, or historical record writes."""
import copy
import chess
import pytest
from attempt_evidence import summarize_attempts,resolve_attempt,item_fingerprint,execution_observation


def sample(index,outcome='completed',**extra):
    b=chess.Board('7k/8/8/8/8/8/P7/K7 w - - 0 1')
    for bit,square in enumerate([chess.B7,chess.C7,chess.D7,chess.E7,chess.F7]):
        if index & (1<<bit):b.set_piece_at(square,chess.Piece(chess.PAWN,chess.BLACK))
    return {'id':'item-'+str(index),'puzzle_id':'puzzle-'+str(index),'fen':b.fen(),'line':['a2a3'],
            'tags':['endgame'],'competency':'endgame','rating':700+index*17,'band':[600,1200],
            'outcome':outcome,'submitted':['a2a3'] if outcome=='completed' else [],'correct_plies':1 if outcome=='completed' else 0,
            'app_new':True,'first_attempt':True,'helped':False,'independent':True,**extra}


def report(items):
    return {'id':'report-fixture','version':'journey-v5','measurement_scope':'broad_area_execution_v1',
            'corpus_sha256':'fixture-corpus','competency_version':'competency-v2','score_version':'skill-index-v1','internal_skill':{'score':3000},'items':items}


def test_eight_success_two_unknown_never_confirmed_hundred_and_old_score_preserved():
    r=report([sample(i,'completed' if i<8 else 'unverified_alternative') for i in range(10)])
    before=copy.deepcopy(r);view=summarize_attempts([r]);totals=view['totals']
    assert totals['assigned']==totals['original_attempts']==10
    assert totals['success']==8 and totals['unresolved']==2 and totals['completion_ratio']==.8
    assert totals['logical_bounds']==[.8,1] and totals['confirmed_ratio'] is None
    assert not totals['all_resolved'] and view['new_skill_score'] is None and r==before


def test_verified_wrong_remains_observation_and_unknown_is_not_failure():
    totals=summarize_attempts([report([sample(0),sample(1,'verified_non_mate'),sample(2,'unverified_alternative')])])['totals']
    assert totals['verified_wrong']==1 and totals['unresolved']==1
    assert totals['logical_bounds']==[1/3,2/3]
    assert totals['confirmed_ratio'] is None


def test_help_repeat_exposure_separate_and_first_assignment_cannot_be_replaced():
    first=sample(0,'unverified_alternative');repeated={**sample(0),'id':'later-item'}
    rows=[first,repeated,sample(1,helped=True),sample(2,app_new=False),sample(3,first_attempt=False)]
    view=summarize_attempts([report(rows)])
    assert view['totals']['assigned']==5 and view['totals']['original_attempts']==1
    assert view['totals']['excluded']=={'repeat':2,'help':1,'exposed':1}
    assert view['totals']['success']==0 and view['totals']['unresolved']==1
    assert view['attempts'][0]['effective_outcome']=='unverified_alternative'


def test_independence_unknown_never_disappears_or_becomes_confirmed_result():
    totals=summarize_attempts([report([sample(0),sample(1,independent=False),sample(2,app_new=None)])])['totals']
    assert totals['original_attempts']==3 and totals['eligibility_unknown']==2
    assert totals['completion_ratio']==1 and totals['logical_bounds']==[1,1]
    assert totals['confirmed_ratio'] is None and not totals['independence_confirmed']


def test_difficulty_is_exact_external_observation_not_adjusted_ability():
    totals=summarize_attempts([report([sample(0,rating=611),sample(1,rating=1199),sample(2,rating=1453,band=[1200,1800])])])['totals']
    difficulty=totals['external_difficulty']
    assert difficulty['ratings']==[611,1199,1453] and difficulty['min']==611 and difficulty['max']==1453
    assert difficulty['bands']==[[600,1200],[1200,1800]] and not difficulty['calibrated_ability']
    assert totals['execution']['fraction']==1 and not totals['execution']['is_ability_score']


MATE_FEN='7k/8/5K2/8/6Q1/8/8/8 w - - 0 1'


def mate_item(move='g4g3',line=None):
    return {'id':'mate-fixture','puzzle_id':'mate-position','fen':MATE_FEN,'line':line or ['g4g7'],'tags':['mateIn1'],
            'submitted':[move],'responses':[{'fen':MATE_FEN,'move':move,'expected':(line or ['g4g7'])[0]}],
            'outcome':'unverified_alternative','correct_plies':0,'competency':'mate','app_new':True,'first_attempt':True,'helped':False,'independent':True,
            'rating':1000,'band':[600,1200]}


def test_saved_original_mismatch_revalidated_without_changing_source():
    item=mate_item();before=copy.deepcopy(item);resolution=resolve_attempt(item)
    assert resolution['status']=='verified_non_mate' and resolution['suggestion']['final_verified']
    assert resolution['mismatch']['fen']==MATE_FEN and resolution['item_fingerprint']==item_fingerprint(item)
    assert resolution['source_policy']=='reference-line-v1' and item==before
    correction={'report_id':'report-fixture','item_id':item['id'],'item_fingerprint':item_fingerprint(item),'resolution':resolution}
    view=summarize_attempts([report([item])],corrections=[correction])
    assert view['totals']['verified_wrong']==1 and view['totals']['unresolved']==0
    assert view['attempts'][0]['corrected'] and not view['comparison_allowed'] and item==before


def test_positive_candidate_with_unplayed_continuation_not_full_completion():
    item=mate_item('f6g6',['g4g3','h8h7','g3g7']);item['tags']=['mateIn2']
    resolution=resolve_attempt(item)
    assert resolution['status']=='verified_goal' and resolution['proof']['continuation']
    assert resolution['suggestion']=={'outcome':'verified_goal','full_completion':False,'final_verified':False}
    record={'report_id':'report-fixture','item_id':item['id'],'resolution':resolution}
    view=summarize_attempts([report([item])],corrections=[record])
    assert view['totals']['unresolved']==1 and view['totals']['success']==0 and not view['attempts'][0]['corrected']


def test_terminal_mate_is_only_positive_proposal_of_completed_execution():
    item=mate_item('g4g7',['g4g3','h8h7','g3g7']);item['tags']=['mateIn2']
    resolution=resolve_attempt(item)
    assert resolution['status']=='verified_goal' and resolution['suggestion']['full_completion']
    record={'report_id':'report-fixture','item_id':item['id'],'resolution':resolution}
    assert summarize_attempts([report([item])],corrections=[record])['totals']['success']==1


def test_stale_fingerprint_and_other_item_correction_cannot_apply():
    item=mate_item();resolution=resolve_attempt(item)
    for record in [dict(report_id='other-report',item_id=item['id'],resolution=resolution),
                   dict(report_id='report-fixture',item_id='other-item',resolution=resolution),
                   dict(report_id='report-fixture',item_id=item['id'],item_fingerprint='stale',resolution=resolution)]:
        assert summarize_attempts([report([item])],corrections=[record])['totals']['unresolved']==1
    item['reason']='preserved source changed'
    record={'report_id':'report-fixture','item_id':item['id'],'resolution':resolution}
    assert summarize_attempts([report([item])],corrections=[record])['totals']['unresolved']==1


def test_missing_or_alternative_prefix_is_not_guessed():
    item=mate_item('f6g6',['g4g3','h8h7','g3g7']);item['submitted'].append('g4c8')
    item['responses'].append({'fen':'6k1/8/6K1/8/6Q1/8/8/8 w - - 2 2','move':'g4c8','expected':'g4c8'})
    assert resolve_attempt(item)['reason']=='unreconstructible_alternative_prefix'
    item=mate_item();item['responses'][0]['fen']=chess.STARTING_FEN
    assert resolve_attempt(item)['reason']=='nonreference_or_conflicting_prefix'
    assert resolve_attempt({**mate_item(),'submitted':[]})['reason']=='no_saved_submission'


def test_limits_and_unsupported_goal_stay_unknown():
    item=mate_item('f6g6',['g4g3','h8h7','g3g7']);item['tags']=['mateIn2']
    assert resolve_attempt(item,max_nodes=1)['reason']=='mate_proof_budget'
    item['tags']=['advantage']
    assert resolve_attempt(item)['reason']=='unsupported_or_conflicting_mate_objective'
    assert not summarize_attempts([report([item])])['attempts'][0]['revalidatable']
    assert resolve_attempt(mate_item(),report_policy='future-unknown')['reason']=='unsupported_source_policy'


def test_forced_vs_choice_is_legal_option_count_not_importance():
    # Checked king has exactly one legal escape; this says nothing about difficulty.
    fen='7k/8/5K1R/8/8/8/8/8 b - - 0 1'
    b=chess.Board(fen);options=list(b.legal_moves)
    assert b.is_valid() and len(options)==1
    item={'fen':fen,'line':[options[0].uci()],'submitted':[options[0].uci()],'correct_plies':1}
    value=execution_observation(item)
    assert value['forced_submissions']==1 and value['confirmed_forced']==1
    assert value['choice_submissions']==0 and value['fraction']==1
    normal=execution_observation(sample(0))
    assert normal['choice_submissions']==1 and normal['fraction']==1


def timed(index, duration):
    return sample(index,rating=700,thinking_time={'version':'thinking-time-v1','availability':'observed',
                  'active_ms':duration,'trusted':False,'usable_for_trend':True,'flags':[]},
                  completed_at=f'2026-01-{index+1:02d}T00:00:00+00:00')


def test_activity_time_is_descriptive_only_and_missing_time_not_zero():
    rows=[timed(i,t) for i,t in enumerate([9000,8000,7000,6000,5000,4000])]
    before=copy.deepcopy(rows);view=summarize_attempts([report(rows)])
    assert view['attempts'][0]['elapsed_ms']==9000 and not view['attempts'][0]['timing']['trusted']
    group=view['timing_trends']['groups'][0]
    assert group['status']=='descriptive_comparison' and group['median_active_ms']==5000
    assert group['previous_median_ms']==8000 and group['change_ms']==-3000
    assert view['totals']['completion_ratio']==1 and view['new_skill_score'] is None and rows==before
    missing=summarize_attempts([report([sample(0)])])['attempts'][0]
    assert missing['elapsed_ms'] is None and missing['timing']['availability']=='unmeasured'


def test_time_flags_help_repeats_and_versions_do_not_inflate_trend():
    rows=[timed(i,1000+i*100) for i in range(3)]
    rows[1]['thinking_time']['flags']=['multiple_streams'];rows[1]['thinking_time']['usable_for_trend']=False
    rows[2]['helped']=True
    r=report(rows+[copy.deepcopy(rows[0])]);view=summarize_attempts([r])
    assert view['timing_trends']['status']=='insufficient' and view['timing_trends']['groups'][0]['count']==1
    assert view['attempts'][1]['elapsed_ms']==1100 and view['attempts'][1]['timing']['flags']==['multiple_streams']
    # Same task contract but distinct corpus cannot create a single comparison.
    a=report([timed(i,1000) for i in range(3)])
    b=report([timed(i,2000) for i in range(3,6)]);b['corpus_sha256']='other-corpus';b['id']='other-report'
    groups=summarize_attempts([a,b])['timing_trends']['groups']
    assert len(groups)==2 and all(g['status']=='reference' and g['count']==3 for g in groups)


def test_second_saved_mismatch_uses_original_reply_and_remaining_bound():
    line=['g4g3','h8h7','g3g7'];b=chess.Board(MATE_FEN);b.push_uci(line[0]);b.push_uci(line[1])
    item=mate_item('g4g3',line);item['tags']=['mateIn2'];item['submitted']=['g4g3','g3g2'];item['correct_plies']=1
    item['responses']=[{'fen':MATE_FEN,'move':'g4g3','expected':'g4g3'},
                       {'fen':b.fen(),'move':'g3g2','expected':'g3g7'}]
    result=resolve_attempt(item)
    assert result['mismatch']['response_index']==1 and result['mismatch']['fen']==b.fen()
    assert result['proof']['remaining_own_moves']==1 and result['status']=='verified_non_mate'


def test_unassigned_empty_and_missing_evidence_never_synthesize_zero_ability():
    empty=summarize_attempts([])
    assert empty['totals']['logical_bounds'] is None and empty['totals']['confirmed_ratio'] is None
    assert empty['new_skill_score'] is None
    row=sample(0);row.pop('helped');row.pop('independent')
    view=summarize_attempts([report([row])])
    assert view['totals']['eligibility_unknown']==1
    assert set(view['attempts'][0]['eligibility_unknown_reasons'])=={'assistance_unknown','independence_not_established'}
    assert view['totals']['confirmed_ratio'] is None


def test_explicit_unfinished_not_wrong_and_not_hidden_in_possible_full_completion():
    rows=[sample(0),sample(1,'not_answered',skipped=True),sample(2,'partial_execution',skipped=True),
          sample(3,'unverified_alternative'),sample(4,None)]
    total=summarize_attempts([report(rows)])['totals']
    assert total['original_attempts']==5 and total['success']==1 and total['verified_wrong']==0
    assert total['unfinished']==2 and total['partial']==1 and total['skipped']==2
    assert total['unresolved']==1 and total['pending']==1
    assert total['logical_bounds']==[.2,.6] and total['confirmed_ratio'] is None
    known=summarize_attempts([report(rows[:3])])['totals']
    assert known['all_resolved'] and not known['all_goals_completed']
    assert known['confirmed_ratio']==1/3 and known['logical_bounds']==[1/3,1/3]


def test_conflicting_original_goal_is_not_replaced_by_a_guessed_move_bound():
    item=mate_item();item['tags']=['mateIn2']
    assert resolve_attempt(item)['reason']=='unsupported_or_conflicting_mate_objective'
    assert not summarize_attempts([report([item])])['attempts'][0]['revalidatable']
