"""Actual board re-entry renews retention exposure; dashboard/history reads do not."""
import json
import sqlite3
from datetime import datetime,timedelta,timezone
import pytest
import learning_server as learning
from journey_evidence import recheck_gate
from test_learning import setup,post,action,solution,path_request

@pytest.mark.parametrize('entry',['same_start','same_resume','paused_resume','path_restore','board_reload'])
def test_board_reentry_restarts_seven_days_without_erasing_help(setup,monkeypatch,entry):
    clock=datetime(2026,10,1,12,tzinfo=timezone.utc)
    monkeypatch.setattr(learning,'now',lambda:clock)
    c,_,_,db=setup
    def read():
        with sqlite3.connect(db) as conn:return json.loads(conn.execute('SELECT state FROM learning_progress').fetchone()[0])
    def write(state):
        with sqlite3.connect(db) as conn:conn.execute('UPDATE learning_progress SET state=?',(json.dumps(state),))
    s=post(c,'start',{'fresh':True,'mode':'verify'})
    action(c,s,'move',solution(s))
    state=read();cid=s['card_id'];category=state['cards'][cid]['category']
    state['cards'][cid]['diagnosis']={'report_id':'saved-diagnosis','item_id':'saved-item'}
    state['cards'][cid]['due']=clock.isoformat()
    # Seed an existing qualifying full-line attempt; success is not a new gate requirement.
    state['attempts'][0].update(assessment_scope='full_line',selection={'source_card':cid},success=False)
    write(state)
    s=post(c,'start',{'card_id':cid})
    if entry=='path_restore':s=path_request(c)['active']
    s=action(c,s,'hint');expected_help=s['hint_level']
    b=None
    if entry in ('paused_resume','path_restore'):b=post(c,'start',{'fresh':True})
    clock+=timedelta(days=6)
    assert not recheck_gate(read(),category,clock)['eligible']
    clock+=timedelta(days=13)
    assert recheck_gate(read(),category,clock)['eligible']
    before=read()
    c.get('/api/learning/dashboard');c.get('/api/learning/dashboard?offset=50')
    assert read()==before
    if entry=='same_start':restored=post(c,'start',{'card_id':cid})
    elif entry=='same_resume':restored=post(c,'resume',{'session_id':s['session_id']})
    elif entry=='paused_resume':restored=post(c,'resume',{'session_id':s['session_id'],'active_id':b['session_id'],'active_revision':b['revision']})
    elif entry=='path_restore':restored=path_request(c)['active']
    else:
        assert c.post('/api/learning/exposure',json={'session_id':s['session_id'],'active_revision':s['revision']}).status_code==200
        restored=c.get('/api/learning/dashboard').json()['active']
    assert restored['hint_level']==expected_help
    gate=recheck_gate(read(),category,clock)
    assert not gate['eligible'] and gate['ready_at']==(clock+timedelta(days=7)).isoformat()
    assert read()['cards'][cid]['exposure']['2026-10-01']==before['cards'][cid]['exposure']['2026-10-01']
    clock+=timedelta(days=7)
    assert recheck_gate(read(),category,clock)['eligible']
