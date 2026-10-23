"""Owned local SQLite provenance. Completed path states are explicit fixtures."""
import copy,json,sqlite3
from test_learning import setup
from test_journey import attach,saved
from test_initial_profile import real_rows,seed_prior_observations


def read_learning(path):
    with sqlite3.connect(path) as db:return json.loads(db.execute('SELECT state FROM learning_progress WHERE code=?',('A',)).fetchone()[0])


def save_learning(path,state):
    with sqlite3.connect(path) as db:db.execute('UPDATE learning_progress SET state=? WHERE code=?',(json.dumps(state),'A'))


def baseline(setup):
    j,_,_,path=attach(setup);seed_prior_observations(path,real_rows())
    p=j.post('/api/journey/initial/review').json()
    return j,p,{**p['recommended_source'],'initial_baseline_id':p['baseline_id']}


def test_old_completed_path_does_not_bind_and_current_binding_is_idempotent(setup):
    c,_,_,path=setup;j,p,request=baseline(setup)
    history=copy.deepcopy(saved(path))
    old=c.post('/api/learning/from-diagnosis',json=p['recommended_source']);assert old.status_code==200
    state=read_learning(path);old_id=state['path']['id'];state['path']['done']=True;state['active']['done']=True
    save_learning(path,state)
    assert c.get('/api/learning/dashboard').json()['path']['initial_baseline_id'] is None
    current=c.post('/api/learning/from-diagnosis',json=request);assert current.status_code==200
    assert current.json()['path']['id']!=old_id
    assert current.json()['path']['initial_baseline_id']==p['baseline_id']
    state=read_learning(path);state['path']['done']=True;state['path']['current']=4;state['active']['done']=True
    save_learning(path,state);before=copy.deepcopy(state)
    repeated=c.post('/api/learning/from-diagnosis',json=request);assert repeated.status_code==200
    assert repeated.json()['path']['done'] and read_learning(path)==before
    active_conflict=copy.deepcopy(before);active_conflict['active']['done']=False;active_conflict['active']['path_id']='other-path'
    save_learning(path,active_conflict)
    assert c.post('/api/learning/from-diagnosis',json=request).status_code==409
    assert read_learning(path)==active_conflict
    assert saved(path)==history
    assert j.get('/api/journey').json()['initial_profile']['baseline_id']==p['baseline_id']


def test_prior_unfinished_path_and_forged_binding_preserve_records(setup):
    c,_,_,path=setup;j,p,request=baseline(setup)
    other=next(s for s in p['sources'] if s['item_id']!=request['item_id'])
    assert c.post('/api/learning/from-diagnosis',json={k:other[k] for k in ('report_id','item_id')}).status_code==200
    before=read_learning(path)
    assert c.post('/api/learning/from-diagnosis',json=request).status_code==409
    assert c.post('/api/learning/from-diagnosis',json={**request,'initial_baseline_id':'wrong'}).status_code==409
    assert read_learning(path)==before
    assert c.post('/api/learning/from-diagnosis',json=request,headers={'Authorization':'B'}).status_code in (404,409)
    assert read_learning(path)==before


def test_same_source_unfinished_path_requires_explicit_validated_link(setup):
    c,_,_,path=setup;j,p,request=baseline(setup)
    assert c.post('/api/learning/from-diagnosis',json=p['recommended_source']).status_code==200
    before=read_learning(path)
    r=c.post('/api/learning/from-diagnosis',json=request)
    assert r.status_code==200 and r.json()['path']['initial_baseline_id']==p['baseline_id']
    after=read_learning(path);expected={**before['path'],'initial_baseline_id':p['baseline_id']}
    assert after['path']==expected and after['active']==before['active'] and after['attempts']==before['attempts']
    after['path']['initial_baseline_id']='other-baseline';save_learning(path,after)
    assert c.post('/api/learning/from-diagnosis',json=request).status_code==409
    assert read_learning(path)==after
