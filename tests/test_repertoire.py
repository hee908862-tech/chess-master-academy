import copy
from concurrent.futures import ThreadPoolExecutor
import chess
import pytest
from test_runtime_isolation import runtime
from repertoire_server import KEY
from repertoire_content import CORE, lesson, explanation
from study_server import courses


def post(client,data,action,**kw):
    return client.post('/api/repertoire/action',json={'action':action,'revision':data['revision'],'attempt_id':(data.get('active') or {}).get('id'),**kw})
def start(client,course='london-core',mode='recall',side='white'):
    data=client.get('/api/repertoire').json();data=post(client,data,'select',selected=[course]).json()
    r=post(client,data,'start',lesson_id=course,mode=mode,side=side);assert r.status_code==200,r.text;return r.json()
def complete(client,data,alternate=False):
    while data['active']['phase']=='playing':
        r=data['active'];l=lesson(r['lesson_id']);lines=[line for line in l['branches'].values() if line[:len(r['moves'])]==r['moves']]
        u=lines[-1 if alternate else 0][len(r['moves'])]
        response=post(client,data,'move',move=u);assert response.status_code==200,response.text;data=response.json()
    return data

@pytest.mark.parametrize('course',CORE)
def test_all_core_branches_positions_and_position_facts(course):
    for line in lesson(course)['branches'].values():
        b=chess.Board()
        for i,u in enumerate(line):
            assert chess.Move.from_uci(u) in b.legal_moves
            ex=explanation(course,line[:i]);assert ex['in_check']==b.is_check()
            for row in ex['attacks']:
                sq=chess.parse_square(row['from'])
                for target in row['targets']:assert chess.parse_square(target) in b.attacks(sq)
            b.push_uci(u);assert b.is_valid()
    assert len(courses())==55

def at(course,ply):
    b=chess.Board()
    for u in lesson(course)['branches']['main'][:ply]:b.push_uci(u)
    return b

def test_authored_geometry_claims():
    for c,p in [('london-core',8),('london-early-c5',4),('jobava-c5',6)]:assert chess.D4 in at(c,p).attacks(chess.C5)
    for c,p in [('london-core',12),('jobava-exchange',8),('jobava-a6',10)]:assert chess.F4 in at(c,p).attacks(chess.D6)
    b=at('london-qb6',10);assert chess.B2 in b.attacks(chess.B6) and chess.D4 not in b.attacks(chess.B6) and chess.D4 in b.attacks(chess.C5)
    assert chess.B3 in at('london-qb6',12).attacks(chess.C4)
    b=at('london-g6',8);assert b.piece_at(chess.F6).symbol()=='n' and chess.D4 not in b.attacks(chess.G7)
    b=at('london-g6',4);assert chess.F5 in b.attacks(chess.G6) and chess.H5 in b.attacks(chess.G6) and chess.D3 not in b.attacks(chess.G6)
    b=at('jobava-exchange',4);assert chess.E4 in b.attacks(chess.C3);assert chess.Move.from_uci('c2c3') not in b.legal_moves and chess.Move.from_uci('c2c4') not in b.legal_moves
    assert chess.B5 in at('jobava-a6',6).attacks(chess.A6)

@pytest.mark.parametrize('side',['white','black'])
def test_recall_completion_alternative_no_other_state_changes(runtime,side):
    server,(a,b)=runtime;before=copy.deepcopy(server.get_state('RUNTIME-A'));data=start(a,side=side)
    assert data['active']['options']==[] and data['active']['guidance'] is None
    data=complete(a,data,alternate=True)
    assert data['active']['phase']=='complete'
    if side=='white':assert data['active']['branch_ids']==['bishop-exchange']
    assert data['metrics']['london-core']['first_recall']['clean']
    assert data['metrics']['london-core']['first_recall']['side']==side
    after=dict(server.get_state('RUNTIME-A'));after.pop(KEY);assert after==dict(before)
    assert b.get('/api/repertoire').json()['active'] is None
    assert post(a,data,'move',move='a2a3').status_code==409


def test_hint_deviation_retry_preserved_and_stale_duplicate(runtime):
    server,(a,b)=runtime;data=start(a)
    data=post(a,data,'hint').json();assert data['active']['options'][0]['move']=='d2d4'
    data=post(a,data,'move',move='e2e4').json();assert data['active']['moves']==[] and data['active']['deviations']==1
    old=copy.deepcopy(data);data=post(a,data,'retry').json()
    assert data['active']['hints']==1 and data['active']['deviations']==1
    assert data['active']['weak_points'][0]['moves']==[]
    assert data['active']['guidance'] is None and data['active']['options']==[]
    assert not data['metrics']['london-core']['first_recall']['clean']
    assert post(a,old,'hint').status_code==409
    data=complete(a,data);data=post(a,data,'finish').json()
    assert len(data['history'])==2
    history=a.get('/api/repertoire/history/'+data['history'][0]['id']).json()
    assert history['events'][0]['kind']=='hint' and history['events'][1]['move']=='e2e4'
    assert b.get('/api/repertoire/history/'+history['id']).status_code==404
    again=post(a,data,'start',lesson_id='london-core',mode='recall').json()
    assert again['metrics']['london-core']['hints']==1 and not again['metrics']['london-core']['first_recall']['clean']


def test_weak_resume_illegal_save_failure_and_version_change(runtime,monkeypatch):
    server,(a,b)=runtime;data=start(a);data=post(a,data,'move',move='d2d4').json();data=post(a,data,'hint').json()
    before=copy.deepcopy(server.get_state('RUNTIME-A'))
    assert post(a,data,'move',move='e1e8').status_code==400
    assert server.get_state('RUNTIME-A')==before
    data=post(a,data,'weak').json();assert data['active']['start_ply']==2 and data['active']['moves']==['d2d4','d7d5']
    assert a.get('/api/repertoire').json()==data
    data=post(a,data,'retry').json();assert data['active']['moves']==[]
    data=post(a,data,'weak').json();assert data['active']['moves']==['d2d4','d7d5']
    from fastapi import HTTPException
    original=server.save_state
    monkeypatch.setattr(server,'save_state',lambda *args:(_ for _ in ()).throw(HTTPException(503,'test save failure')))
    assert post(a,data,'hint').status_code==503
    monkeypatch.setattr(server,'save_state',original)
    assert a.get('/api/repertoire').json()==data
    import repertoire_server as module
    original_lesson=module.lesson
    monkeypatch.setattr(module,'lesson',lambda k:{**original_lesson(k),'version':'changed'})
    changed=a.get('/api/repertoire').json();assert changed['active']['outdated'] and not changed['active']['legal']
    assert post(a,data,'move',move='c1f4').status_code==409
    assert post(a,changed,'finish').status_code==200


def test_concurrent_revision_and_bounds(runtime):
    server,(a,b)=runtime;data=start(a)
    with ThreadPoolExecutor(2) as pool:
        rs=list(pool.map(lambda _:post(a,data,'hint'),range(2)))
    assert sorted(r.status_code for r in rs)==[200,409]
    current=a.get('/api/repertoire').json();assert current['metrics']['london-core']['hints']==1
    assert post(a,current,'select',selected=['x']*17).status_code==422
    state=server.get_state('RUNTIME-A');state[KEY]['active']['events']=[{'kind':'hint','ply':0}]*256;server.save_state('RUNTIME-A',state)
    current=a.get('/api/repertoire').json();assert post(a,current,'hint').status_code==409


@pytest.mark.parametrize('action',['finish','retry'])
def test_first_incomplete_recall_side_and_legacy_unknown_preserved(runtime,action):
    server,(a,b)=runtime;data=start(a,side='black')
    data=post(a,data,action).json()
    first=data['metrics']['london-core']['first_recall']
    assert first['side']=='black' and not first['completed']
    state=server.get_state('RUNTIME-A');state[KEY]['metrics']['london-core']['first_recall'].pop('side');server.save_state('RUNTIME-A',state)
    before=copy.deepcopy(server.get_state('RUNTIME-A'))
    loaded=a.get('/api/repertoire').json()
    assert 'side' not in loaded['metrics']['london-core']['first_recall']
    assert server.get_state('RUNTIME-A')==before


@pytest.mark.parametrize('count',[63,64])
@pytest.mark.parametrize('phase',[None,'playing','complete'])
@pytest.mark.parametrize('action',['start','retry','finish','move'])
def test_archive_boundary_matrix_preserves_and_allows_exit(runtime,count,phase,action):
    server,(a,b)=runtime;data=start(a);state=server.get_state('RUNTIME-A');s=state[KEY]
    template=copy.deepcopy(s['active']);template.update(phase='complete',moves=lesson('london-core')['branches']['main'],recorded=True)
    s['history']=[{**copy.deepcopy(template),'id':f'archived-{i}'} for i in range(count)]
    if phase is None:s['active']=None
    elif phase=='complete':s['active']=copy.deepcopy(template)
    server.save_state('RUNTIME-A',state);before=copy.deepcopy(server.get_state('RUNTIME-A'));data=a.get('/api/repertoire').json()
    result=post(a,data,action,lesson_id='london-core',mode='recall',move='d2d4')
    expected=200 if (action=='start' and phase is None and count==63) or (action=='finish' and phase is not None) or (action=='move' and phase=='playing') else 409
    assert result.status_code==expected,result.text
    saved=server.get_state('RUNTIME-A')[KEY]
    assert saved['history'][:count]==before[KEY]['history']
    if expected==409:assert server.get_state('RUNTIME-A')==before
    if action=='finish' and expected==200:
        out=result.json();assert out['active'] is None and not out['can_start']
        assert len(out['history'])==count+1
        assert out['retained_legacy_attempt']==(count==64)
        assert a.get('/api/repertoire/history/'+template['id']).status_code==200
        assert a.get('/api/repertoire').json()==out
    if action=='start' and expected==200:
        assert post(a,result.json(),'finish').status_code==200


def test_event_and_byte_limits_preserve_normal_finish(runtime,monkeypatch):
    import json
    import repertoire_server as module
    server,(a,b)=runtime;data=start(a)
    state=server.get_state('RUNTIME-A');s=state[KEY];s['active']['events']=[{'kind':'hint','ply':0,'fen':chess.STARTING_FEN}]*256
    server.save_state('RUNTIME-A',state);data=a.get('/api/repertoire').json();before=copy.deepcopy(server.get_state('RUNTIME-A'))
    for action in ['hint','move']:assert post(a,data,action,move='d2d4').status_code==409
    assert server.get_state('RUNTIME-A')==before
    assert post(a,data,'finish').status_code==200
    data=start(a)
    state=server.get_state('RUNTIME-A');s=state[KEY]
    # Exact real 1MiB persisted boundary, including a fixture-only inert padding field.
    s['padding']='';current=len(json.dumps(s,ensure_ascii=False).encode());s['padding']='x'*(module.MAX_BYTES-current)
    assert len(json.dumps(s,ensure_ascii=False).encode())==module.MAX_BYTES
    server.save_state('RUNTIME-A',state);data=a.get('/api/repertoire').json();before=copy.deepcopy(server.get_state('RUNTIME-A'))
    assert post(a,data,'hint').status_code==409
    assert server.get_state('RUNTIME-A')==before
    out=post(a,data,'finish');assert out.status_code==200,out.text
    assert out.json()['active'] is None
    assert server.get_state('RUNTIME-A')[KEY]['padding']==before[KEY]['padding']
