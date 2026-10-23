"""Owned review transactions; only isolated synthetic histories are written."""
import copy
import threading
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import attempt_review
from test_learning import setup

FEN='7k/8/5K2/8/6Q1/8/8/8 w - - 0 1'


def make():
    item={'id':'item','puzzle_id':'fixture','fen':FEN,'line':['g4g7'],'tags':['mateIn1'],
          'submitted':['g4g3'],'correct_plies':0,'outcome':'unverified_alternative',
          'competency':'mate','band':[600,1200],'rating':900,'app_new':True,
          'first_attempt':True,'independent':True}
    report={'id':'report','items':[item],'answer_policy':'reference-line-v1'}
    states={'A':{'results':[report],'active':{'untouched':True},'initial_profile':{'baseline':{'score':3000}}},
            'B':{'results':[],'active':None}}
    clock=[datetime(2026,1,1,tzinfo=timezone.utc)];lock=threading.RLock()
    def auth(header):
        if header not in states:raise HTTPException(401,'authentication required')
        return header
    @contextmanager
    def store(code):
        with lock:
            state=copy.deepcopy(states[code]);yield state;states[code]=state
    app=FastAPI();attempt_review.attach_attempt_review(app,auth,lambda c:copy.deepcopy(states[c]),store,lambda:clock[0])
    return TestClient(app),states,clock


def post(c,request='request_000000001',owner='A',item='item'):
    return c.post('/api/journey/revalidate',headers={'Authorization':owner},
                  json={'report_id':'report','item_id':item,'request_id':request})


def test_owned_idempotent_correction_preserves_original_and_active():
    c,states,clock=make();original=copy.deepcopy(states['A'])
    assert post(c,owner='B').status_code==404
    assert c.get('/api/journey/attempt-evidence/report',headers={'Authorization':'B'}).status_code==404
    r=post(c);assert r.status_code==200,r.text
    assert r.json()['resolution']['status']=='verified_non_mate'
    assert post(c).json()==r.json()
    assert post(c,request='request_000000002').json()==r.json()
    assert len(states['A']['attempt_revalidations'])==1
    for key in original:assert states['A'][key]==original[key]
    view=c.get('/api/journey/attempt-evidence/report',headers={'Authorization':'A'}).json()
    assert view['totals']['verified_wrong']==1 and view['totals']['unresolved']==0


def test_unknown_is_not_failure_and_retry_budget_is_finite(monkeypatch):
    c,states,clock=make();original=copy.deepcopy(states['A']['results'])
    monkeypatch.setattr(attempt_review,'resolve_attempt',lambda *a,**k:{'status':'unknown','reason':'test_budget','suggestion':None})
    for n in range(3):
        assert post(c,request=f'request_00000000{n}').status_code==200
        if n<2:assert post(c,request='request_cooldown00').status_code==429
        clock[0]+=timedelta(seconds=11)
    assert post(c,request='request_exhausted').status_code==409
    assert states['A']['results']==original
    view=c.get('/api/journey/attempt-evidence/report',headers={'Authorization':'A'}).json()
    assert view['totals']['unresolved']==1


def test_concurrent_retry_admission_does_not_duplicate_proof(monkeypatch):
    c,states,clock=make();entered=threading.Event();release=threading.Event();calls=[]
    original_resolver=attempt_review.resolve_attempt
    def delayed(*args,**kwargs):
        calls.append(1);entered.set();release.wait(3);return original_resolver(*args,**kwargs)
    monkeypatch.setattr(attempt_review,'resolve_attempt',delayed)
    thread=threading.Thread(target=lambda:post(c));thread.start();assert entered.wait(2)
    try:assert post(c).status_code==429
    finally:release.set();thread.join(4)
    assert len(calls)==1 and len(states['A']['attempt_revalidations'])==1
    assert post(c).status_code==200


def test_request_id_cannot_target_another_item_and_raw_move_is_ignored():
    c,states,clock=make();other=copy.deepcopy(states['A']['results'][0]['items'][0]);other['id']='other'
    states['A']['results'][0]['items'].append(other)
    response=c.post('/api/journey/revalidate',headers={'Authorization':'A'},json={
        'report_id':'report','item_id':'item','request_id':'request_000000001','move':'g4g7'})
    assert response.json()['resolution']['mismatch']['move']=='g4g3'
    assert post(c,item='other').status_code==409


def test_malformed_optional_time_does_not_reject_valid_chess_move(setup):
    from test_journey import attach, post as journey_post, saved
    c,_,_,path=attach(setup)
    session=journey_post(c,'start',{'mode':'balanced'})
    item=saved(path)['active']['items'][0]
    response=c.post('/api/journey/action',json={'session_id':session['session_id'],
        'revision':session['revision'],'action':'move','move':item['line'][0],'thinking_time':'invalid'})
    assert response.status_code==200,response.text
    stored=saved(path)['active']['items'][0]
    assert stored['thinking_time']['usable_for_trend'] is False
    assert 'invalid_payload' in stored['thinking_time']['flags']


def test_actual_stockfish_agrees_with_short_mate_counterexample():
    import os,chess,chess.engine
    from attempt_evidence import resolve_attempt
    engine=chess.engine.SimpleEngine.popen_uci(os.environ['STOCKFISH_PATH'])
    try:
        item={'fen':'r1b1k2r/p1pp1ppp/2p5/8/2P1N3/4Q2P/PPK1P3/q7 w kq - 0 18',
              'line':['e4d6','e8d8','d6f7'],'tags':['mateIn2'],'submitted':['e4g5'],
              'outcome':'unverified_alternative'}
        result=resolve_attempt(item)
        assert result['status']=='verified_non_mate'
        b=chess.Board(item['fen']);b.push_uci('e4g5')
        evaluation=engine.analyse(b,chess.engine.Limit(time=.2,depth=18,nodes=100000))
        assert evaluation['score'].white().score(mate_score=10000)<0
        assert evaluation['pv'][0].uci()=='e8f8'
    finally:engine.quit()
