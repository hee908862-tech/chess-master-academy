"""Finite continuation and supplement revisions; temporary SQLite only."""
import copy,json,sqlite3
from initial_profile import initialize,status,freeze,TECHNICAL_REPLACEMENTS
from test_learning import setup
from test_journey import attach,post,act,saved
from test_initial_profile import real_rows,report,seed_prior_observations,complete_chunk


def write(path,state):
    with sqlite3.connect(path) as db:db.execute("UPDATE journey_progress SET state=? WHERE code='A'",(json.dumps(state),))


def test_technical_failures_have_separate_finite_budget_not_error_credit():
    rows=real_rows()[:12]
    for row in rows:
        row['outcome']='unverified_alternative';row['engine_evidence']={'status':'unverified','reason':'engine_failure'}
    rows[2]['engine_evidence']['reason']='engine_busy'
    r=report(rows);r['initial_course']='initial-profile-v1';state={'results':[r],'active':None};initialize(state,r['corpus_sha256'])
    state['initial_profile']['assigned']=72
    view=status(state)
    assert view['valid']==0 and view['technical_failures']==12
    assert view['excluded']['technical_failure']==12
    assert view['maximum']==80 and view['budget_left']==TECHNICAL_REPLACEMENTS
    assert view['state']=='in_progress'
    state['initial_profile']['assigned']=80;assert status(state)['state']=='held'
    rows[0]['engine_evidence']['reason']='insufficient_depth'
    rows[1]['engine_evidence']['reason']='mate_proof_budget'
    assert status(state)['technical_failures']==10
    # Historical stored budget policy is not silently rewritten.
    state['initial_profile'].pop('budget_policy');assert status(state)['maximum']==72


def test_last_answer_does_not_announce_course_ready_before_saved_next():
    rows=real_rows();r=report(rows);state={'results':[], 'active':{**r,'session_id':'active','phase':'feedback'}}
    initialize(state,r['corpus_sha256']);view=status(state)
    assert view['valid']==48 and view['state']=='in_progress' and view['active']
    state['results']=[r];state['active']=None;assert status(state)['state']=='ready'


def test_held_supplement_preserves_frozen_baseline_and_never_repeats(setup):
    c,_,_,path=attach(setup);rows=real_rows();missing=rows[-2:];seed_prior_observations(path,rows[:-2])
    # A historical held 46/48 baseline is not rewritten by GET or supplement.
    state=saved(path);initialize(state,report(rows)['corpus_sha256']);state['initial_profile']['assigned']=26
    freeze(state,'original','정해진 추가 확인 상한에 도달했습니다.');state['initial_profile']['reviewed_at']='original'
    original=copy.deepcopy(state);write(path,state)
    before=c.get('/api/journey').json()['initial_profile'];assert before['valid']==46 and before['state']=='held'
    response=c.post('/api/journey/initial/supplement');assert response.status_code==200,response.text
    view=response.json();assert view['state']=='in_progress' and view['supplement_used']
    assert view['previous_baselines'][0]['baseline_id']==before['baseline_id']
    assert view['previous_baselines'][0]['valid']==46 and view['previous_baselines'][0]['remaining']==2
    after=saved(path);history=after['initial_profile']['history'][0]
    assert history['baseline']==original['initial_profile']['baseline'] and history['reviewed_at']=='original'
    assert after['results']==original['results'] and after['reserved']==original['reserved']
    assert view['budget_left']==2 and view['maximum']==28
    assert c.post('/api/journey/initial/supplement').status_code==409
    session=post(c,'start',{'mode':'initial'});assert session['total']==2
    assert all(i['competency']==missing[0]['competency'] for i in saved(path)['active']['items'])
    complete_chunk(c,session);assert c.get('/api/journey').json()['initial_profile']['state']=='held'
    assert c.post('/api/journey/initial/supplement').status_code==409
    assert saved(path)['initial_profile']['history'][0]==history


def test_supplement_without_supply_or_with_active_session_never_mutates(setup,monkeypatch):
    import journey_server
    c,_,_,path=attach(setup);s=post(c,'start',{'mode':'initial'});before=saved(path)
    assert c.post('/api/journey/initial/supplement').status_code==409
    assert saved(path)==before
    complete_chunk(c,s);assert c.post('/api/journey/initial/stop').status_code==200
    before=saved(path);monkeypatch.setattr(journey_server,'inventory',lambda:{})
    response=c.post('/api/journey/initial/supplement');assert response.status_code==409
    assert '미노출 문제가 없습니다' in response.text and saved(path)==before


def test_automatic_next_skips_empty_area_but_keeps_its_missing_observations(setup,monkeypatch):
    import journey_server
    c,_,_,path=attach(setup);pools=copy.deepcopy(journey_server.inventory())
    first=next(iter(pools));pools[first]=[]
    monkeypatch.setattr(journey_server,'inventory',lambda:pools)
    s=post(c,'start',{'mode':'initial'})
    assert s['question']['competency']!=first
    p=c.get('/api/journey').json()['initial_profile']
    assert p['state']=='in_progress' and next(a for a in p['areas'] if a['id']==first)['missing']==8


def test_mixed_answer_policy_keeps_valid_history_but_disables_exact_comparison():
    rows=real_rows();a=report(rows[:24]);b=report(rows[24:]);b['id']='second';b['answer_policy']='goal-alternatives-v1'
    state={'results':[a,b],'active':None};before=copy.deepcopy(state)
    p=status(state)
    assert p['valid']==48 and p['mixed_answer_policy'] and not p['comparison_allowed']
    assert {s['answer_policy'] for s in p['sources']}=={'reference-line-v1','goal-alternatives-v1'}
    assert state==before
    assert all(not a['comparable'] for a in p['performance'].values())
