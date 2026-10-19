"""Controlled stale snapshots, SQLite transactions, and valid review input."""
import pytest
from fastapi import HTTPException
from test_review_assistance import api


def test_unrelated_stale_save_cannot_erase_new_puzzle(api):
    c,server=api
    old=server.get_state('HELP-QA')
    new=server.get_state('HELP-QA')
    new['v9_puzzle']={'session_id':'new-puzzle','done':False}
    server.save_state('HELP-QA',new)
    old['assessment_v8']={'phase':'questions','index':0}
    server.save_state('HELP-QA',old)
    final=server.get_state('HELP-QA')
    assert final['v9_puzzle']['session_id']=='new-puzzle'
    assert final['assessment_v8']==old['assessment_v8']
    assert final['games']==[]
    assert c.get('/api/games/history').status_code==200


def test_same_field_stale_save_rejects_and_rolls_back(api):
    _,server=api
    a=server.get_state('HELP-QA');b=server.get_state('HELP-QA')
    a['puzzle_results'].append({'id':'a'})
    b['puzzle_results'].append({'id':'b'});b['practice']={'must':'rollback'}
    server.save_state('HELP-QA',a)
    with pytest.raises(HTTPException) as caught:server.save_state('HELP-QA',b)
    assert caught.value.status_code==409
    saved=server.get_state('HELP-QA')
    assert saved['puzzle_results']==[{'id':'a'}] and saved['practice'] is None


def test_review_placeholder_has_friendly_validation(api):
    c,_=api
    r=c.get('/api/games/review/대국 불러오는 중')
    assert r.status_code==400 and '목록에서 선택' in r.json()['detail']
