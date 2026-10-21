"""Cross-check presentation attacks against python-chess, with explicit move contracts."""
import json,random,subprocess
from pathlib import Path
import chess
ROOT=Path(__file__).resolve().parents[1]
SETUP="""global.window=global;global.document={addEventListener(){}};global.addEventListener=()=>{};global.matchMedia=()=>({addEventListener(){}});require('./public/board-presentation.js');const rows=JSON.parse(require('fs').readFileSync(0,'utf8'));"""
def node(rows,expression):
    p=subprocess.run(['node','-e',SETUP+'process.stdout.write(JSON.stringify(rows.map('+expression+')));'],input=json.dumps(rows),text=True,capture_output=True,cwd=ROOT,check=True)
    return json.loads(p.stdout)
def pieces(b):return {chess.square_name(s):p.symbol() for s,p in b.piece_map().items()}
def test_checks_include_pinned_attackers_and_match_random_legal_positions():
    rng=random.Random(20261021);boards=[chess.Board('4k3/8/8/8/8/8/2K1r3/4R3 w - - 0 1')]
    for _ in range(30):
        b=chess.Board()
        for _ in range(80):
            boards.append(b.copy(stack=False))
            if b.is_game_over():break
            b.push(rng.choice(list(b.legal_moves)))
    actual=node([pieces(b) for b in boards],"b=>cmaBoardPresentation.checked(b).sort()")
    expected=[[chess.square_name(b.king(c)) for c in [chess.WHITE,chess.BLACK] if b.is_attacked_by(not c,b.king(c))] for b in boards]
    assert actual==[sorted(x) for x in expected]
def test_explicit_move_plans_castling_capture_ep_promotion_and_reverse():
    cases=[(chess.STARTING_FEN,'e2e4'),('4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1','e1g1'),('r3k2r/8/8/8/8/8/8/4K3 b kq - 0 1','e8c8'),('7k/8/8/3pP3/8/8/8/6K1 w - d6 0 2','e5d6'),('7k/P7/8/8/8/8/8/6K1 w - - 0 1','a7a8n'),('7k/8/8/8/n7/8/8/R5K1 w - - 0 1','a1a4')]
    rows=[]
    for fen,u in cases:
        b=chess.Board(fen);assert chess.Move.from_uci(u) in b.legal_moves
        before=pieces(b);b.push_uci(u);rows.append({'before':before,'after':pieces(b),'uci':u})
    plans=node(rows,"r=>({forward:cmaBoardPresentation.plan(r.before,r.after,r.uci),back:cmaBoardPresentation.plan(r.after,r.before,r.uci,true),absent:cmaBoardPresentation.plan(r.before,r.after,null)})")
    for (fen,u),p in zip(cases,plans):
        assert p['forward'] and p['back'] and p['absent'] is None
        assert p['forward'][0]['from']==u[:2] and p['back'][0]['to']==u[:2]
        assert len(p['forward'])==(2 if u in ('e1g1','e8c8') else 1)
    rows[0]['after']['a3']='Q'
    assert node(rows[:1],"r=>cmaBoardPresentation.plan(r.before,r.after,r.uci)")==[None]
