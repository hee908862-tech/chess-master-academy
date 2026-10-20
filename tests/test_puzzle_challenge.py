import copy
from concurrent.futures import ThreadPoolExecutor
import chess
import pytest
from fastapi.testclient import TestClient
from test_onboarding import api
from puzzle_challenge import attach_challenge,KEY,board

@pytest.fixture
def challenge(api):
 c,s=api;attach_challenge(c.app,vars(s));return c,s

def send(c,s,action,move=''):
 r=c.post('/api/challenge/action',json={'revision':s['revision'],'session_id':(s.get('active') or {}).get('id'),'action':action,'move':move})
 assert r.status_code==200,r.text
 return r.json()

def solve(c,server,s):
 while s['active']['phase']=='playing':
  run=server.get_state('INTRO-QA')[KEY]['active'];u=run['puzzles'][run['index']]['moves'][run['offset']]
  s=send(c,s,'move',u)
 return s

def test_whole_game_hints_restore_duplicate_no_credit(challenge):
 c,server=challenge;before=copy.deepcopy(dict(server.get_state('INTRO-QA')))
 initial=c.get('/api/challenge').json();assert initial['active'] is None
 assert dict(server.get_state('INTRO-QA'))==before
 s=send(c,initial,'start');assert len(server.get_state('INTRO-QA')[KEY]['active']['puzzles'])==10
 for i in range(10):
  if i==0:s=send(c,s,'hint');assert s['active']['hint']
  stale=copy.deepcopy(s);s=solve(c,server,s)
  r=c.post('/api/challenge/action',json={'revision':stale['revision'],'session_id':stale['active']['id'],'action':'hint'})
  assert r.status_code==409
  if i<9:s=send(c,s,'next')
 assert s['active']['score']==95 and s['active']['phase']=='ended'
 assert len(s['history'])==1 and s['history'][0]['hinted_solved']==1
 assert TestClient(c.app,headers=dict(c.headers)).get('/api/challenge').json()==s
 review=c.get('/api/challenge/review/'+s['active']['id']).json();assert len(review['items'])==10
 assert len(review['items'][0]['frames'])>=2
 after=dict(server.get_state('INTRO-QA'));after.pop(KEY);assert after==before
 # Replaying completion with a current revision cannot award score again.
 assert c.post('/api/challenge/action',json={'revision':s['revision'],'session_id':s['active']['id'],'action':'finish'}).status_code==409
 other=TestClient(c.app);t=other.post('/api/register',json={'code':'CHALLENGE-OTHER','pin':'local-only-pin'}).json()['token'];other.headers['Authorization']='Bearer '+t
 assert other.get('/api/challenge').json()['active'] is None
 assert other.get('/api/challenge/review/'+s['active']['id']).status_code==404
 assert TestClient(c.app).get('/api/challenge').status_code==401

def test_lives_illegal_moves_skip_and_new_game(challenge):
 c,server=challenge;s=send(c,c.get('/api/challenge').json(),'start')
 r=c.post('/api/challenge/action',json={'revision':s['revision'],'session_id':s['active']['id'],'action':'move','move':'a1a1'})
 assert r.status_code==400 and c.get('/api/challenge').json()==s
 for i in range(3):
  s=send(c,s,'next')
  assert s['active']['lives']==2-i
  if i<2:s=send(c,s,'next')
 assert s['active']['phase']=='ended' and s['active']['score']==0
 review=c.get('/api/challenge/review/'+s['active']['id']).json();assert len(review['items'])==3
 old=s['active']['id'];s=send(c,s,'start');assert s['active']['id']!=old and len(s['history'])==1

def test_simultaneous_submission_commits_once(challenge):
 c,server=challenge;s=send(c,c.get('/api/challenge').json(),'start')
 body={'revision':s['revision'],'session_id':s['active']['id'],'action':'next'}
 def req(_):return TestClient(c.app,headers=dict(c.headers)).post('/api/challenge/action',json=body).status_code
 with ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(req,range(2)))
 assert sorted(codes)==[200,409]
 assert c.get('/api/challenge').json()['active']['lives']==2

def test_promotion_ep_and_castling_snapshots(challenge):
 c,server=challenge
 examples=[('7k/P7/8/8/8/8/8/4K3 b - - 0 1',['h8g8','a7a8n']),('4k3/3p4/8/4P3/8/8/8/4K3 b - - 0 1',['d7d5','e5d6']),('4k3/8/8/8/8/8/8/4K2R b K - 0 1',['e8d8','e1g1'])]
 for fen,moves in examples:
  state=server.get_state('INTRO-QA');state[KEY]={'revision':0,'history':[]};server.save_state('INTRO-QA',state)
  s=send(c,c.get('/api/challenge').json(),'start');state=server.get_state('INTRO-QA');run=state[KEY]['active'];run['puzzles'][0]={'id':'rules','fen':fen,'moves':moves,'rating':1000,'themes':[]};server.save_state('INTRO-QA',state)
  s=c.get('/api/challenge').json();assert moves[1] in s['active']['legal'];s=send(c,s,'move',moves[1]);b=chess.Board(fen)
  for u in moves:b.push_uci(u)
  assert s['active']['fen']==b.fen() and s['active']['score']==10
