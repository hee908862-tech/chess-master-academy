"""Static packaging checks. No chess engine required; DO NOT call these full end-to-end tests."""
import ast,re,subprocess,sys
from pathlib import Path
p=Path(__file__).parent
for f in p.glob('*.py'):ast.parse(f.read_text(encoding='utf8'))
for f in (p/'public').glob('*.js'):
    r=subprocess.run(['node','--check',str(f)],capture_output=True,text=True)
    if r.returncode:raise AssertionError((f.name,r.stderr))
html=(p/'public'/'index.html').read_text()
ids=re.findall(r'\bid="([^"]+)"',html)
assert len(ids)==len(set(ids)),'duplicate ids'
for f in ['assessment_v8.py','v8_server.py','mate3_v8.py','server.py','Dockerfile','public/v8.js']:
    assert (p/f).exists(),f
for key in ['v8Start','v8Next','v8Overlay','v8Outcome','v8ScoreSummary','v8History','v8MateStart','v8MateBoard']:
    assert key in ids,key
assert 'assessment_v8.py mate3_v8.py' in (p/'Dockerfile').read_text()
print('정적 검사 통과. 체스 엔진/서버 통합 테스트는 별도 필요.')
