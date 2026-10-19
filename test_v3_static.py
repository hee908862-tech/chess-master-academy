"""Static checks only. Does not replace integration tests with python-chess and browser."""
import ast, pathlib, re
from html.parser import HTMLParser
root=pathlib.Path(__file__).parent
for name in ('server.py','exercises.py','assessment_v3.py','lesson_scenarios.py','validation.py'):
    ast.parse((root/name).read_text())
class Scripts(HTMLParser):
    src=[]
    def handle_starttag(self,tag,attrs):
        if tag=='script':
            s=dict(attrs).get('src')
            if s:self.src.append(s)
parser=Scripts();parser.feed((root/'public/index.html').read_text())
required=['board-tools.js','app.js','extended.js','v4.js','v5.js','v6.js','v7.js','mate-explanation.js','v8.js','v9.js','learning.js']
assert len(parser.src)==len(set(parser.src)), '중복 script 실행 금지'
positions=[parser.src.index('/assets/'+name) for name in required]
assert positions==sorted(positions), '필수 모듈의 의존 순서'
assert all(s.startswith('/assets/') for s in parser.src), '로컬 배포 script 경로'
for s in parser.src:assert (root/'public'/s.removeprefix('/assets/')).exists()
ui=(root/'public/extended.js').read_text()
app=(root/'public/app.js').read_text()
server=(root/'server.py').read_text()
assert 'guidedSelected===s' in ui and 'v3Selected===s' in ui and 'practiceSelected===square' in ui
assert 'selectedGame===s' in app and 'selectedPuzzle===s' in app
for path in ('/api/assessment-v3/start','/api/assessment-v3/answer','/api/assessment-v3/game-move','/api/guided/move'):
    assert path in server,path
assert 'moveTargets' in ui and 'targets:guidedSelected' in ui and 'targets:v3Selected' in ui
for theme in ('classic','royal'):
    for color in ('w','b'):
        for piece in 'KQRBNP':assert (root/f'public/assets/pieces/{theme}/{color}{piece}.svg').is_file()
print('PASS: Python parse, script paths, engine assets, UI action bindings and server endpoints.')
print('NOT RUN: actual chess move legality, multi-device account sync, full browser rendering.')
