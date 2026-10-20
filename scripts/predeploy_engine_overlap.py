"""Opt-in disposable loopback PG + actual 512MiB app concurrency, never production."""
import json,os,secrets,time,subprocess,urllib.request,urllib.error
from urllib.parse import urlparse
import chess
import psycopg
url=os.environ.get('CMA_TEST_PG_URL','');parsed=urlparse(url)
if parsed.hostname not in ('127.0.0.1','localhost') or parsed.path!='/cma_predeploy':raise RuntimeError('Disposable loopback PG required')
BASE='http://127.0.0.1:18080/api/'
def request(path,body=None,token=None):
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    req=urllib.request.Request(BASE+path,None if body is None else json.dumps(body).encode(),headers)
    with urllib.request.urlopen(req,timeout=20) as response:return json.load(response)
def account():
    code='OVERLAP-'+secrets.token_hex(4).upper();return code,request('register',{'code':code,'pin':'temporary-overlap-pin'})['token']
def state(table,code):
    with psycopg.connect(url) as conn:return json.loads(conn.execute(f'SELECT state FROM {table} WHERE code=%s',(code,)).fetchone()[0])
def engines():
    text=subprocess.check_output(['docker','top','cma-predeploy-app','-eo','pid,comm'],text=True)
    return sum(line.split()[-1]=='stockfish' for line in text.splitlines())
code,a=account();_,b=account();diagnostic_code,c=account()
s=request('journey/start',{'mode':'balanced'},c)
for index,item in enumerate(state('journey_progress',diagnostic_code)['active']['items']):
    position=chess.Board(item['fen']);alternatives=[]
    for move in position.legal_moves:
        trial=position.copy();trial.push(move)
        if move.uci()!=item['line'][0] and not trial.is_game_over():alternatives.append(move.uci())
    if alternatives:break
assert alternatives
for _ in range(index):
    s=request('journey/action',{'session_id':s['session_id'],'revision':s['revision'],'action':'skip'},c)
    s=request('journey/action',{'session_id':s['session_id'],'revision':s['revision'],'action':'next'},c)
board=chess.Board();moves=[]
for san in 'e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7 Re1 b5 Bb3 d6 c3 O-O h3 Nb8 d4 Nbd7 c4 c6 Nc3 Qc7 cxb5 axb5 Be3 Bb7 Rc1 Rfe8 a3 Bf8 d5 c5 Nd2 Ba6 Bc2 Nb6 Bd3 c4 Be2 Nfd7'.split():
    move=board.parse_san(san);moves.append(move.uci());board.push(move)
assert len(moves)//2>=20
legacy=state('progress',code);legacy['games']=[{'moves':moves,'color':'white','termination':'resign','result':'loss','ended':'2026-10-20','assistance':{'version':1,'complete':True,'events':[]}}]
with psycopg.connect(url) as conn:conn.execute('UPDATE progress SET state=%s WHERE code=%s',(json.dumps(legacy),code))
key=request('games/analysis',token=a)['games'][0]['game_key'];request('games/analysis/'+key,{},a)
for _ in range(100):
    if engines()==1:break
    time.sleep(.02)
else:raise AssertionError('Background engine did not start')
start=time.monotonic()
try:request('game/new',{'color':'black','difficulty':5},b);raise AssertionError('Concurrent foreground engine should return retry')
except urllib.error.HTTPError as e:assert e.code==503 and e.headers['Retry-After']=='1'
foreground_seconds=time.monotonic()-start;assert foreground_seconds<2
start=time.monotonic();request('me',token=b);profile_seconds=time.monotonic()-start;assert profile_seconds<1
result=request('journey/action',{'session_id':s['session_id'],'revision':s['revision'],'action':'move','move':alternatives[0]},c)
assert result['feedback']['outcome']=='unverified_alternative'
assert engines()<=1
for _ in range(500):
    analysed=request('games/analysis',token=a)['games'][0]
    if analysed['status'] not in ('queued','running'):break
    time.sleep(.05)
assert analysed['status'] in ('complete','partial') and analysed['user_moves']>=20,analysed
retry=request('game/new',{'color':'black','difficulty':5},b);assert retry['board']['ply']==1
peak=int(subprocess.check_output(['docker','exec','cma-predeploy-app','cat','/sys/fs/cgroup/memory.peak'],text=True))
status=json.loads(subprocess.check_output(['docker','inspect','cma-predeploy-app','--format','{{json .State}}'],text=True))
assert status['Running'] and not status['OOMKilled']
print(json.dumps({'result':'PASS','conditions':'app 1 CPU/512MiB, one worker, PG 1 CPU/512MiB, 21 own moves background analysis overlaps alternative diagnosis and AI response',
                 'own_moves':analysed['user_moves'],'analysis_status':analysed['status'],'foreground_retry_seconds':foreground_seconds,'other_account_profile_seconds':profile_seconds,
                 'max_observed_engine_processes':1,'memory_peak_bytes':peak,'oom_killed':False,'foreground_retry_after_analysis':'PASS'},indent=2))
