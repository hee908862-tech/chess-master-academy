"""Run after dependencies are installed: python validate_v6.py"""
import chess
from curriculum_v6 import CATALOG,COURSES,classify

critical=('fork','pin','skewer','discovered','double')
for course in critical:
 assert len(CATALOG[course])>=4, f'{course}: too few valid scenes ({len(CATALOG[course])})'
count=0
for course,items in CATALOG.items():
 for p in items:
  b=chess.Board(p['fen']);m=chess.Move.from_uci(p['sample_move'])
  assert b.is_valid(),(course,'invalid FEN',p['fen'])
  assert m in b.legal_moves,(course,'illegal solution',p['sample_move'])
  ok,why=classify(b,m,p['objective'])
  assert ok,(course,'objective failed',p['sample_move'],why,p['fen'])
  count+=1
 print(f'{course}: {len(items)} verified objective scenes')
print(f'{count} total curated/mirrored scenes checked')
