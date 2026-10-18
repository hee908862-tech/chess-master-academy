"""Short guided board exercises. Completion requires actual legal move sequence."""
import chess
SCENARIOS={
 'rules': [{'fen':'4k3/8/8/8/8/8/R7/4K3 w - - 0 1','answer':'a2a8','prompt':'룩을 움직여 상대 킹을 체크하세요.'}, {'fen':'4k3/8/8/8/8/8/5N2/4K3 w - - 0 1','answer':'f2d3','prompt':'나이트를 L자 형태로 이동하세요.'}],
 'capture':[{'fen':'4k3/8/8/3q4/8/8/3R4/4K3 w - - 0 1','answer':'d2d5','prompt':'룩으로 상대 퀸을 잡아 이득을 얻으세요.'},{'fen':'4k3/8/8/8/4q3/8/4R3/4K3 w - - 0 1','answer':'e2e4','prompt':'중요한 상대 기물을 포획하세요.'}],
 'tactics':[{'fen':'3qk2r/8/8/6N1/8/8/8/4K3 w - - 0 1','answer':'g5f7','prompt':'나이트를 움직여 퀸과 룩을 동시에 위협하는 포크를 만드세요.'},{'fen':'4k3/8/8/8/5q2/8/4N3/4K3 w - - 0 1','answer':'e2f4','prompt':'나이트로 상대 퀸을 포획하세요.'}],
 'calculation':[{'fen':'4k3/8/8/3q4/8/8/3R4/4K3 w - - 0 1','answer':'d2d5','prompt':'상대 기물을 잡을 수 있는 강제수를 계산하세요.'},{'fen':'4k3/8/8/8/5q2/8/4N3/4K3 w - - 0 1','answer':'e2f4','prompt':'다음 수의 기물 관계를 예상하고 퀸을 잡으세요.'}],
 'endgame':[{'fen':'7k/8/8/8/3P4/4K3/8/8 w - - 0 1','answer':'d4d5','prompt':'폰을 승격 방향으로 한 칸 전진시키세요.'},{'fen':'7k/8/8/3P4/8/4K3/8/8 w - - 0 1','answer':'d5d6','prompt':'왕이 지원하는 폰을 계속 전진시키세요.'}],
 'opening':[{'fen':'rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2','answer':'g1f3','prompt':'오프닝에서 나이트를 중앙으로 전개하세요.'},{'fen':'rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR w KQkq d6 0 2','answer':'b1c3','prompt':'중앙을 지키도록 나이트를 전개하세요.'}],
 'review':[{'fen':'4k3/8/8/8/5q2/8/4N3/4K3 w - - 0 1','answer':'e2f4','prompt':'복기: 왜 기물 포획을 놓치면 안 되는지 직접 확인하세요.'},{'fen':'4k3/8/8/3q4/8/8/3R4/4K3 w - - 0 1','answer':'d2d5','prompt':'복기: 지나친 수읽기보다 즉각적인 기물 획득을 찾으세요.'}]
}
# Drop invalid predefined moves at startup rather than silently accepting nonlegal lessons.
for key,scenes in SCENARIOS.items():
 for s in scenes:
  b=chess.Board(s['fen']); m=chess.Move.from_uci(s['answer'])
  assert b.is_valid() and m in b.legal_moves,(key,s)
