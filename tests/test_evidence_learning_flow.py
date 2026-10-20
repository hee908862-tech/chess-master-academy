"""Read-only move explanations, stored grading, and verification boundaries."""
import copy
import chess
import pytest
from journey_evidence import learning_observation
from test_learning import setup
from test_learning_bridge import report_fixture, post, action, state_from
from test_journey import attach, post as journey_post, act, saved


def sample(outcome='partial_execution', submitted=None):
    return {'fen':chess.STARTING_FEN,'line':['e2e4','e7e5','g1f3','b8c6'],
            'submitted':['e2e4'] if submitted is None else submitted,'outcome':outcome}

@pytest.mark.parametrize('outcome,label', [('not_answered','미응답'),('partial_execution','일부 수행'),('verified_error','큰 손실'),('unverified_alternative','판단 보류'),('equivalent_alternative','비슷한 대안'),('completed','전체 수순 성공')])
def test_labels_do_not_turn_uncertainty_into_error(outcome,label):
    item=sample(outcome);before=copy.deepcopy(item)
    result=learning_observation(item)
    assert label in result['label'] and item==before
    assert result['observed']==['e4']
    assert result['reference']['san']=='Nf3' and result['reference']['own_move']==2


def test_reference_stops_at_actual_deviation_and_invalid_data_is_not_explained():
    result=learning_observation(sample('unverified_alternative',['d2d4']))
    assert result['observed']==['d4'] and result['reference']['san']=='e4'
    result=learning_observation(sample('not_answered',[]))
    assert not result['observed'] and result['reference']['own_move']==1
    bad=sample();bad['line']=['e2e5'];assert learning_observation(bad)['reference'] is None
    bad['fen']='invalid';assert learning_observation(bad)['reference'] is None
    finished=learning_observation(sample('completed',['e2e4','g1f3']))
    assert finished['reference'] is None


def test_rule_facts_are_from_actual_board():
    item={'fen':'7k/5K2/6Q1/8/8/8/8/8 w - - 0 1','line':['g6g7'],'outcome':'not_answered','submitted':[]}
    assert '기준 수 뒤 체크메이트입니다.' in learning_observation(item)['reference']['facts']


def test_status_observations_never_change_reports_or_active_answers(setup):
    c,ns,old,path=attach(setup)
    s=journey_post(c,'start',{'mode':'targeted','competency':'mate'})
    assert c.get('/api/journey').json()['learning_evidence']=={}
    while s['phase']!='complete':s=act(c,s,'skip' if s['phase']=='question' else 'next')
    before=saved(path)
    result=c.get('/api/journey').json()
    assert result['learning_evidence'][s['report']['id']]
    assert saved(path)==before
    assert result['latest']==before['results'][-1]
    assert c.get('/api/journey',headers={'Authorization':'B'}).json()['learning_evidence']=={}


def test_training_link_survives_resume_but_is_hidden_in_verification(setup):
    client,ns,old,db=setup;report,item=report_fixture(ns)
    linked=post(client,'from-diagnosis',{'report_id':report['id'],'item_id':item['id']})
    assert linked['active']['learning_link']['item_id']==item['id']
    s=linked['active']
    for move in item['line'][::2]:
        if s['done']:break
        s=action(client,s,'move',move)
    # Verification of the same position is deliberately not independent; no answer metadata leaks.
    verify=post(client,'start',{'card_id':s['card_id'],'mode':'verify'})
    assert verify['learning_link'] is None and verify['concept'] is None
    assert client.get('/api/learning/dashboard').json()['active']['learning_link'] is None
