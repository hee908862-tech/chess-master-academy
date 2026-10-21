import subprocess,os,json,time
from pathlib import Path
root=Path('/tmp/cma-focused-ui');os.chdir(root)
out=Path('/tmp/cma-focus-final');out.mkdir(exist_ok=True)
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
files=sorted(subprocess.check_output(['rg','--files','-g','test_*.py','-g','*_test.py'],text=True).splitlines())
# Balance whole files by previous measured duration; do not split stateful module fixtures.
import xml.etree.ElementTree as ET
weights={}
for xml in Path('/tmp/cma-focus-full').glob('suite-*.xml'):
 for c in ET.parse(xml).findall('.//testcase'):
  name=c.attrib['classname'].replace('.','/')+'.py'
  weights[name]=weights.get(name,0)+float(c.attrib.get('time','0'))
suites=[[] for _ in range(4)];totals=[0]*4
for name in sorted(files,key=lambda f:weights.get(f,20),reverse=True):
 i=min(range(4),key=lambda j:totals[j]);suites[i].append(name);totals[i]+=weights.get(name,20)
assert len(set(sum(suites,[])))==len(files)
assert 'tests/test_image_runtime_package.py' in files
start=time.monotonic();procs=[];logs=[]
manifest={'head':head,'files':files,'suites':suites,'browser':'normal Chromium','status':'running'}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
for i,paths in enumerate(suites):
 log=open(out/f'suite-{i}.log','w');logs.append(log)
 env={**os.environ,'PYTHONPATH':'.:tests:docs/qa-board-centered-feedback','STOCKFISH_PATH':'/tmp/stockfish/stockfish-ubuntu-x86-64-avx2','CMA_JOURNEY_INDEX':'/tmp/chess-journey-index.json.gz','DATABASE_URL':'','SQLITE_FILE':str(out/f'isolated-{i}.sqlite')}
 env.pop('CMA_LOW_RESOURCE',None)
 procs.append(subprocess.Popen(['/tmp/chess-venv/bin/python','-m','pytest','-p','cma_reap_tests','-q','-rs',f'--junitxml={out}/suite-{i}.xml',*paths],stdout=log,stderr=subprocess.STDOUT,env=env))
manifest['pids']=[p.pid for p in procs];(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
results=[p.wait() for p in procs]
for f in logs:f.close()
manifest.update(exit_codes=results,elapsed_seconds=round(time.monotonic()-start,2),status='complete')
(out/'manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps({k:v for k,v in manifest.items() if k not in ('files','suites')}))
