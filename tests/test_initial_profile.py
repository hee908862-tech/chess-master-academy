import copy
import hashlib
import json
import sqlite3
import pytest
from initial_profile import status,initialize,freeze,collect
from journey_server import DATA_FILE,inventory
from competencies import line_positions
from test_learning import setup
from test_journey import attach,post,act,saved


def complete_chunk(c,s):
    while s['phase']!='complete':
        if s['phase']=='question':s=act(c,s,'skip')
        else:s=act(c,s,'next')
    return s


def test_finite_skip_budget_survives_reload_and_stop_is_not_success(setup):
    c,ns,old,path=attach(setup)
    p=c.get('/api/journey').json()['initial_profile'];assert p['remaining']==48
    assigned=0;areas=set()
    for batch in range(12):
        s=post(c,'start',{'mode':'initial'})
        assert s['total']==(8 if batch<6 else 4) and s['initial_course']
        areas.add(s['question']['competency']);assigned+=s['total']
        if batch==5:assert len(areas)==6
        assert c.post('/api/journey/start',json={'mode':'initial'}).status_code==409
        assert c.post('/api/journey/initial/stop').status_code==409
        complete_chunk(c,s)
        p=c.get('/api/journey').json()['initial_profile']
        assert p['assigned']==assigned and p['valid']==0
    assert p['state']=='held' and p['budget_left']==0
    before=saved(path)
    assert c.post('/api/journey/start',json={'mode':'initial'}).status_code==409
    p=c.post('/api/journey/initial/review').json();assert p['reviewed'] and p['state']=='held'
    assert p['internal_skill']['score'] is None
    after=saved(path);assert before['results']==after['results'] and before['reserved']==after['reserved']
    assert c.post('/api/journey/initial/review').json()==p


def real_rows():
    rows=[];seen=set()
    for area,pool in inventory().items():
        for band in [(600,1200),(1200,1800)]:
            n=0
            for row in pool:
                positions=line_positions(row['fen'],row['line'])
                if band[0]<=row['rating']<band[1] and not seen.intersection(positions):
                    seen.update(positions);n+=1
                    rows.append({**row,'id':area+str(band[0])+str(n),'competency':area,'band':list(band),'app_new':True,'first_attempt':True,'helped':False,'outcome':'completed' if n%2 else 'verified_error','submitted':row['line'][::2]})
                    if n==4:break
    return rows


def report(rows):
    return {'id':'baseline-import','score_version':'skill-index-v1','version':'journey-v5','measurement_scope':'broad_area_execution_v1','competency_version':'competency-v2','corpus_sha256':hashlib.sha256(DATA_FILE.read_bytes()).hexdigest(),'mode':'balanced','items':rows}


def test_completed_and_verified_errors_fill_range_without_rewriting_scores():
    r=report(real_rows());r['old_score']=2900
    state={'results':[r],'active':None};before=copy.deepcopy(r)
    initialize(state,r['corpus_sha256']);p=status(state)
    assert p['state']=='ready' and p['valid']==48 and p['internal_skill']['score']==1501
    freeze(state,'now');state['initial_profile']['reviewed_at']='now'
    baseline=status(state);state['results'].append(report([]))
    assert status(state)==baseline and r==before
    assert len(baseline['sources'])==48 and baseline['baseline_version']=='initial-baseline-v1'


def test_repeats_help_unknown_and_old_versions_never_silently_fill():
    rows=real_rows();rows[0]['outcome']='not_answered';rows[1]['helped']=True;rows[2]['outcome']='unverified_alternative'
    r=report(rows);state={'results':[r,copy.deepcopy(r)],'active':None}
    p=status(state);assert p['valid']==45 and p['remaining']==3
    assert p['excluded']['repeat']==48
    state['results']=[{**r,'version':'journey-v4'}];assert status(state)['valid']==0


def test_initial_gate_exception_preserves_old_cycle_and_active_session(setup):
    c,ns,old,path=attach(setup)
    s=post(c,'start',{'mode':'balanced'});complete_chunk(c,s)
    before=saved(path);cycle=c.get('/api/journey').json()['cycle'];assert not cycle['unlocked']
    s=post(c,'start',{'mode':'initial','competency':'defense'});assert s['question']['competency']=='defense'
    assert c.get('/api/journey').json()['cycle']==cycle
    assert saved(path)['results']==before['results']
    assert c.post('/api/journey/initial/review').status_code==409
    restored=c.get('/api/journey').json()['active'];assert restored['session_id']==s['session_id']


def test_held_course_cannot_reset_or_switch_corpus(setup):
    c,ns,old,path=attach(setup)
    s=post(c,'start',{'mode':'initial'});complete_chunk(c,s)
    p=c.post('/api/journey/initial/stop').json();assert p['state']=='held'
    assert c.post('/api/journey/start',json={'mode':'initial'}).status_code==409
    state=saved(path);state['initial_profile'].pop('baseline');state['initial_profile']['corpus']='other'
    with sqlite3.connect(path) as db:db.execute("UPDATE journey_progress SET state=? WHERE code='A'",(json.dumps(state),))
    assert c.post('/api/journey/start',json={'mode':'initial'}).status_code==409
    assert c.post('/api/journey/initial/review').status_code==409
    assert saved(path)==state


def test_incomplete_blueprint_never_displays_perfect_score_or_mutates_records():
    rows=real_rows()
    for i,row in enumerate(rows):row['outcome']='completed' if i%4==0 else 'not_answered'
    state={'results':[report(rows)],'active':None};original=copy.deepcopy(state['results'])
    initialize(state,state['results'][0]['corpus_sha256']);freeze(state,'now','사용자 중단')
    p=status(state)
    assert p['state']=='held' and p['valid']==12 and p['remaining']==36
    assert p['internal_skill']['score'] is None and p['internal_skill']['unresolved']==36
    assert all(p['performance'][a['id']]['score'] is None for a in p['areas'])
    assert len(p['sources'])==12 and state['results']==original


def seed_prior_observations(path, rows):
    """Only this test's temporary account database receives synthetic history."""
    import chess
    prior=report(rows);prior['mode']='domain'
    reserved=[]
    for row in rows:
        board=chess.Board(row['fen'])
        reserved.append({'puzzle_id':row['puzzle_id'],'fen':board.fen()})
        for move in row['line']:
            board.push_uci(move)
            reserved.append({'puzzle_id':row['puzzle_id'],'fen':board.fen()})
    state={'results':[prior],'active':None,'reserved':reserved}
    with sqlite3.connect(path) as db:
        db.execute('INSERT OR REPLACE INTO journey_progress(code,state) VALUES(?,?)',('A',json.dumps(state)))
    return state


def test_last_feedback_cannot_freeze_and_reviewed_baseline_survives_new_session(setup):
    c,ns,old,path=attach(setup)
    rows=real_rows();missing=rows.pop()
    before=seed_prior_observations(path,rows)
    s=post(c,'start',{'mode':'initial'})
    assert s['total']==1
    item=saved(path)['active']['items'][0]
    assert item['competency']==missing['competency'] and item['band']==missing['band']
    for move in item['line'][::2]:
        s=act(c,s,'move',move)
        if s['phase']=='feedback':break
    assert s['phase']=='feedback' and s['feedback']['complete']
    progress=c.get('/api/journey').json()['initial_profile']
    assert progress['valid']==48 and progress['active'] and not progress['reviewed']
    snapshot=saved(path)
    assert c.post('/api/journey/initial/review').status_code==409
    assert saved(path)==snapshot and 'baseline' not in snapshot['initial_profile']
    done=act(c,s,'next');assert done['phase']=='complete'
    assert 'baseline' not in saved(path)['initial_profile']
    response=c.post('/api/journey/initial/review');assert response.status_code==200
    baseline=copy.deepcopy(saved(path)['initial_profile']['baseline'])
    assert response.json()['reviewed'] and baseline['valid']==48
    assert saved(path)['results'][0]==before['results'][0]
    assert c.post('/api/journey/initial/review').json()==response.json()
    # A later freely selected diagnosis neither replaces nor recalculates the baseline.
    later=post(c,'start',{'mode':'domain','competency':missing['competency']})
    assert saved(path)['initial_profile']['baseline']==baseline
    complete_chunk(c,later)
    assert saved(path)['initial_profile']['baseline']==baseline
    assert c.get('/api/journey').json()['initial_profile']==response.json()


def test_only_missing_band_is_assigned_without_spending_other_slots(setup):
    c,ns,old,path=attach(setup)
    rows=real_rows();area=rows[0]['competency']
    keep=[row for row in rows if not(row['competency']==area and row['band']==[1200,1800])]
    before=seed_prior_observations(path,keep)
    s=post(c,'start',{'mode':'initial','competency':area})
    current=saved(path)
    assert s['total']==4 and all(i['band']==[1200,1800] for i in current['active']['items'])
    assert current['initial_profile']['assigned']==4
    assert current['initial_profile']['assigned_by_area']=={area:4}
    assert current['initial_profile']['maximum']==28
    assert current['results']==before['results']


def test_exhausted_pool_holds_once_without_reservations_or_budget_charge(setup,monkeypatch):
    import journey_server
    c,ns,old,path=attach(setup)
    area=next(iter(inventory()))
    monkeypatch.setattr(journey_server,'inventory',lambda:{area:[]})
    result=post(c,'start',{'mode':'initial','competency':area})
    assert result['phase']=='initial_held'
    state=saved(path)
    assert state['active'] is None and state['reserved']==[] and state['results']==[]
    assert state['initial_profile']['assigned']==0
    assert result['initial_profile']['state']=='held'
    assert c.post('/api/journey/start',json={'mode':'initial','competency':area}).status_code==409
    assert saved(path)==state
    reviewed=c.post('/api/journey/initial/review')
    assert reviewed.status_code==200 and reviewed.json()['reviewed']
    assert reviewed.json()['internal_skill']['score'] is None


def test_old_corpus_history_does_not_advertise_ready_current_course(setup):
    c,ns,old,path=attach(setup)
    state=seed_prior_observations(path,real_rows())
    state['results'][0]['corpus_sha256']='previous-corpus-version'
    with sqlite3.connect(path) as db:
        db.execute("UPDATE journey_progress SET state=? WHERE code='A'",(json.dumps(state),))
    response=c.get('/api/journey');assert response.status_code==200
    preview=response.json()['initial_profile']
    current=hashlib.sha256(DATA_FILE.read_bytes()).hexdigest()
    assert preview['corpus']==current
    assert preview['state']=='not_started' and preview['valid']==0 and preview['remaining']==48
    assert preview['internal_skill']['score'] is None
    assert response.json()['results']==state['results'] and saved(path)==state
    started=post(c,'start',{'mode':'initial'})
    assert started['initial_course'] and started['initial_profile']['corpus']==current
    assert saved(path)['results']==state['results']
