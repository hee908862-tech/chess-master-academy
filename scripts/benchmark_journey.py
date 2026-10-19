"""Local-only cold/warm benchmark using real server db/auth and temporary SQLite."""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    with tempfile.TemporaryDirectory(prefix='chess-benchmark-') as folder:
        os.environ['DATABASE_URL']='';os.environ['SQLITE_FILE']=str(Path(folder)/'benchmark.sqlite')
        from fastapi.testclient import TestClient
        import server
        import journey_server as journey
        clients=[]
        for name in ['COLD','OBSERVER','WARM']:
            c=TestClient(server.app)
            r=c.post('/api/register',json={'code':'BENCH-'+name,'pin':'local-bench-9384'})
            assert r.status_code==200,r.text
            c.headers['Authorization']='Bearer '+r.json()['token'];clients.append(c)
        server.DB_TIMINGS.clear()
        entering=threading.Event();durations=[];original=journey.inventory
        def inventory():
            entering.set();begin=time.perf_counter()
            try:return original()
            finally:durations.append(time.perf_counter()-begin)
        journey.inventory=inventory
        def measured(client,method,path,body=None):
            begin=time.perf_counter();r=client.request(method,path,json=body)
            return {'path':path,'seconds':round(time.perf_counter()-begin,4),'status':r.status_code}
        with ThreadPoolExecutor(max_workers=4) as pool:
            cold=pool.submit(measured,clients[0],'POST','/api/journey/start',{})
            assert entering.wait(30),'inventory entry timeout'
            probes=[pool.submit(measured,clients[1],method,path,body) for method,path,body in
                    [('GET','/api/me',None),('GET','/api/onboarding',None),('POST','/api/game/new',{'color':'white'})]]
            result={'cold':cold.result(),'concurrent':[p.result() for p in probes]}
        result['warm']=measured(clients[2],'POST','/api/journey/start',{})
        result['inventory_work_seconds']=round(max(durations),4)
        result['db_metrics']={field:{'max_ms':max(values,default=0),'count':len(values)} for field in ['connect_ms','transaction_ms','wait_ms'] for values in [[t[field] for t in server.DB_TIMINGS if field in t]]}
        result['corpus_count']=len(journey.LIB)
        result['database']='temporary SQLite, production server.db/auth, in-process TestClient'
        print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
