import json
from pathlib import Path
import chess
from build_guest_examples import payload

def test_public_examples_exactly_match_verified_existing_content():
 data=json.loads(Path('public/guest-examples.json').read_text())
 assert data==payload() and len(data['examples'])==3
 for task in data['examples']:
  b=chess.Board(task['fen']);assert b.is_valid()
  assert set(task['moves'])=={m.uci() for m in b.legal_moves}
  for u,r in task['moves'].items():
   after=b.copy();after.push_uci(u);assert r['fen']==after.fen()
   assert r['checkmate']==after.is_checkmate()
   assert r['accepted']==(after.is_checkmate() if task['puzzle'] else u==task['answer'])
  assert task['moves'][task['answer']]['accepted']
