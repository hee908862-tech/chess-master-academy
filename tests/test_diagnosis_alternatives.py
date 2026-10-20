import json,os
import chess
import pytest
import growth_model as growth
from engine_budget import EngineBusy
from study_server import DATA

ENGINE=os.environ.get('STOCKFISH_PATH','/tmp/chess-stockfish/usr/games/stockfish')

def test_ozelq_real_engine_and_sequence_context():
    row=next(json.loads(l) for l in open('puzzles_lichess.jsonl') if '"OZElq"' in l)
    b=chess.Board(row['fen']);b.push_uci(row['moves'][0])
    wrong=growth.verify_loss(b.fen(),'d2c3',ENGINE)
    assert wrong['status']=='verified_error' and wrong['loss_cp']>=200 and min(wrong['depths'])>=10,wrong
    same=growth.verify_loss(b.fen(),'d3e4',ENGINE);assert same['status']=='equivalent_alternative',same
    assert chess.Move.from_uci('d2g5') not in b.legal_moves
    b.push_uci('d3e4');b.push_uci('e7g5');assert chess.Move.from_uci('d2g5') in b.legal_moves
    after=growth.verify_loss(b.fen(),'d2g5',ENGINE);assert after['status']!='verified_error',after


def test_unverified_causes_and_engine_budget(monkeypatch,tmp_path):
    path=tmp_path/'engine';path.touch()
    assert growth.verify_loss(chess.STARTING_FEN,'e2e4','')['reason']=='engine_unavailable'
    class Engine:
        id={'name':'test'}
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def configure(self,*a):pass
        def analyse(self,*a):return {'score':chess.engine.PovScore(chess.engine.Cp(0),chess.WHITE),'depth':4}
    monkeypatch.setattr(growth,'open_engine',lambda *a,**k:Engine())
    assert growth.verify_loss(chess.STARTING_FEN,'e2e4',str(path))['reason']=='insufficient_depth'
    Engine.analyse=lambda *a:{'score':chess.engine.PovScore(chess.engine.Mate(2),chess.WHITE),'depth':12}
    r=growth.verify_loss(chess.STARTING_FEN,'e2e4',str(path));assert r['reason']=='mate_requires_proof' and 'loss_cp' not in r
    def busy(*a,**k):raise EngineBusy()
    monkeypatch.setattr(growth,'open_engine',busy)
    assert growth.verify_loss(chess.STARTING_FEN,'e2e4',str(path))['reason']=='engine_busy'
    assert growth._diagnostic_slot.acquire(False)
    try:assert growth.verify_loss(chess.STARTING_FEN,'e2e4',str(path))['reason']=='diagnosis_busy'
    finally:growth._diagnostic_slot.release()


def test_equivalent_is_not_full_line_credit():
    item={'app_new':True,'helped':False,'first_attempt':True,'outcome':'equivalent_alternative','band':[600,1200],'correct_plies':0,'total_plies':2}
    assert growth.area_score([item])['observed']==0 and growth.area_score([item])['score'] is None
    state={'cycles':{'r':{'cards':{'1':'c'}}}}
    growth.credit_cycle(state,{'growth_task':{'report_id':'r','task_id':'1'},'card_id':'c','turns':1},{'success':False,'assessment_scope':'full_line'})
    assert not state['cycles']['r'].get('completed')

from test_runtime_isolation import runtime

def test_balanced_api_real_ozelq_and_busy_reason(runtime,monkeypatch):
    import journey_server
    server,(client,_)=runtime;monkeypatch.setattr(server,'STOCKFISH_PATH',ENGINE)
    r=client.post('/api/journey/start',json={'mode':'balanced'});assert r.status_code==200,r.text
    source=next(json.loads(l) for l in open('puzzles_lichess.jsonl') if '"OZElq"' in l)
    b=chess.Board(source['fen']);b.push_uci(source['moves'][0])
    def install_question():
        with server.db() as conn:
            raw=server.execute(conn,'SELECT state FROM journey_progress WHERE code=?',('RUNTIME-A',)).fetchone()
            state=json.loads(raw['state']);s=state['active'];item=s['items'][s['index']]
            item.update(puzzle_id='OZElq',fen=b.fen(),line=source['moves'][1:],competency='capture',band=[1200,1800],tags=source['themes'])
            s.update(fen=b.fen(),offset=0,correct=0,submitted=[],played=[],phase='question')
            server.execute(conn,'UPDATE journey_progress SET state=? WHERE code=?',(json.dumps(state),'RUNTIME-A'))
        return s
    s=install_question()
    r=client.post('/api/journey/action',json={'session_id':s['session_id'],'revision':s['revision'],'action':'move','move':'d2c3'})
    assert r.status_code==200,r.text
    assert r.json()['feedback']['outcome']=='verified_error'
    assert r.json()['feedback']['engine_evidence']['depth']>=10
    s=install_question()
    def busy(*a,**kw):raise EngineBusy()
    monkeypatch.setattr(growth,'open_engine',busy)
    r=client.post('/api/journey/action',json={'session_id':s['session_id'],'revision':s['revision'],'action':'move','move':'d2c3'})
    assert r.json()['feedback']['outcome']=='unverified_alternative'
    assert r.json()['feedback']['engine_evidence']['reason']=='engine_busy'
