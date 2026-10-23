import gzip,json,collections,chess,hashlib
with gzip.open('journey-index.json.gz','rt') as f:d=json.load(f)
items=d['items'];pools=d['pools'];eligible={k:[p for p in ids if 600<=items[p]['rating']<1800] for k,ids in pools.items()}
generic={'opening','middlegame','endgame','short','long','veryLong','oneMove','advantage','crushing','equality','master','masterVsMaster','superGM','mate'}
def shape(p):
 b=chess.Board(p['fen']);m=chess.Move.from_uci(p['line'][0]);return (tuple(sorted(t for t in p['tags'] if t not in generic)),tuple(sorted(str(x) for x in b.piece_map().values())),(len(p['line'])+1)//2,b.piece_type_at(m.from_square),b.is_capture(m),b.gives_check(m))
result={'corpus_sha256':d['corpus_sha256'],'scope':'eligible 600<=rating<1800','areas':{},'overlap':{}}
for area,ids in eligible.items():
 sig=collections.defaultdict(list)
 for pid in ids:sig[shape(items[pid])].append(pid)
 examples=sorted(sig.values(),key=len,reverse=True)[:2]
 result['areas'][area]={'eligible':len(ids),'basic':sum(items[p]['rating']<1200 for p in ids),'applied':sum(items[p]['rating']>=1200 for p in ids),'structural_groups':len(sig),'largest_groups':[{'count':len(g),'examples':g[:3]} for g in examples]}
for a,x in eligible.items():
 for b,y in eligible.items():
  if a<b:result['overlap'][a+'+'+b]=len(set(x)&set(y))
print(json.dumps(result,ensure_ascii=False,indent=2))
