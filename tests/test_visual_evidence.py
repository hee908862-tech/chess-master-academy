"""Read-only chess facts, eligibility boundaries and real-engine replay evidence."""
import copy
import os
import chess
import pytest
from diagnostic_replay import position_facts,replay_snapshot,evaluate_frame
from skill_index import cumulative_evidence
from foundation_content import BY_ID


def test_check_escape_and_mate_capture_are_legal_position_facts():
    f=position_facts(chess.Board(BY_ID['king-check']['steps'][1]['fen']))
    assert any(a['from']=='g8' and a['to']=='g1' and a['kind']=='threat' for a in f['arrows'])
    moves={a['square']:a for a in f['king_moves']}
    assert moves['f2']['legal'] and not moves['g2']['legal']
    f=position_facts(chess.Board('7k/6Q1/5K2/8/8/8/8/8 b - - 0 1'))
    assert f['ending']=='checkmate' and not f['responses']
    assert all(not a['legal'] for a in f['king_moves'])
    assert any(a['from']=='f6' and a['to']=='g7' and a['kind']=='protect' for a in f['arrows'])
    assert 'f6 킹' in f['squares']['g7']
    stalemate=position_facts(chess.Board('7k/5K2/6Q1/8/8/8/8/8 b - - 0 1'))
    assert stalemate['ending']=='stalemate' and stalemate['check_king'] is None


def test_replay_preserves_fen_rights_and_effects_without_mutation():
    for course,index in [('castling',0),('en-passant',0),('promotion',0)]:
        row=copy.deepcopy(BY_ID[course]['steps'][index]);old=copy.deepcopy(row)
        replay=replay_snapshot(row)
        assert replay['frames'][0]['fen']==row['fen']
        assert replay['frames'][1]['effects'] and row==old
    row={'fen':chess.STARTING_FEN,'line':['e2e4','e7e5']}
    assert replay_snapshot(row)['frames'][1]['fen'].split()[3]=='e3'
    assert not replay_snapshot({'fen':chess.STARTING_FEN,'line':['e2e5']})['available']


def report(items,**kw):
    return dict(items=items,score_version='skill-index-v1',version='journey-v5',competency_version='competency-v2',measurement_scope='broad_area_execution_v1',corpus_sha256='sample',mode='balanced',**kw)


def sample():
    return dict(puzzle_id='one',fen=BY_ID['rook-bishop']['steps'][0]['fen'],line=['a1a4'],competency='mate',band=[600,1200],app_new=True,first_attempt=True,helped=False,outcome='completed')


def test_cumulative_duplicate_assistance_unknown_and_version_isolation():
    item=sample();original=report([item]);before=copy.deepcopy(original)
    e=cumulative_evidence([original,copy.deepcopy(original)])
    assert e['valid']==1 and e['excluded']['duplicate_position_or_line']==1
    assert not e['ready'] and e['areas_observed']==1 and e['areas_ready']==0
    assert e['missing']==47 and e['minimum_comprehensive_sessions']==2 and original==before
    for changes in [{'helped':True},{'outcome':'partial_execution'},{'outcome':'not_answered'},{'outcome':'unverified_alternative'},{'first_attempt':False},{'app_new':False}]:
        assert cumulative_evidence([report([{**item,**changes}])])['valid']==0
    for changes in [{'version':'journey-v4'},{'mode':'subskill'},{'measurement_scope':'uncued_execution'}]:
        assert cumulative_evidence([{**original,**changes}])['valid']==0
    assert cumulative_evidence([original,{**report([]),'corpus_sha256':'new'}])['valid']==0


def test_all_area_and_both_bands_are_required_even_if_total_met():
    item=sample();e=cumulative_evidence([report([item])],{'version':'test','per_band':1,'per_area':1,'total':1})
    assert not e['ready'] and e['missing']>0


def test_real_stockfish_white_orientation_and_terminal_not_zero():
    path=os.environ.get('STOCKFISH_PATH','')
    if not os.path.isfile(path):pytest.skip('actual Stockfish unavailable')
    e=evaluate_frame('7k/6Q1/5K2/8/8/8/8/8 b - - 0 1',path)
    assert e['status']=='mate' and e['winner']=='white' and 'cp_white' not in e
    e=evaluate_frame(chess.STARTING_FEN,path)
    assert e['status']=='analysed' and isinstance(e['cp_white'],int) and 'Stockfish' in e['basis']
    assert evaluate_frame(chess.STARTING_FEN,'')['status']=='unavailable'

from test_learning import setup
from test_journey import attach,post,act,saved


def test_replay_evaluation_is_owner_only_after_submission_without_writes(setup):
    c,ns,old,path=attach(setup)
    s=post(c,'start',{'mode':'domain','competency':'mate'})
    assert s['version']=='journey-v5' and s['measurement_scope']=='broad_area_execution_v1'
    row=saved(path)['active']['items'][0]
    url=f"/api/journey/replay-evaluation/{s['session_id']}/{row['id']}/0"
    assert c.get(url).status_code==404
    s=act(c,s,'skip');before=saved(path)
    assert c.get(url,headers={'Authorization':'B'}).status_code==404
    assert c.get(url).status_code==200
    assert c.get(url+'/999').status_code==404
    assert saved(path)==before
    assert s['feedback']['replay']['frames'][0]['fen']==row['fen']


def test_old_inflight_session_keeps_hidden_area_and_scores(setup):
    import json,sqlite3
    c,ns,old,path=attach(setup);s=post(c,'start',{'mode':'balanced'})
    state=saved(path);state['active']['version']='journey-v4';state['active']['measurement_scope']='uncued_execution'
    with sqlite3.connect(path) as db:db.execute("UPDATE journey_progress SET state=? WHERE code='A'",(json.dumps(state),))
    before=saved(path);restored=c.get('/api/journey').json()['active']
    assert 'label' not in restored['question'] and 'competency' not in restored['question']
    assert saved(path)==before
    next_state=act(c,restored,'skip');assert next_state['version']=='journey-v4'


def test_complete_cumulative_blueprint_requires_48_unique_real_corpus_lines():
    from journey_server import inventory
    from competencies import line_positions
    rows=[];seen=set();ids=set()
    for area,pool in inventory().items():
        for band in [(600,1200),(1200,1800)]:
            picked=0
            for row in pool:
                if not band[0]<=row['rating']<band[1] or row['puzzle_id'] in ids:continue
                footprint=line_positions(row['fen'],row['line'])
                if seen.intersection(footprint):continue
                rows.append({**row,'competency':area,'band':list(band),'app_new':True,'first_attempt':True,'helped':False,'outcome':'completed'})
                seen.update(footprint);ids.add(row['puzzle_id']);picked+=1
                if picked==4:break
            assert picked==4
    before=copy.deepcopy(rows);e=cumulative_evidence([report(rows)])
    assert e['ready'] and e['valid']==48 and e['areas_ready']==6 and e['missing']==0
    assert rows==before


def test_en_passant_removes_the_checker_not_blocks_the_attack():
    b=chess.Board('7k/8/8/3pP3/4K3/8/8/8 w - d6 0 2')
    assert b.is_valid() and b.is_check() and chess.Move.from_uci('e5d6') in b.legal_moves
    assert '체크 기물 잡기' in position_facts(b)['responses']
    assert '공격선 막기' not in position_facts(b)['responses']
