"""Real corpus, SQLite, restart and concurrent-write diagnostic contracts."""
import copy
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import chess
from fastapi import FastAPI
from fastapi.testclient import TestClient
import journey_server as journey
from test_learning import setup


def attach(setup):
    _,ns,legacy,path=setup
    app=FastAPI();journey.attach_journey(app,ns)
    return TestClient(app,headers={'Authorization':'A'}),ns,legacy,path


def post(c,path,body):
    r=c.post('/api/journey/'+path,json=body); assert r.status_code==200,r.text
    return r.json()


def act(c,s,action,move=None):
    return post(c,'action',{'session_id':s['session_id'],'revision':s['revision'],'action':action,'move':move})


def saved(path):
    with sqlite3.connect(path) as db:
        return json.loads(db.execute("SELECT state FROM journey_progress WHERE code='A'").fetchone()[0])


def test_basic_snapshots_hidden_answers_restart_and_atomic_write(setup):
    c,ns,old,path=attach(setup); before=copy.deepcopy(old)
    s=post(c,'start',{}); snapshot=saved(path)['active']['items']
    assert s['total']==12 and len({journey.key(i['fen']) for i in snapshot})==12
    assert set(i['competency'] for i in snapshot)==set(journey.inventory())
    assert 'line' not in s['question'] and 'expected' not in s['question']
    app=FastAPI();journey.attach_journey(app,ns)
    restored=TestClient(app,headers={'Authorization':'A'})
    assert restored.get('/api/journey').json()['active']==s
    assert c.post('/api/journey/start',json={}).status_code==409
    assert c.get('/api/journey',headers={'Authorization':'B'}).json()['active'] is None
    body={'session_id':s['session_id'],'revision':0,'action':'move','move':snapshot[0]['line'][0]}
    with ThreadPoolExecutor(max_workers=3) as pool:
        statuses=list(pool.map(lambda _:c.post('/api/journey/action',json=body).status_code,range(3)))
    assert sorted(statuses)==[200,409,409]
    assert len(saved(path)['active']['items'][0]['responses'])==1
    assert old==before


def test_multi_ply_partial_skip_full_report_and_bridge(setup):
    c,ns,old,path=attach(setup)
    s=post(c,'start',{'mode':'targeted','competency':'calculation'})
    source=saved(path)['active']['items'][0]
    s=act(c,s,'move',source['line'][0])
    assert s['phase']=='question' and s['question']['ply']==1
    assert s['question']['opponent_last_move']==source['line'][1]
    s=act(c,s,'skip');assert s['feedback']['first_correct'] and not s['feedback']['complete']
    assert s['question']['legal']==[]
    assert c.post('/api/journey/action',json={'session_id':s['session_id'],'revision':s['revision'],'action':'move','move':source['line'][2]}).status_code==409
    s=act(c,s,'next')
    while s['phase']!='complete':
        row=saved(path)['active']['items'][s['index']]
        for uci in row['line'][::2]:
            s=act(c,s,'move',uci)
            if s['phase']=='feedback': break
        assert s['feedback']['complete']
        s=act(c,s,'next')
    report=s['report']; assert report['areas'][1]['partial']==1
    assert all(a['independent']==0 for a in report['areas']) # old completed lesson is uncertain exposure
    assert ns['journey_report']('A',report['id'])['items'][0]['line']==source['line']
    assert c.get('/api/journey').json()['active'] is None
    training=setup[0].post('/api/learning/from-diagnosis',json={'report_id':report['id'],'item_id':source['id']})
    assert training.status_code==200,training.text
    assert training.json()['diagnosis']['correct_plies']==1


def test_unmeasured_no_overwrite_and_unverified_alternative(setup):
    c,ns,old,path=attach(setup);old.clear()
    assert c.post('/api/journey/start',json={'mode':'targeted','competency':'strategy'}).status_code==409
    s=post(c,'start',{'mode':'targeted','competency':'calculation'})
    row=saved(path)['active']['items'][0]
    wrong=next(m for m in s['question']['legal'] if m!=row['line'][0])
    s=act(c,s,'move',wrong)
    assert '미검증' in s['feedback']['reason'] and not s['feedback']['complete']
    assert saved(path)['active']['items'][0]['responses'][0]['move']==wrong
    while s['phase']!='complete':
        if s['phase']=='question':s=act(c,s,'skip')
        s=act(c,s,'next')
    assert s['report']['areas'][1]['independent']==1
    before={i['puzzle_id'] for i in s['report']['items']}
    nxt=post(c,'start',{'mode':'targeted','competency':'calculation'})
    assert not before.intersection(i['puzzle_id'] for i in saved(path)['active']['items'])


def test_recheck_delay_and_learning_positions_excluded(setup,monkeypatch):
    c,ns,old,path=attach(setup)
    request={'mode':'recheck','competency':'mate'}
    assert c.post('/api/journey/start',json=request).status_code==409
    date=journey.now()
    pool=journey.inventory()['mate']; card=pool[0]
    learning={'cards':{'x':{'fen':card['fen'],'puzzle_id':card['puzzle_id'],'diagnosis':{'report_id':'prior'},'category':'mate'}},'attempts':[{'at':date.isoformat(),'selection':{'source_card':'x'},'mode':'verify','fresh':True,'helped':False,'assessment_scope':'full_line','category':'mate'}]}
    with sqlite3.connect(path) as db:
        db.execute('INSERT INTO learning_progress(code,state) VALUES(?,?)',('A',json.dumps(learning)))
    assert c.post('/api/journey/start',json=request).status_code==409
    monkeypatch.setattr(journey,'now',lambda:date+timedelta(days=8))
    # Even an unfinished recent hint/exposure resets the gap, without a new attempt.
    learning['cards']['x']['exposure']={date.date().isoformat():{'last_at':(date+timedelta(days=7)).isoformat(),'hints':1}}
    with sqlite3.connect(path) as db:
        db.execute('UPDATE learning_progress SET state=? WHERE code=?',(json.dumps(learning),'A'))
    assert c.post('/api/journey/start',json=request).status_code==409
    monkeypatch.setattr(journey,'now',lambda:date+timedelta(days=15))
    s=post(c,'start',request)
    assert all(journey.key(i['fen'])!=journey.key(card['fen']) for i in saved(path)['active']['items'])
    assert s['total']==3


def test_promotion_and_actual_mate_explanation(setup,monkeypatch):
    # Legal underpromotion mate from the original full-line contract.
    c,ns,old,path=attach(setup)
    puzzle=next(p for p in journey.inventory()['promotion'] if chess.Move.from_uci(p['line'][0]).promotion and len(p['line'])==1 and chess.Board(p['fen']).is_valid() and 600<=p['rating']<1800)
    monkeypatch.setattr(journey,'inventory',lambda:{'promotion':[puzzle]})
    s=post(c,'start',{'mode':'targeted','competency':'promotion'})
    s=act(c,s,'move',puzzle['line'][0]);assert s['feedback']['complete']
    assert s['feedback']['continuation'][0]['move']==puzzle['line'][0]
    b=chess.Board(s['feedback']['fen'])
    if b.is_checkmate(): assert s['feedback']['mate_explanation']['legal_replies']==0


def test_cross_module_concurrent_reservation_and_continuation_exclusion(setup,monkeypatch):
    import learning_server
    c,ns,old,path=attach(setup);old.clear()
    row=next(p for p in journey.inventory()['calculation'] if 600<=p['rating']<1200)
    monkeypatch.setattr(journey,'inventory',lambda:{'calculation':[row]})
    monkeypatch.setattr(learning_server,'LIB',{row['puzzle_id']:journey.LIB[row['puzzle_id']]})
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(c.post,'/api/journey/start',json={}),pool.submit(setup[0].post,'/api/learning/start',json={'fresh':True})]
        responses=[f.result() for f in futures]
    assert sorted(r.status_code for r in responses)==[200,409]
    if responses[0].status_code==200:
        b=chess.Board(row['fen'])
        for uci in row['line']:
            b.push_uci(uci)
            assert journey.key(b.fen()) in ns['journey_positions']('A')
    else:
        assert c.post('/api/journey/start',json={}).status_code==409


def test_saved_line_survives_corpus_change(setup,monkeypatch):
    c,ns,old,path=attach(setup)
    s=post(c,'start',{'mode':'targeted','competency':'calculation'})
    row=saved(path)['active']['items'][0]
    monkeypatch.setattr(journey,'LIB',{})
    for uci in row['line'][::2]:
        s=act(c,s,'move',uci)
    assert s['phase']=='feedback' and s['feedback']['complete']
    assert s['feedback']['correct_plies']==len(row['line'][::2])
