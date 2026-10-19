"""Uncertainty is not failure; scope and app-local exposure stay explicit."""
import copy
from datetime import datetime, timedelta, timezone
from journey_evidence import build_report, additional_plan, recheck_gate, CUED, UNCUED, JOURNEY_VERSION
from test_learning import setup
from test_journey import attach, post, act, saved

NOW=datetime(2026,10,19,tzinfo=timezone.utc)
FEN='7k/8/8/8/8/8/8/KQ6 w - - 0 1'


def item(outcome='unverified_alternative',**kw):
    return dict(id='i',competency='mate',fen=FEN,complete=False,first_correct=False,
                reason='판단 보류',outcome=outcome,app_new=True,independent=False,
                completed_at=NOW.isoformat(),**kw)


def report(rows,scope=CUED,previous=None):
    return build_report({'items':rows,'version':JOURNEY_VERSION,'session_id':'s','mode':'basic',
                         'measurement_scope':scope},previous or [],NOW)


def test_unverified_and_unanswered_are_not_failure_or_weakness():
    result=report([item(),item('not_answered')]);area=result['areas'][0]
    assert area['assessed_denominator']==0
    assert area['unverified']==1 and area['unanswered']==1
    assert area['verified_not_completed']==0 and area['app_new_attempts']==0
    assert len(result['recommendations'])==1 and result['recommendations'][0]['intent']=='practice'
    assert len(result['comparison_practice'])==1


def test_unknown_legacy_exposure_does_not_poison_new_app_tracking():
    row=item('completed');row.update(complete=True,first_correct=True,legacy_exposure_unknown=True,prior_exposure_unknown=True)
    area=report([row])['areas'][0]
    assert area['independent']==0 and area['app_new_attempts']==1
    assert area['evidence']['tracked']==1 and area['full_success']==1
    row['app_new']=False
    assert report([row])['areas'][0]['evidence']['tracked']==0


def test_guidance_never_combines_cued_uncued_or_old_versions():
    row=item('completed');row.update(complete=True,first_correct=True)
    prior=report([row]);old=copy.deepcopy(prior);old['version']='journey-v2'
    for scope,prev in [(UNCUED,prior),(CUED,old)]:
        assert report([],scope,[prev])['areas'][0]['evidence']['tracked']==0
    assert report([],CUED,[prior])['areas'][0]['evidence']['tracked']==1


def test_additional_difficulty_follows_observed_completion():
    assert additional_plan([],'mate')['band']==[600,1200]
    assert additional_plan([{'areas':[{'id':'mate','count':2,'full_success':2}]}, {'areas':[{'id':'mate','count':0,'full_success':0}]}],'mate')['band']==[1200,1800]
    for count,band in [(0,[600,1200]),(1,[900,1500]),(2,[1200,1800])]:
        assert additional_plan([{'areas':[{'id':'mate','full_success':count}]}],'mate')['band']==band


def test_recheck_status_date_moves_after_related_exposure():
    learning={'cards':{'source':{'diagnosis':{'report_id':'s'},'category':'mate','exposure':{}},
                       'fresh':{'selection':{'source_card':'source'},'exposure':{}}},
              'attempts':[{'at':NOW.isoformat(),'card_id':'fresh','selection':{'source_card':'source'},
                           'mode':'verify','fresh':True,'helped':False,'assessment_scope':'full_line'}]}
    gate=recheck_gate(learning,'mate',NOW)
    assert gate['ready_at']==(NOW+timedelta(days=7)).isoformat() and not gate['eligible']
    assert recheck_gate(learning,'mate',NOW+timedelta(days=7))['eligible']
    learning['cards']['source']['exposure']['2026-10-22']={'last_at':(NOW+timedelta(days=3)).isoformat()}
    gate=recheck_gate(learning,'mate',NOW+timedelta(days=7))
    assert not gate['eligible'] and gate['ready_at']==(NOW+timedelta(days=10)).isoformat()
    assert not recheck_gate(learning,'capture',NOW)['eligible']
    learning['cards']['source']['exposure']['2026-10-22']['last_at']='unrecorded'
    assert not recheck_gate(learning,'mate',NOW+timedelta(days=20))['eligible']


def test_real_new_report_preserves_unknown_history_and_next_band(setup):
    c,_,legacy,path=attach(setup)
    s=post(c,'start',{'mode':'targeted','competency':'mate'})
    while s['phase']!='complete':
        row=saved(path)['active']['items'][s['index']]
        if s['phase']=='question':
            for move in row['line'][::2]:
                s=act(c,s,'move',move)
                if s['phase']=='feedback':break
        s=act(c,s,'next')
    result=s['report'];area=result['areas'][0]
    assert area['full_success']==3 and area['app_new_attempts']==3 and area['independent']==0
    status=c.get('/api/journey').json()
    assert status['additional']['mate']['band']==[1200,1800]
    assert not status['rechecks']['mate']['eligible']
    assert legacy['completed_lessons']==['old']
