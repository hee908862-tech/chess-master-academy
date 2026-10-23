"""All-defense rule proof; separate from Stockfish heuristic evidence."""
import copy,json,sqlite3
import chess
from growth_model import prove_mate_alternative,ANSWER_POLICY
from test_learning import setup
from test_journey import attach,post,act,saved

FEN='7k/8/5K2/8/6Q1/8/8/8 w - - 0 1'
LINE=['g4g3','h8h7','g3g7']
ITEM={'fen':FEN,'line':LINE,'tags':['mateIn2']}


def test_all_defenses_proved_and_original_immutable():
    before=copy.deepcopy(ITEM)
    evidence=prove_mate_alternative(FEN,'f6g6',ITEM)
    assert evidence['status']=='verified_goal' and evidence['basis']=='all_legal_defenses'
    b=chess.Board(FEN);b.push_uci('f6g6')
    for u in evidence['continuation']:assert chess.Move.from_uci(u) in b.legal_moves;b.push_uci(u)
    assert b.is_checkmate() and ITEM==before


def test_longer_win_is_not_original_one_move_mate():
    one={'fen':FEN,'line':['g4g7'],'tags':['mateIn1']}
    r=prove_mate_alternative(FEN,'g4g3',one)
    assert r['status']=='verified_non_mate' and r['remaining_own_moves']==1


def test_budget_unknown_and_nonmate_objective_not_invented():
    assert prove_mate_alternative(FEN,'f6g6',ITEM,max_nodes=1)['reason']=='mate_proof_budget'
    assert prove_mate_alternative(FEN,'f6g6',{**ITEM,'tags':['advantage','endgame']}) is None


def install(setup,policy=True):
    c,ns,old,path=attach(setup);post(c,'start',{'mode':'balanced'})
    state=saved(path);s=state['active'];row=s['items'][0]
    row.update(ITEM,competency='mate',puzzle_id='local-rule-proof',position_keys=[])
    s.update(index=0,fen=FEN,offset=0,correct=0,submitted=[],played=[],phase='question')
    if policy:s['answer_policy']=ANSWER_POLICY
    else:s.pop('answer_policy',None)
    with sqlite3.connect(path) as db:db.execute("UPDATE journey_progress SET state=? WHERE code='A'",(json.dumps(state),))
    return c,s,path


def test_api_proven_branch_resume_and_original_record_preserved(setup):
    c,s,path=install(setup)
    r=act(c,s,'move','f6g6')
    assert r['phase']=='question' and r['question']['ply']==1
    stored=saved(path)['active'];assert stored['items'][0]['line']==LINE
    assert stored['answer_line']!=LINE and stored['items'][0]['alternative_evidence'][0]['status']=='verified_goal'
    resumed=c.get('/api/journey').json()['active'];assert resumed==r
    final=act(c,resumed,'move',stored['answer_line'][-1])
    assert final['feedback']['complete'] and final['feedback']['execution_rubric']['confirmed_own_moves']==2
    row=saved(path)['active']['items'][0]
    assert row['line']==LINE and row['expected']==LINE[::2] and row['submitted'][0]=='f6g6'
    assert final['feedback']['replay']['frames'][0]['fen']==FEN


def test_old_session_retains_old_policy_and_no_silent_credit(setup):
    c,s,path=install(setup,False)
    r=act(c,s,'move','f6g6')
    assert r['feedback']['outcome']=='unverified_alternative'
    assert 'execution_rubric' not in r['feedback'] and 'answer_line' not in saved(path)['active']


def test_partial_execution_is_observation_not_arbitrary_half_score(setup):
    c,s,path=install(setup)
    r=act(c,s,'move','f6g6');r=act(c,r,'skip')
    rubric=r['feedback']['execution_rubric']
    assert rubric['confirmed_own_moves']==1 and rubric['partial_score'] is None and not rubric['objective_complete']
    assert r['feedback']['outcome']=='partial_execution'


def test_proof_covers_multiple_legal_defenses_not_just_stored_reply():
    fen='7k/8/5K1p/8/6Q1/8/8/8 w - - 0 1'
    item={**ITEM,'fen':fen}
    r=prove_mate_alternative(fen,'g4g2',item)
    assert r['status']=='verified_goal'
    b=chess.Board(fen);b.push_uci('g4g2')
    defenses=list(b.legal_moves);assert len(defenses)==2
    # Independent one-ply exhaustive check of both defender branches.
    for defense in defenses:
        after=b.copy();after.push(defense)
        assert any(_push(after,m).is_checkmate() for m in after.legal_moves)


def _push(board,move):
    result=board.copy();result.push(move);return result
