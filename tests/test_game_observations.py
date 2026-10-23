import copy
import chess
import game_analysis as ga
from game_observations import observe_game
from assistance import ledger, event, record_move
from test_runtime_isolation import runtime


FEN = '7k/5K2/6Q1/8/8/8/8/8 w - - 0 1'


def sample(move='g6g7'):
    return {'initial_fen': FEN, 'moves': [move], 'color': 'white', 'time_mode': 'rapid'}


def test_multiple_mates_are_one_opportunity_and_original_unchanged():
    game = sample(); original = copy.deepcopy(game)
    result = observe_game(game, ga.game_key(game))
    assert game == original
    assert result['status'] == 'complete'
    assert result['summary']['opportunities'] == result['summary']['executed'] == 1
    row = result['rows'][0]
    assert len(row['alternatives']) > 1 and row['before_fen'] == FEN
    assert row['source'] == 'legal_rules' and row['pv'] is None
    assert row['assistance']['hint_viewed'] is None


def test_other_move_and_black_mate_and_stalemate():
    assert observe_game(sample('f7e7'), 'a')['summary']['other_move'] == 1
    black = {'initial_fen': '8/8/8/8/8/6q1/5k2/7K b - - 0 1',
             'moves': ['g3g2'], 'color': 'black'}
    assert observe_game(black, 'b')['summary']['executed'] == 1
    # Qg6 here stalemates: never classify the move as executing mate.
    game = {'initial_fen': '7k/5K2/8/6Q1/8/8/8/8 w - - 0 1',
            'moves': ['g5g6'], 'color': 'white'}
    board = chess.Board(game['initial_fen']);board.push_uci('g5g6')
    assert board.is_stalemate()
    assert observe_game(game, 'c')['summary']['executed'] == 0


def test_promotion_mate_and_en_passant_state_use_full_legal_position():
    g = {'initial_fen':'k7/2P5/1K6/8/8/8/8/8 w - - 0 1',
         'moves':['c7c8q'],'color':'white'}
    result = observe_game(g,'promotion')
    assert result['summary']['executed'] == 1
    assert result['rows'][0]['played_uci'] == 'c7c8q'
    # En passant is a legal capture only while the original FEN right remains.
    ep = {'initial_fen':'4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2',
          'moves':['e5d6'],'color':'white'}
    assert observe_game(ep,'ep')['status'] == 'complete'
    ep['initial_fen'] = ep['initial_fen'].replace(' d6 ', ' - ')
    assert observe_game(ep,'no-ep')['status'] == 'unavailable'


def test_allowed_mate_has_legal_avoidance_witness():
    game = {'moves': ['f2f3', 'e7e5', 'g2g4'], 'color': 'white'}
    result = observe_game(game, 'x');row = result['rows'][0]
    assert row['opponent_mates'] == ['d8h4']
    assert row['kind'] == 'allows_mate_in_one' and not row['alternatives_complete']
    board = chess.Board(row['before_fen']);board.push_uci(row['alternatives'][0])
    for move in board.legal_moves:
        child = board.copy();child.push(move)
        assert not child.is_checkmate()


def test_limits_and_invalid_suffix_preserve_only_completed_decisions():
    assert observe_game(sample(), 'x', max_operations=0)['status'] == 'unavailable'
    g = {'moves': ['e2e4','e7e5','g1f3'], 'color': 'white'}
    limited = observe_game(g, 'x', max_user_moves=1)
    assert limited['status'] == 'partial' and limited['coverage']['reason'] == 'user_move_limit'
    g['moves'] = ['e2e4', 'bad']
    result = observe_game(g, 'x')
    assert result['status'] == 'partial' and result['coverage']['processed_user_moves'] == 1
    assert observe_game({'initial_fen':'bad','moves':[],'color':'white'}, 'x')['status'] == 'unavailable'


def test_help_is_preserved_as_provenance_not_unassisted_success():
    g = sample();g['moves'] = [];b = chess.Board(FEN);ledger(g, complete=True)
    event(g,b,'hint',recommended='g6g7',source='fixture')
    record_move(g,b,chess.Move.from_uci('g6g7'));g['moves'].append('g6g7')
    row = observe_game(g,'x')['rows'][0]
    assert row['assistance']['hint_adopted'] is True
    assert row['assistance']['undo_replayed'] is False


def test_consecutive_same_kind_is_not_independent_evidence():
    g = {'initial_fen': FEN, 'moves':['g6f6','h8h7','f7f8'], 'color':'white'}
    result = observe_game(g,'x')
    assert len(result['rows']) == 2
    assert result['rows'][0]['group_id'] == result['rows'][1]['group_id']
    assert result['summary']['opportunities'] == 1
    assert result['summary']['excluded_duplicates'] == 1


def test_owned_endpoint_no_engine_no_writes_and_no_analysis_required(runtime,monkeypatch):
    server,(a,b) = runtime
    def forbidden(*args,**kwargs):raise AssertionError('extra engine call')
    monkeypatch.setattr(ga,'open_engine',forbidden)
    monkeypatch.setattr(chess.engine.SimpleEngine,'popen_uci',forbidden)
    state=server.get_state('RUNTIME-A');state['games']=[sample()]
    server.save_state('RUNTIME-A',state)
    before=copy.deepcopy(server.get_state('RUNTIME-A'));key=ga.game_key(state['games'][0])
    url='/api/games/observations/'+key
    assert b.get(url).status_code == 404
    result=a.get(url);assert result.status_code == 200,result.text
    assert result.json()['summary']['executed'] == 1
    assert a.get(url).json() == result.json()
    assert server.get_state('RUNTIME-A') == before
    assert a.get('/api/games/analysis').json()['games'][0]['status'] == 'not_started'
    with server.db() as conn:
        assert server.execute(conn,'SELECT * FROM game_analysis').fetchall() == []
