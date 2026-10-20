import copy
from types import SimpleNamespace
import chess
import pytest
import app_rating as ar
from test_runtime_isolation import runtime


def game(result='win',color='white',mode='unlimited'):
    moves=['e2e4','e7e5','g1f3','b8c6']
    calls=[{'ply':i+1,'engine':'Stockfish 17.1','settings':{'level':5,'configured':True,'fallback':False},'anchor':40,'policy':ar.AI_VERSION} for i in range(4) if (i%2==0)!=(color=='white')]
    return {'session_id':'one','result':result,'moves':moves,'color':color,'time_mode':mode,'termination':'rules','assistance':{'version':1,'complete':True,'events':[]},'ai_execution':{'version':ar.AI_VERSION,'complete':True,'calls':calls}}


@pytest.mark.parametrize('color',['white','black'])
@pytest.mark.parametrize('result',['win','draw','loss'])
def test_outcomes_and_duplicate_archive(color,result):
    g=game(result,color);state={'games':[g]};ar.archive(state,g)
    record=g['app_rating'];assert record['eligible'] and record['before']==50
    assert (record['after']>50)==(result=='win')
    original=copy.deepcopy(state);ar.archive(state,g);assert state==original
    duplicate=copy.deepcopy(g);duplicate.pop('app_rating');state['games'].append(duplicate);ar.archive(state,duplicate)
    assert state['app_ratings']['unlimited']['games']==1 and duplicate['app_rating']==record


@pytest.mark.parametrize('termination',['resign','timeout'])
def test_normal_loss_is_included_and_modes_are_separate(termination):
    g=game('loss');g['termination']=termination;state={'games':[g]};ar.archive(state,g)
    assert g['app_rating']['eligible'] and g['app_rating']['after']<50
    other=game('win',mode='bullet');other['session_id']='two';state['games'].append(other);ar.archive(state,other)
    assert state['app_ratings']['bullet']['games']==1 and other['app_rating']['before']==50


@pytest.mark.parametrize('change,reason',[
    (lambda g:g.pop('ai_execution'),'실제 AI'),
    (lambda g:g['assistance'].update(complete=False),'도움 정보'),
    (lambda g:g['assistance']['events'].append({'kind':'undo'}),'힌트·무르기'),
    (lambda g:g['ai_execution']['calls'][0].update(anchor=None),'기준점'),
    (lambda g:g['ai_execution']['calls'][0].update(engine='cma-minimax-v1'),'대체 AI'),
    (lambda g:g.update(termination='aborted'),'정상 종료'),
])
def test_exclusion_is_explicit_no_retroactive_estimate(change,reason):
    g=game();change(g);before=copy.deepcopy(g)
    assert not ar.public_game(g)['eligible'] and g==before
    state={'games':[g]};ar.archive(state,g)
    assert not g['app_rating']['eligible'] and reason in ' '.join(g['app_rating']['reasons'])
    assert 'app_ratings' not in state


def test_real_api_records_effective_engine_and_persists_once(runtime,monkeypatch,tmp_path):
    server,(a,b)=runtime;binary=tmp_path/'engine';binary.touch();monkeypatch.setattr(server,'STOCKFISH_PATH',str(binary))
    class Engine:
        id={'name':'Stockfish 17.1'}
        def configure(self,options):assert options['Threads']==1
        def play(self,board,limit):return SimpleNamespace(move=next(iter(board.legal_moves)))
        def quit(self):pass
    monkeypatch.setattr(chess.engine.SimpleEngine,'popen_uci',lambda *a,**k:Engine())
    g=a.post('/api/game/new',json={'color':'black','difficulty':5,'time_mode':'bullet'}).json()
    move=g['board']['legal'][0]
    response=a.post('/api/game/move',json={'from_sq':move['from'],'to_sq':move['to'],'session_id':g['session_id']});assert response.status_code==200,response.text
    assert a.post('/api/game/resign').status_code==200
    saved=server.get_state('RUNTIME-A');record=saved['games'][0]
    assert record['app_rating']['eligible'] and record['app_rating']['result']=='loss'
    assert record['ai_execution']['calls'][0]['settings']['UCI_Elo']==1900
    first=a.get('/api/games/analysis').json();assert first['app_rating']['series']['bullet']['games']==1
    assert a.post('/api/game/resign').status_code==400
    server.initdb()
    assert a.get('/api/games/analysis').json()==first
    assert server.get_state('RUNTIME-A')==saved
    assert b.get('/api/games/analysis').json()['app_rating']['series']=={}


@pytest.mark.parametrize('failure',['configuration','unknown_version','fallback'])
def test_effective_profile_failures_are_not_rated(runtime,monkeypatch,tmp_path,failure):
    server,(a,b)=runtime;binary=tmp_path/'engine';binary.touch();monkeypatch.setattr(server,'STOCKFISH_PATH',str(binary))
    class Engine:
        id={'name':'Stockfish 99' if failure=='unknown_version' else 'Stockfish 17.1'}
        def configure(self,options):
            if failure=='configuration':raise RuntimeError('unsupported')
        def play(self,board,limit):return SimpleNamespace(move=next(iter(board.legal_moves)))
        def quit(self):pass
    def open_engine(*a,**k):
        if failure=='fallback':raise OSError('engine absent')
        return Engine()
    monkeypatch.setattr(chess.engine.SimpleEngine,'popen_uci',open_engine)
    g=a.post('/api/game/new',json={'color':'white','difficulty':1}).json();move=g['board']['legal'][0]
    assert a.post('/api/game/move',json={'from_sq':move['from'],'to_sq':move['to']}).status_code==200
    assert a.post('/api/game/resign').status_code==200
    saved=server.get_state('RUNTIME-A')['games'][0]
    assert not saved['app_rating']['eligible'] and saved['app_rating']['reasons']
    assert saved['ai_execution']['calls'][0]['settings']['fallback']==(failure=='fallback')


def test_analysis_and_reload_do_not_reapply_internal_rating(runtime,monkeypatch):
    import game_analysis as ga
    from test_game_analysis import wait_result
    server,(a,b)=runtime;state=server.get_state('RUNTIME-A');g=game();state['games']=[g];ar.archive(state,g);server.save_state('RUNTIME-A',state)
    before=copy.deepcopy(state['app_ratings']);key=ga.game_key(g)
    monkeypatch.setattr(ga,'analyse_game',lambda *a:{'status':'complete','score_version':ga.VERSION,'quality':70,'user_moves':2,'representative':False})
    assert a.post('/api/games/analysis/'+key).status_code==200;wait_result(a,key)
    assert a.post('/api/games/analysis/'+key).status_code==200
    server.initdb();a.get('/api/games/analysis');assert server.get_state('RUNTIME-A')['app_ratings']==before


@pytest.mark.parametrize('color',['white','black'])
def test_ai_clock_expiry_keeps_unplayed_evaluation_provenance(color):
    g=game('win',color);g['termination']='timeout'
    if color=='white':g['moves']=g['moves'][:3]
    else:g['ai_execution']['calls'].append({**copy.deepcopy(g['ai_execution']['calls'][-1]),'ply':5})
    state={'games':[g]};ar.archive(state,g)
    assert g['app_rating']['eligible'] and g['app_rating']['after']>50
    assert g['ai_execution']['calls'][-1]['played'] is False


def test_actual_api_ai_clock_expiry_is_rated(runtime,monkeypatch,tmp_path):
    import time
    server,(a,b)=runtime;binary=tmp_path/'engine';binary.touch();monkeypatch.setattr(server,'STOCKFISH_PATH',str(binary))
    class Engine:
        id={'name':'Stockfish 17.1'}
        def configure(self,options):pass
        def play(self,board,limit):time.sleep(.02);return SimpleNamespace(move=next(iter(board.legal_moves)))
        def quit(self):pass
    monkeypatch.setattr(chess.engine.SimpleEngine,'popen_uci',lambda *a,**k:Engine())
    g=a.post('/api/game/new',json={'color':'white','difficulty':5,'time_mode':'bullet'}).json()
    state=server.get_state('RUNTIME-A');state['active_game']['black_ms']=1;server.save_state('RUNTIME-A',state)
    move=g['board']['legal'][0];response=a.post('/api/game/move',json={'from_sq':move['from'],'to_sq':move['to']})
    assert response.status_code==200 and response.json()['timeout'] and response.json()['outcome']=='win'
    saved=server.get_state('RUNTIME-A')['games'][0]
    assert saved['app_rating']['eligible'] and saved['app_rating']['after']>50
    assert saved['ai_execution']['calls'][-1]['played'] is False
