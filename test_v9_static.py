"""Offline checks, not gameplay certification."""
from pathlib import Path
from html.parser import HTMLParser
root=Path(__file__).parent
class C(HTMLParser):
 def __init__(self):super().__init__();self.ids=set();self.duplicates=[];self.scripts=[]
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  if 'id' in d:
   if d['id'] in self.ids:self.duplicates.append(d['id'])
   self.ids.add(d['id'])
  if tag=='script' and d.get('src'):self.scripts.append(d['src'])
x=C();x.feed((root/'public/index.html').read_text())
assert not x.duplicates,x.duplicates
for name in ['v9PuzzleBoard','v9CourseBoard','v9CourseCards','v9CourseLevel','v9PuzzleStart','v9CourseStart','v9CourseNext','v9PuzzleNext']:
 assert name in x.ids,name
assert '/assets/v9.js' in x.scripts
assert 'v9_server.py' in (root/'Dockerfile').read_text()
assert 'puzzles_lichess.jsonl' in (root/'Dockerfile').read_text()
assert (root/'puzzles_lichess.jsonl').exists()
print('v9 정적 UI·파일 검사 통과 (실제 대국 검증 아님)')
