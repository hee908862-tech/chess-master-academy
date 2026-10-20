"""Course switching preserves the entire session and rejects obsolete replacement tokens."""
import copy
from test_qa_behavior import api


def test_course_resume_after_switch_and_stale_token(api):
    c, state = api
    a = c.post('/api/v9/course/start',json={'theme':'mateIn1','level':'입문'})
    assert a.status_code==200,a.text
    c.get('/api/v9/course/hint')
    before=copy.deepcopy(state['v9_course'])
    saved=c.get('/api/v9/session/course').json()
    assert saved['session_id']==before['session_id'] and saved['replace_token']
    assert c.post('/api/v9/course/start',json={'theme':'fork','level':'중급'}).status_code==409
    assert state['v9_course']==before
    b=c.post('/api/v9/course/start',json={'theme':'fork','level':'중급','replace_token':saved['replace_token']})
    assert b.status_code==200,b.text
    assert state['v9_course_paused']==[before]
    bstate=copy.deepcopy(state['v9_course'])
    assert c.post('/api/v9/course/resume/'+before['session_id'],json={'theme':'mateIn1','level':'입문','replace_token':saved['replace_token']}).status_code==409
    current=c.get('/api/v9/session/course').json()
    restored=c.post('/api/v9/course/resume/'+before['session_id'],json={'theme':'mateIn1','level':'입문','replace_token':current['replace_token']})
    assert restored.status_code==200,restored.text
    resumed=state['v9_course']
    assert resumed['session_id']!=before['session_id']
    assert {k:v for k,v in resumed.items() if k!='session_id'}=={k:v for k,v in before.items() if k!='session_id'}
    assert state['v9_course_paused']==[bstate]
    assert c.post('/api/v9/course/move',json={'move':'a1a2','session_id':before['session_id']}).status_code==409
    assert c.get('/api/v9/course/hint',params={'session_id':before['session_id']}).status_code==409
    assert c.post('/api/v9/course/next',json={'session_id':before['session_id']}).status_code==409
    assert not state.get('v9_course_history') and not state.get('puzzle_results')
