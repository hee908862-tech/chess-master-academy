from test_runtime_isolation import runtime

def test_navigation_revalidates_without_forced_reload(runtime):
    server,(client,_)=runtime
    for path in ['/','/assets/guest-practice.js','/assets/focus-layout.css']:
        r=client.get(path)
        assert r.status_code==200
        assert r.headers['cache-control']=='no-cache'
        again=client.get(path,headers={'If-None-Match':r.headers['etag']})
        assert again.status_code in (200,304)
        assert again.headers['cache-control']=='no-cache'
