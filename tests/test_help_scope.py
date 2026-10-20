import json
import sqlite3
import chess
import chess.engine
from test_learning import setup,post,action,solution


def test_current_help_separate_from_prior_card_exposure(setup):
    c,_,_,_=setup
    s=post(c,'start',{'fresh':True});s=action(c,s,'hint');first=action(c,s,'move',solution(s))
    assert first['outcome']['current_helped'] is True
    s=post(c,'start',{'card_id':s['card_id']});done=action(c,s,'move',solution(s))
    a=done['outcome']
    assert a['current_helped'] is False and a['current_hint_level']==0
    assert a['prior_helped'] and a['helped'] and a['independent_kind'] is None
    assert a['status']=='hinted_success'


def test_situation_uses_same_exposure_but_not_current_hint(setup,monkeypatch,tmp_path):
    c,ns,_,db=setup
    engine=tmp_path/'fake-engine';engine.touch();ns['STOCKFISH_PATH']=str(engine)
    class Engine:
        def analyse(self,b,limit):return {'score':chess.engine.PovScore(chess.engine.Cp(0),chess.WHITE),'pv':[next(iter(b.legal_moves))]}
        def configure(self,*a):pass
        def quit(self):pass
    monkeypatch.setattr(chess.engine.SimpleEngine,'popen_uci',lambda *a,**k:Engine())
    s=post(c,'start',{'fresh':True});s=action(c,s,'hint')
    with sqlite3.connect(db) as conn:
        state=json.loads(conn.execute('SELECT state FROM learning_progress').fetchone()[0]);state['cards'][s['card_id']].update(fen=chess.STARTING_FEN,line=['e2e4'],prior=None)
        conn.execute('UPDATE learning_progress SET state=?',(json.dumps(state),))
    s=post(c,'start',{'card_id':s['card_id'],'mode':'situation_practice'})
    for _ in range(6):
        s=action(c,s,'move',s['legal'][0])
        if s['done']:break
    assert s['done'] and s['outcome']['success']
    assert not s['outcome']['current_helped'] and s['outcome']['prior_helped']
    assert s['outcome']['completion_basis']=='evaluation_maintenance'
    assert s['outcome']['independent_kind'] is None


def test_dashboard_read_compatibility_preserves_stored_json(setup):
    c,_,_,db=setup;s=post(c,'start',{'fresh':True})
    with sqlite3.connect(db) as conn:
        state=json.loads(conn.execute('SELECT state FROM learning_progress').fetchone()[0]);state['cards'][s['card_id']].pop('tags');raw=json.dumps(state)
        conn.execute('UPDATE learning_progress SET state=?',(raw,))
    assert c.get('/api/learning/dashboard').json()['cards'][0]['tags']
    with sqlite3.connect(db) as conn:assert conn.execute('SELECT state FROM learning_progress').fetchone()[0]==raw


def test_card_pages_preserve_history_and_due_count(setup):
    import copy
    c,_,_,db=setup;s=post(c,'start',{'fresh':True})
    with sqlite3.connect(db) as conn:
        state=json.loads(conn.execute('SELECT state FROM learning_progress').fetchone()[0]);card=state['cards'][s['card_id']]
        for i in range(62):
            clone=copy.deepcopy(card);clone['id']='archived-'+str(i);state['cards'][clone['id']]=clone
        raw=json.dumps(state);conn.execute('UPDATE learning_progress SET state=?',(raw,))
    first=c.get('/api/learning/dashboard').json();second=c.get('/api/learning/dashboard?offset=50').json()
    assert len(first['cards'])==50 and len(second['cards'])==13
    assert first['cards_total']==first['due_count']==63 and len(first['due'])==50
    assert first['cards_next']==50 and second['cards_next'] is None
    assert len({x['id'] for x in first['cards']+second['cards']})==63
    with sqlite3.connect(db) as conn:assert conn.execute('SELECT state FROM learning_progress').fetchone()[0]==raw
