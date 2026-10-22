"""Explicit real-engine run. Exits 2 when unavailable; never silently uses a test double."""
import argparse,json,pathlib,sys,time
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import chess
from growth_model import verify_loss
parser=argparse.ArgumentParser();parser.add_argument('--engine',required=True);args=parser.parse_args()
if not pathlib.Path(args.engine).is_file():
    print(json.dumps({'status':'blocked','reason':'real_engine_missing'}));sys.exit(2)
cases=[('bhYwD','d1d2','2Q5/6pk/4p3/5p2/1P1PpP2/4P3/5KPp/2Rq4 b - - 1 47'),('EM5dO','f2f1','8/B6R/1P1p4/3k4/P7/6Pp/5rr1/4R2K b - - 3 40')]
corpus={r['id']:r for r in map(json.loads,open(pathlib.Path(__file__).resolve().parents[1]/'puzzles_lichess.jsonl'))}
for puzzle,move,fen in cases:
    row=corpus[puzzle];board=chess.Board(row['fen']);board.push_uci(row['moves'][0]);assert board.fen()==fen
    t=time.monotonic();result=verify_loss(fen,move,args.engine)
    print(json.dumps({'puzzle_id':puzzle,'corpus_fen':row['fen'],'analysis_fen':fen,'move':move,'caller_elapsed_ms':round((time.monotonic()-t)*1000,3),'evidence':result},ensure_ascii=False))
