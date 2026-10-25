import copy
import json
import sqlite3
import pytest
from growth_model import area_score,credit_cycle,cycle_status
from test_learning import setup
from test_journey import attach,post,act,saved


def sample(outcome='completed',band=(600,1200),correct=1):
    return {'app_new':True,'helped':False,'outcome':outcome,'band':list(band),'correct_plies':correct,'total_plies':1}


def test_score_missing_help_uncertainty_and_equal_band_weight():
    assert area_score([{**sample(),'first_attempt':False}])['observed']==0
    assert area_score([{**sample(band=band),'total_plies':3} for band in [(600,1200),(1200,1800)]])['score']==100
    assert area_score([sample('not_answered')])['score'] is None
    assert area_score([sample('unverified_alternative')])['score'] is None
    assert area_score([{**sample(),'helped':True}])['score'] is None
    rows=[sample(),sample(),sample('verified_error',(1200,1800),0),sample('verified_error',(1200,1800),0)]
    score=area_score(rows)
    assert score['score']==50 and score['comparable'] and score['band_counts']==[2,2]
    assert area_score(rows+[sample()]*10)['score']==50
    assert area_score([sample(),sample(band=(1200,1800))])['comparable'] is False
    assert area_score([sample('verified_error',band,0) for band in [(600,1200),(1200,1800)]])['score']==0


def finish_diagnosis(c,s,db,solve=False):
    while s['phase']!='complete':
        if solve:
            row=saved(db)['active']['items'][s['index']]
            for move in row['line'][::2]:
                s=act(c,s,'move',move)
                if s['phase']=='feedback':break
        else:s=act(c,s,'skip')
        s=act(c,s,'next')
    return s['report']


def test_balanced_24_snapshots_cycle_unlock_and_new_positions(setup):
    c,ns,legacy,db=attach(setup);legacy.clear()
    s=post(c,'start',{'mode':'balanced'})
    rows=saved(db)['active']['items'];assert len(rows)==24
    assert s['question']['competency'] and 'rating' not in s['question'] and 'total_plies' not in s['question']
    assert s['version']=='journey-v5' and s['measurement_scope']=='broad_area_execution_v1'
    from collections import Counter
    assert set(Counter((r['competency'],tuple(r['band'])) for r in rows).values())=={2}
    report=finish_diagnosis(c,s,db)
    assert all(a['performance']['score'] is None for a in report['areas'])
    assert not report['insights']['strengths'] and not report['insights']['priorities']
    assert len(report['training_plan'])==5
    for mode in ('balanced','quick','basic'):
        assert c.post('/api/journey/start',json={'mode':mode}).status_code==409
    learner=setup[0]
    for task in report['training_plan']:
        body={'report_id':report['id'],'item_id':task['id']}
        start=learner.post('/api/learning/cycle/start',json=body);assert start.status_code==200,start.text
        t=start.json();assert learner.post('/api/learning/cycle/start',json=body).json()['session_id']==t['session_id']
        action={'session_id':t['session_id'],'revision':t['revision'],'action':'hint'}
        t=learner.post('/api/learning/action',json=action).json()
        with sqlite3.connect(db) as conn:
            state=json.loads(conn.execute('SELECT state FROM learning_progress').fetchone()[0]);line=state['cards'][t['card_id']]['line']
        for move in line[::2]:
            action={'session_id':t['session_id'],'revision':t['revision'],'action':'move','move':move}
            response=learner.post('/api/learning/action',json=action);assert response.status_code==200,response.text;t=response.json()
            if t['done']:break
        assert t['done']
        assert learner.post('/api/learning/action',json=action).status_code==409
        assert learner.post('/api/learning/cycle/start',json=body).status_code==409
    status=c.get('/api/journey').json();assert status['cycle']['completed']==5 and status['cycle']['unlocked']
    assert all(t['completion']['helped'] for t in status['cycle']['tasks'])
    for _ in range(2):assert c.post('/api/journey/start',json={'mode':'basic'}).status_code==409
    before={r['puzzle_id'] for r in rows}
    new=post(c,'start',{'mode':'balanced'})
    assert not before.intersection(r['puzzle_id'] for r in saved(db)['active']['items'])
    # Starting a new assessment keeps prior result and earned gate until completion commits.
    assert c.get('/api/journey').json()['latest']['id']==report['id']
    assert c.get('/api/journey').json()['cycle']['unlocked']
    newer=finish_diagnosis(c,new,db)
    assert c.get('/api/journey').json()['cycle']['completed']==0
    assert learner.post('/api/learning/cycle/start',json=body).status_code==409
    assert newer['snapshot']['mode']=='balanced'


def test_credit_requires_actual_assigned_success_and_unique_position():
    state={'cycles':{'r':{'cards':{'1':'a','2':'b'},'completed':{}}}}
    session={'id':'s','growth_task':{'report_id':'r','task_id':'1'},'card_id':'a','turns':0}
    attempt={'success':True,'assessment_scope':'full_line','position':'p','at':'today','helped':False}
    credit_cycle(state,session,attempt);assert not state['cycles']['r']['completed']
    session['turns']=1;credit_cycle(state,session,{**attempt,'success':None});assert not state['cycles']['r']['completed']
    credit_cycle(state,session,attempt);credit_cycle(state,session,attempt)
    session.update(card_id='b',growth_task={'report_id':'r','task_id':'2'});credit_cycle(state,session,attempt)
    assert len(state['cycles']['r']['completed'])==1


def test_quick_and_balanced_not_comparable_old_records_untouched(setup):
    c,ns,legacy,db=attach(setup)
    s=post(c,'start',{'mode':'basic'});old=finish_diagnosis(c,s,db);assert 'snapshot' not in old
    s=post(c,'start',{'mode':'quick'});assert s['total']==12
    report=finish_diagnosis(c,s,db,solve=True)
    assert report['snapshot']['mode']=='quick'
    assert all(not a['performance']['comparable'] for a in report['areas'])
    assert c.get('/api/journey').json()['results'][0]==old
    assert report['insights']['strengths']


def test_balanced_scores_and_higher_followup_preserve_cycle(setup):
    c,ns,legacy,db=attach(setup);legacy.clear()
    s=post(c,'start',{'mode':'balanced'});r=finish_diagnosis(c,s,db,solve=True)
    assert all(a['performance']['score']==3000 and a['performance']['comparable'] for a in r['areas'] if a['count'])
    assert r['insights']['balanced'] and not r['insights']['priorities']
    extra=post(c,'start',{'mode':'targeted','competency':'mate'})
    assert all(row['band']==[1800,2400] or tuple(row['band'])==(1800,2400) for row in saved(db)['active']['items'])
    extra_report=finish_diagnosis(c,extra,db)
    status=c.get('/api/journey').json()
    assert status['latest']['id']==extra_report['id'] and status['cycle_report']['id']==r['id'] and status['cycle']['completed']==0


def test_insufficient_balanced_pool_preserves_saved_state(setup,monkeypatch):
    import journey_server as journey
    c,ns,legacy,db=attach(setup);legacy.clear()
    finish_diagnosis(c,post(c,'start',{'mode':'basic'}),db)
    before=saved(db)
    monkeypatch.setattr(journey,'inventory',lambda:{'mate':[]})
    assert c.post('/api/journey/start',json={'mode':'balanced'}).status_code==409
    assert saved(db)==before


def test_engine_evidence_is_optional_bounded_and_releases_slot(monkeypatch,tmp_path):
    import chess
    import chess.engine
    import growth_model as growth
    path=tmp_path/'engine';path.touch()
    class Engine:
        id={'name':'controlled'}
        def configure(self,settings):pass
        def analyse(self,board,limit):
            return {'score':chess.engine.PovScore(chess.engine.Cp(300 if not board.move_stack else 0),chess.WHITE),'depth':12}
        def quit(self):pass
    monkeypatch.setattr(chess.engine.SimpleEngine,'popen_uci',lambda *a,**k:Engine())
    assert growth.verify_loss('invalid','e2e4',str(path))['reason']=='engine_failure'
    evidence=growth.verify_loss(chess.STARTING_FEN,'e2e4',str(path))
    assert evidence['loss_cp']==300 and evidence['depth']==12
    Engine.analyse=lambda *a:{'score':chess.engine.PovScore(chess.engine.Mate(1),chess.WHITE),'depth':12}
    assert growth.verify_loss(chess.STARTING_FEN,'e2e4',str(path))['status']=='unverified'
    Engine.analyse=lambda *a:{'score':chess.engine.PovScore(chess.engine.Cp(0),chess.WHITE),'depth':4}
    assert growth.verify_loss(chess.STARTING_FEN,'e2e4',str(path))['status']=='unverified'
    assert growth.verify_loss(chess.STARTING_FEN,'e2e4',str(tmp_path/'absent'))['reason']=='engine_unavailable'


@pytest.mark.parametrize('loss,expected',[(300,'verified_error'),(50,'unverified_alternative')])
def test_alternative_move_uses_only_verified_large_loss(setup,monkeypatch,loss,expected):
    import chess
    import journey_server as journey
    c,ns,legacy,db=attach(setup);legacy.clear()
    s=post(c,'start',{'mode':'balanced'})
    candidates=[]
    for index,row in enumerate(saved(db)['active']['items']):
        # This contract exercises CP-loss evidence, not the separate exact mate proof.
        if any(tag.startswith('mateIn') for tag in row.get('tags',[])):continue
        board=chess.Board(row['fen']);candidates=[]
        for move in board.legal_moves:
            if move.uci()==row['line'][0]:continue
            trial=board.copy();trial.push(move)
            if not trial.is_game_over():candidates.append(move.uci())
        if candidates:break
    assert candidates
    for _ in range(index):s=act(c,act(c,s,'skip'),'next')
    calls=[]
    def verify(*args):
        calls.append(args)
        return {'status':'verified_error' if loss>=200 else 'unverified','loss_cp':loss,'depth':12,'engine':'controlled','policy':'test'}
    monkeypatch.setattr(journey,'verify_loss',verify)
    result=act(c,s,'move',candidates[0])
    assert result['feedback']['outcome']==expected
    assert len(calls)==1 and calls[0][:2]==(row['fen'],candidates[0])
    stored=saved(db)['active']['items'][index]
    assert stored['engine_evidence']['loss_cp']==loss
