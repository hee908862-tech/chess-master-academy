"""Build a corpus-fingerprinted, policy-versioned diagnostic index before serving."""
import gzip
import hashlib
import json
import os
from pathlib import Path
from journey_server import build_inventory, DATA_FILE, INDEX_POLICY, INDEX_PATH


def build(path=INDEX_PATH):
    pools=build_inventory()
    items={p['puzzle_id']:p for rows in pools.values() for p in rows}
    data={'policy':INDEX_POLICY,'corpus_sha256':hashlib.sha256(DATA_FILE.read_bytes()).hexdigest(),
          'items':items,'pools':{c:[p['puzzle_id'] for p in rows] for c,rows in pools.items()}}
    path=Path(path);temporary=path.with_suffix(path.suffix+'.tmp')
    with gzip.open(temporary,'wt',encoding='utf8') as f:json.dump(data,f,ensure_ascii=False,separators=(',',':'))
    os.replace(temporary,path)
    print(json.dumps({'file':str(path),'unique_items':len(items),'bytes':path.stat().st_size}))

if __name__=='__main__':build()
