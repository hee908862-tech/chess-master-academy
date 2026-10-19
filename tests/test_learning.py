"""New learning API: real SQLite isolation/concurrency, corpus and engine boundaries."""
import copy
import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

import chess
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import learning_server as learning


@pytest.fixture
def setup(tmp_path):
    path = tmp_path/'learning.sqlite'
    legacy = {'games': [], 'puzzle_results': [], 'completed_lessons': ['old']}
    @contextmanager
    def db():
        with sqlite3.connect(path, timeout=10) as conn:
            conn.row_factory=sqlite3.Row
            yield conn
    def auth(h):
        if not h: raise HTTPException(401)
        return h
    ns = {'db':db, 'execute':lambda c,q,a=():c.execute(q,a), 'DATABASE_URL':'',
          'auth':auth, 'get_state':lambda _:copy.deepcopy(legacy), 'STOCKFISH_PATH':''}
    app=FastAPI(); learning.attach_learning(app,ns)
    client=TestClient(app,headers={'Authorization':'A'})
    return client,ns,legacy,path


def post(client, path, data):
    r=client.post('/api/learning/'+path,json=data)
    assert r.status_code==200,r.text
    return r.json()


def action(client,s,kind,move=None):
    return post(client,'action',{'session_id':s['session_id'],'revision':s['revision'],'action':kind,'move':move})


def solution(s):
    return learning.LIB[s['card_id'].removeprefix('puzzle-')]['moves'][1]


def test_hidden_answer_verify_server_enforced(setup):
    c,ns,old,_=setup
    s=post(c,'start',{'fresh':True,'mode':'verify'})
    assert s['category'] is None and s['concept'] is None
    assert not s['playback'] and 'line' not in s and 'best_move' not in s
    for kind in ('hint','reveal','undo','refutation'):
        assert c.post('/api/learning/action',json={'session_id':s['session_id'],'revision':0,'action':kind}).status_code==403
    done=action(c,s,'move',solution(s))
    assert done['done'] and done['legal']==[] and done['outcome']['status']=='unaided_first_success'
    assert old=={'games': [], 'puzzle_results': [], 'completed_lessons': ['old']}
    assert c.post('/api/learning/action',json={'session_id':s['session_id'],'revision':0,'action':'move','move':solution(s)}).status_code==409


@pytest.mark.parametrize('kind,status',[('hint','hinted_success'),('reveal','revealed_success')])
def test_help_classification_and_delayed_restore(setup,monkeypatch,kind,status):
    c,ns,_,path=setup
    s=post(c,'start',{'fresh':True})
    s=action(c,s,kind)
    s=action(c,s,'move',solution(s)); assert s['outcome']['status']==status
    stamp=learning.now()+timedelta(days=2)
    monkeypatch.setattr(learning,'now',lambda:stamp)
    # New application instance with same DB, not an in-memory mock.
    app=FastAPI();learning.attach_learning(app,ns)
    restored=TestClient(app,headers={'Authorization':'A'})
    d=restored.get('/api/learning/dashboard').json()
    assert d['active']['done'] and len(d['attempts'])==1 and len(d['due'])==1
    s=post(restored,'start',{'card_id':s['card_id'],'mode':'verify'})
    s=action(restored,s,'move',solution(s))
    assert s['outcome']['status']=='later_unaided_success'


def test_concurrent_duplicate_move_commits_once(setup):
    c,_,_,_=setup
    s=post(c,'start',{'fresh':True})
    body={'session_id':s['session_id'],'revision':0,'action':'move','move':solution(s)}
    with ThreadPoolExecutor(max_workers=4) as pool:
        codes=list(pool.map(lambda _:c.post('/api/learning/action',json=body).status_code,range(4)))
    assert sorted(codes)==[200,409,409,409]
    assert len(c.get('/api/learning/dashboard').json()['attempts'])==1


def test_account_isolation_and_settings_rollback(setup):
    c,_,_,_=setup
    post(c,'start',{'fresh':True})
    assert c.get('/api/learning/dashboard',headers={'Authorization':'B'}).json()['active'] is None
    assert c.get('/api/learning/dashboard',headers={'Authorization':''}).status_code==401
    post(c,'settings',{'intervals':[2,5,10]})
    assert c.post('/api/learning/settings',json={'intervals':[5,1]}).status_code==400
    assert c.get('/api/learning/dashboard').json()['intervals']==[2,5,10]


def test_no_engine_and_no_repeat(setup):
    c,ns,old,_=setup
    old['games']=[{'moves':['f2f3','e7e5','g2g4','d8h4'],'color':'white'}]
    assert c.post('/api/learning/import/0').status_code==503
    s=post(c,'start',{'fresh':True})
    assert c.post('/api/learning/start',json={'card_id':s['card_id'],'mode':'situation_verify'}).status_code==503
    assert c.get('/api/learning/dashboard').json()['active']['session_id']==s['session_id']
    next_s=post(c,'start',{'fresh':True})
    assert next_s['card_id']!=s['card_id']


def test_legacy_seen_excluded_and_missing_data(setup,monkeypatch):
    c,_,old,_=setup
    p=next(iter(learning.LIB.values()))
    monkeypatch.setattr(learning,'LIB',{p['id']:p})
    old['puzzle_results']=[{'puzzle_id':p['id']}]
    assert c.post('/api/learning/start',json={'fresh':True}).status_code==409
    assert c.get('/api/learning/dashboard').json()['cards']==[]


def test_wrong_verification_records_failure(setup):
    c,_,_,_=setup
    s=post(c,'start',{'fresh':True,'mode':'verify'})
    b=chess.Board(s['fen'])
    wrong=next(m.uci() for m in b.legal_moves if m.uci()!=solution(s) and not after_mate(b,m))
    result=action(c,s,'move',wrong)
    assert result['done'] and result['outcome']['status']=='unverified_alternative'


def after_mate(board,move):
    b=board.copy();b.push(move);return b.is_checkmate()


ENGINE='/tmp/chess-stockfish/usr/games/stockfish'
@pytest.mark.skipif(not Path(ENGINE).exists(),reason='local real Stockfish unavailable')
def test_real_engine_situation_and_undo(setup):
    c,ns,_,_=setup;ns['STOCKFISH_PATH']=ENGINE
    s=post(c,'start',{'fresh':True,'category':'endgame'})
    s=post(c,'start',{'card_id':s['card_id'],'mode':'situation_practice'})
    hint=action(c,s,'hint'); assert hint['hint_level']==1
    with chess.engine.SimpleEngine.popen_uci(ENGINE) as eng:
        move=eng.play(chess.Board(s['fen']),chess.engine.Limit(time=.2)).move.uci()
    advanced=action(c,hint,'move',move)
    assert advanced['turns']==1
    if not advanced['done']:
        undone=action(c,advanced,'undo')
        assert undone['fen']==s['fen'] and undone['turns']==0


@pytest.mark.skipif(not Path(ENGINE).exists(),reason='local real Stockfish unavailable')
def test_real_game_import_deduplicates(setup,monkeypatch,tmp_path):
    c,ns,old,_=setup
    # Reuse actual existing review implementation without accessing any user DB.
    monkeypatch.setenv('SQLITE_FILE',str(tmp_path/'legacy.sqlite'));monkeypatch.setenv('DATABASE_URL','')
    import server
    ns['build_review_rows']=server.build_review_rows;ns['STOCKFISH_PATH']=ENGINE
    old['games']=[{'moves':['f2f3','e7e5','g2g4','d8h4'],'color':'white'}]
    result=c.post('/api/learning/import/0');assert result.status_code==200,result.text
    assert 1<=result.json()['count']<=3
    count=len(c.get('/api/learning/dashboard').json()['cards'])
    c.post('/api/learning/import/0')
    assert len(c.get('/api/learning/dashboard').json()['cards'])==count
    card=c.get('/api/learning/dashboard').json()['cards'][0]
    s=post(c,'start',{'card_id':card['id']})
    s=action(c,s,'refutation');assert s['playback']
    for frame in s['playback']:assert chess.Board(frame['fen']).is_valid()


def test_new_learning_survives_legacy_json_writes(setup):
    c,ns,old,path=setup
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE progress(code TEXT PRIMARY KEY,state TEXT)')
        conn.execute('INSERT INTO progress VALUES(?,?)',('A',json.dumps(old)))
    s=post(c,'start',{'fresh':True})
    def legacy_write(_):
        with sqlite3.connect(path,timeout=10) as conn:
            conn.execute('UPDATE progress SET state=? WHERE code=?',(json.dumps(old),'A'))
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs=[pool.submit(legacy_write,i) for i in range(3)]
        done=action(c,s,'move',solution(s))
        for job in jobs:job.result()
    assert done['done']
    with sqlite3.connect(path) as conn:
        assert json.loads(conn.execute('SELECT state FROM progress').fetchone()[0])==old
        assert len(json.loads(conn.execute('SELECT state FROM learning_progress').fetchone()[0])['attempts'])==1


@pytest.mark.skipif(not Path(ENGINE).exists(),reason='local real Stockfish unavailable')
def test_situation_six_turn_completion_and_assisted_undo(setup):
    c,ns,_,path=setup;ns['STOCKFISH_PATH']=ENGINE
    original=post(c,'start',{'fresh':True})
    with sqlite3.connect(path) as conn:
        state=json.loads(conn.execute('SELECT state FROM learning_progress').fetchone()[0])
        state['cards'][original['card_id']].update(fen=chess.STARTING_FEN,line=['e2e4'],prior=None)
        conn.execute('UPDATE learning_progress SET state=?',(json.dumps(state),))
    s=post(c,'start',{'card_id':original['card_id'],'mode':'situation_practice'})
    with chess.engine.SimpleEngine.popen_uci(ENGINE) as eng:
        for turn in range(6):
            move=eng.play(chess.Board(s['fen']),chess.engine.Limit(time=.12)).move.uci()
            s=action(c,s,'move',move)
            if turn==0:
                assert not s['done']
                s=action(c,s,'undo'); assert s['fen']==chess.STARTING_FEN
                s=action(c,s,'move',move)
            if s['done']:break
    assert s['done'] and s['outcome']['mode']=='situation_practice'
    assert s['outcome']['helped']
    if s['outcome']['success']:assert s['outcome']['status']=='hinted_success'

@pytest.mark.parametrize('help_kind,expected',[('reveal','revealed_success'),('hint','hinted_success'),('wrong','retry_success')])
def test_restart_cannot_erase_card_exposure(setup,help_kind,expected):
    c,_,_,_=setup
    s=post(c,'start',{'fresh':True})
    if help_kind=='wrong':
        b=chess.Board(s['fen']);wrong=next(m.uci() for m in b.legal_moves if m.uci()!=solution(s) and not after_mate(b,m))
        action(c,s,'move',wrong)
    else:action(c,s,help_kind)
    # No completed attempt before restarting: the card itself must retain exposure.
    assert c.get('/api/learning/dashboard').json()['attempts']==[]
    s=post(c,'start',{'card_id':s['card_id']})
    result=action(c,s,'move',solution(s))
    assert result['outcome']['status']==expected
    assert result['outcome']['independent_kind'] is None
    assert c.get('/api/learning/dashboard').json()['cards'][0]['successes']==0


def test_delayed_credit_once_daily_and_distinct_evidence(setup,monkeypatch):
    c,_,_,_=setup
    s=post(c,'start',{'fresh':True})
    action(c,s,'move',solution(s))
    tomorrow=learning.now()+timedelta(days=2)
    monkeypatch.setattr(learning,'now',lambda:tomorrow)
    s=post(c,'start',{'card_id':s['card_id'],'mode':'verify'})
    first=action(c,s,'move',solution(s))
    assert first['outcome']['status']=='later_unaided_success'
    d=c.get('/api/learning/dashboard').json();due=d['cards'][0]['due']
    for _ in range(5):
        s=post(c,'start',{'card_id':s['card_id'],'mode':'verify'})
        repeated=action(c,s,'move',solution(s))
        assert repeated['outcome']['status']=='unaided_repeat_success'
    d=c.get('/api/learning/dashboard').json()
    assert d['cards'][0]['due']==due and d['cards'][0]['successes']==2
    skill=next(k for k in d['skills'] if k['count'])
    first=next(g for g in skill['groups'] if g['assessment_scope']=='first_move')
    assert first['independent']==2 and first['distinct']==1 and first['insufficient']
    assert first['novel']==1 and first['delayed']==1
    assert skill['independent']==0 and skill['recent'] is None


def test_shared_tag_selection_and_no_unrelated_fallback(setup,monkeypatch):
    c,_,_,_=setup
    bases=copy.deepcopy(list(learning.LIB.values())[:3])
    source={**bases[0],'id':'source','themes':['fork']}
    related={**bases[1],'id':'related','themes':['fork','pin']}
    unrelated={**bases[2],'id':'unrelated','themes':['skewer']}
    monkeypatch.setattr(learning,'LIB',{'source':source})
    s=post(c,'start',{'fresh':True})
    monkeypatch.setattr(learning,'LIB',{'related':related,'unrelated':unrelated})
    new=post(c,'start',{'similar_to':s['card_id'],'mode':'verify'})
    assert new['card_id']=='puzzle-related' and new['selection'] is None
    result=action(c,new,'move',related['moves'][1])
    evidence=result['outcome']['selection']
    assert evidence['overlap']==['fork'] and evidence['source_card']==s['card_id']
    assert sum(k['transfer'] for k in c.get('/api/learning/dashboard').json()['skills'])==1
    assert c.post('/api/learning/start',json={'similar_to':s['card_id'],'mode':'verify'}).status_code==409
    # Independent selection can still use unrelated data, but must never count as transfer.
    other=post(c,'start',{'fresh':True,'mode':'verify'})
    action(c,other,'move',unrelated['moves'][1])
    assert sum(k['transfer'] for k in c.get('/api/learning/dashboard').json()['skills'])==1


def path_request(c,d=None,kind='continue'):
    return post(c,'path',{'action':kind,**({'path_id':d['id'],'revision':d['revision']} if d else {})})


def test_daily_route_keeps_source_and_resumes_after_free_practice(setup,monkeypatch):
    c,ns,_,_=setup
    s=post(c,'start',{'fresh':True})
    source=s['card_id']
    route=path_request(c);path=route['path'];review=route['active']
    assert path['source_card']==source and path['current']==0
    review=action(c,review,'hint')
    # Other freely selected learning must not destroy the route's in-progress session.
    post(c,'start',{'fresh':True})
    app=FastAPI();learning.attach_learning(app,ns);c=TestClient(app,headers={'Authorization':'A'})
    restored=path_request(c)
    assert restored['active']['session_id']==review['session_id']
    assert restored['active']['hint_level']==1
    action(c,restored['active'],'move',solution(review))
    d=c.get('/api/learning/dashboard').json()
    assert source not in [card['id'] for card in d['due']]
    concept=path_request(c,d['path']);assert concept['path']['current']==1
    acknowledged=path_request(c,concept['path'],'acknowledge')
    assert acknowledged['path']['current']==2
    assert c.post('/api/learning/path',json={'action':'acknowledge','path_id':concept['path']['id'],'revision':concept['path']['revision']}).status_code==409
    transfer=path_request(c,acknowledged['path'])
    assert transfer['active']['mode']=='verify'
    result=action(c,transfer['active'],'move',solution(transfer['active']))
    assert result['outcome']['path_id']==path['id'] and result['outcome']['selection']['overlap']
    finished=path_request(c)
    assert finished['path']['done'] and finished['path']['source_card']==source
    assert finished['path']['steps'][3]['status']=='skipped'
    assert 'Stockfish' in finished['path']['steps'][3]['reason']
    d=c.get('/api/learning/dashboard').json()
    assert d['path']==finished['path']
    assert [a['mode'] for a in d['attempts']]==['verify','practice']
    assert sum(k['transfer'] for k in d['skills'])==1


def test_newcomer_route_starts_real_beginner_task(setup):
    c,_,_,_=setup
    result=path_request(c)
    assert not result['path']['done'] and result['path']['fresh']
    assert result['path']['steps'][0]['status']=='active'
    task=result['active']; original=learning.LIB[task['card_id'].removeprefix('puzzle-')]
    assert 600<=original['rating']<=1200 and 'mateIn1' in original['themes']
    assert c.get('/api/learning/dashboard').json()['attempts']==[]
    finished=action(c,task,'move',solution(task))
    assert finished['done'] and finished['outcome']['status']=='unaided_first_success'
    route=path_request(c)['path']
    assert route['current']==1 and not route['done']


def test_missing_corpus_route_never_claims_completion(setup,monkeypatch):
    c,_,_,_=setup
    monkeypatch.setattr(learning,'LIB',{})
    result=path_request(c)
    assert not result['path']['done'] and result['active'] is None
    assert all(s['status']=='pending' for s in result['path']['steps'])
    assert '완료한 상태가 아닙니다' in result['path']['selection_reason']
    assert c.get('/api/learning/dashboard').json()['attempts']==[]


def test_next_route_prioritizes_failed_verification(setup,monkeypatch):
    c,_,_,path=setup
    first=post(c,'start',{'fresh':True})
    second=post(c,'start',{'fresh':True})
    with sqlite3.connect(path) as conn:
        state=json.loads(conn.execute('SELECT state FROM learning_progress').fetchone()[0])
        state['cards'][second['card_id']]['full_line']=True
        state['attempts'].append({'card_id':second['card_id'],'mode':'verify','success':False,
                                  'competency_version':learning.COMPETENCY_VERSION,'assessment_scope':'full_line'})
        conn.execute('UPDATE learning_progress SET state=?',(json.dumps(state),))
    route=path_request(c)
    assert route['path']['source_card']==second['card_id']

@pytest.mark.skipif(not Path(ENGINE).exists(),reason='local real Stockfish unavailable')
def test_route_missing_transfer_skips_but_original_situation_still_starts(setup,monkeypatch):
    c,ns,_,_=setup;ns['STOCKFISH_PATH']=ENGINE
    original=post(c,'start',{'fresh':True,'category':'endgame'})
    puzzle=learning.LIB[original['card_id'].removeprefix('puzzle-')]
    monkeypatch.setattr(learning,'LIB',{puzzle['id']:puzzle})
    review=path_request(c)['active']
    action(c,review,'move',puzzle['moves'][1])
    concept=path_request(c)
    path_request(c,concept['path'],'acknowledge')
    situation=path_request(c)
    assert situation['path']['current']==3
    assert situation['path']['steps'][2]['status']=='skipped'
    assert '미노출' in situation['path']['steps'][2]['reason']
    assert situation['active']['mode']=='situation_practice'
    assert situation['active']['card_id']==original['card_id']
    d=c.get('/api/learning/dashboard').json()
    assert original['card_id'] not in [row['id'] for row in d['due']]
    assert d['path']['source_card']==original['card_id']
