"""Static regression checks; run without python-chess."""
from pathlib import Path
from html.parser import HTMLParser
import ast, subprocess
ROOT=Path(__file__).parent
class P(HTMLParser):
    def __init__(self):super().__init__();self.src=[];self.ids=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='script' and 'src' in a:self.src.append(a['src'])
        if 'id' in a:self.ids.append(a['id'])
p=P();p.feed((ROOT/'public/index.html').read_text())
for src in p.src:
    assert src.startswith('/assets/')
    assert (ROOT/'public'/src.removeprefix('/assets/')).is_file(),src
assert len(p.ids)==len(set(p.ids)), 'duplicate IDs'
for f in ROOT.glob('*.py'):ast.parse(f.read_text())
for f in (ROOT/'public').glob('*.js'):
    run=subprocess.run(['node','--check',str(f)],capture_output=True,text=True)
    assert run.returncode==0,(f,run.stderr)
text=(ROOT/'public/extended.js').read_text()
fn=text[text.index('async function practiceClick(square){'):text.index("$('freshPuzzle').addEventListener")]
assert fn.index('const allowed=')<fn.index("await api('/practice/answer'")<fn.index('animateBoardTransition')
assert 'if(!allowed)' in fn and 'if(result.correct)' in fn
backend=(ROOT/'v7_server.py').read_text()
for route in ('/api/v7/game/hint','/api/v7/game/undo','/api/v7/review/variation'):
    assert route in backend
assert 'v7_server.py' in (ROOT/'Dockerfile').read_text()
print('PASS: all available static regression checks.')
print('UNTESTED: chess semantics and live server/UI integration.')
