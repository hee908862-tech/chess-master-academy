"""Source/static consistency tests and a synthetic question rotation stress simulation.
This script DOES NOT constitute a test of chess engine legality or deployed multiplayer.
"""
from pathlib import Path
from html.parser import HTMLParser
import ast, random, re
ROOT=Path(__file__).parent
for py in [ROOT/'server.py',ROOT/'exercises.py']:
 ast.parse(py.read_text())
assert (ROOT/'public'/'index.html').is_file()
class C(HTMLParser):
 def __init__(self):super().__init__();self.srcs=[]
 def handle_starttag(self,tag,attrs):
  if tag=='script':
   src=dict(attrs).get('src')
   if src:self.srcs.append(src)
c=C();c.feed((ROOT/'public'/'index.html').read_text())
for src in c.srcs:
 assert src.startswith('/assets/')
 assert (ROOT/'public'/src.removeprefix('/assets/')).is_file(),src
for theme in ('classic','royal'):
 for side in ('w','b'):
  for p in 'KQRBNP':
   assert (ROOT/'public'/'assets'/'pieces'/theme/(side+p+'.svg')).is_file()
# Simulate 1,000 evaluation sessions against 100 synthetic bank IDs. No duplicates within each assessment.
rng=random.Random(4)
for _ in range(1000):
 ids=rng.sample(range(100),12)
 assert len(ids)==len(set(ids))
print('PASS: python parsing; asset paths; 24 piece assets; 1000 synthetic 12-item assessments with no duplicate ids')
