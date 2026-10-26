import copy
import pytest
from movement_content import BY_ID
from test_movement import movement,start,save
from test_onboarding import api
from test_relationship_lessons import act


def retry(c,s,**extra):
    return c.post('/api/movement/start',json=dict(action='restart',unit_id=s['active']['unit_id'],revision=s['revision'],request_id='retry-current-practice',relationship_flow=True,retry_practice=True,**extra))


def test_current_retry_archives_moves_success_and_preserves_other_state(movement):
    c,server=movement
    s=start(c,unit='rules-shield-piece')
    s=save(c,s,['d2d4'])
    old=copy.deepcopy(dict(server.get_state('INTRO-QA')))
    result=retry(c,s);assert result.status_code==200,result.text
    after=result.json();row=after['active']
    assert row['session_id']!=s['active']['session_id']
    assert row['moves']==[] and not row['done'] and row['result'] is None
    assert row['teaching']['phase']=='independent'
    assert row['fen']==BY_ID[row['unit_id']]['fen']
    assert after['summary']['completed']==s['summary']['completed']
    saved=copy.deepcopy(dict(server.get_state('INTRO-QA')))
    assert saved['movement_v1']['history'][-1]['moves']==['d2d4']
    assert saved['movement_v1']['history'][-1]['done']
    assert saved['movement_v1']['history'][-1]['practice_result']==s['active']['practice_result']
    saved.pop('movement_v1');old.pop('movement_v1');assert saved==old
    assert retry(c,s).json()==after # Same request id does not create another run.


@pytest.mark.parametrize('phase',['explain','guided'])
def test_retry_cannot_bypass_learning_phase(movement,phase):
    c,server=movement;s=start(c,unit='rules-shield-piece',independent=False)
    if phase=='guided':s=act(c,s,'guided')
    before=copy.deepcopy(dict(server.get_state('INTRO-QA')))
    assert retry(c,s).status_code==409
    assert dict(server.get_state('INTRO-QA'))==before


def test_wrong_attempt_and_stale_retry_cannot_overwrite_progress(movement):
    c,server=movement;s=start(c,unit='rules-shield-piece');old=copy.deepcopy(s)
    s=save(c,s,['d2d3'],mistakes=2)
    assert retry(c,old).status_code==409
    r=retry(c,s);assert r.status_code==200
    stored=server.get_state('INTRO-QA')['movement_v1']
    assert stored['history'][-1]['moves']==['d2d3']
    assert stored['history'][-1]['mistakes']==2
    assert r.json()['active']['teaching']['phase']=='independent'


def test_retry_does_not_turn_answer_exposure_into_unaided_success(movement):
    c,_=movement;s=start(c,unit='rules-shield-piece')
    demo=c.post('/api/movement/demo',json={'unit_id':s['active']['unit_id'],'session_id':s['active']['session_id'],'revision':s['revision']})
    assert demo.status_code==200
    s=demo.json()['dashboard']
    assert s['active']['teaching']['independent_helped']
    r=retry(c,s);assert r.status_code==200
    s=r.json()
    assert s['active']['teaching']['independent_helped']
    s=save(c,s,['d2d4'])
    assert s['active']['practice_result']=='assisted_application'
