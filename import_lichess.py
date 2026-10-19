"""Offline CC0 Lichess puzzle importer. Original download: https://database.lichess.org/#puzzles
Usage: python import_lichess.py path/to/lichess_db_puzzle.csv.zst
Dependency: system zstd command (or uncompressed .csv / .csv.gz).
One-pass bounded reservoir sample, random with reproducible seed for auditing.
"""
import csv, gzip, json, random, subprocess, sys, collections
from pathlib import Path

TAGS = {'mateIn1','mateIn2','mateIn3','mateIn4','mateIn5','fork','pin','skewer',
        'discoveredAttack','doubleCheck','defensiveMove','endgame','equality','advantage',
        'hangingPiece','trappedPiece','interference','quietMove','sacrifice','promotion',
        'zugzwang','backRankMate','clearance','deflection','attraction','overloading',
        'xRayAttack','intermezzo','underPromotion','exposedKing','capturingDefender'}
BANDS=[(600,950),(950,1200),(1200,1450),(1450,1700),(1700,1950),(1950,2250),(2250,2900)]
CAP=200

def main(path,out):
    rng=random.Random(20261019)
    seen=collections.Counter(); chosen={}
    p=Path(path)
    process=None
    if p.suffix=='.zst':
        process=subprocess.Popen(['zstd','-dc',str(p)],stdout=subprocess.PIPE)
        stream=__import__('io').TextIOWrapper(process.stdout,encoding='utf-8',newline='')
    elif p.suffix=='.gz':stream=gzip.open(p,'rt',encoding='utf-8',newline='')
    else:stream=open(p,'r',encoding='utf-8',newline='')
    try:
        for row in csv.DictReader(stream):
            try:
                rating=int(row['Rating']);pop=int(row['Popularity']);plays=int(row['NbPlays']);rd=int(row['RatingDeviation'])
                if pop<65 or plays<45 or rd>135 or not 600<=rating<2900:continue
                moves=row['Moves'].split(); tags=set(row['Themes'].split())&TAGS
                if len(moves)<2 or len(moves)>35 or len(moves)%2 or not tags:continue
                if not all(len(x) in (4,5) for x in moves):continue
                band=next(i for i,(lo,hi) in enumerate(BANDS) if lo<=rating<hi)
                item={'id':row['PuzzleId'],'fen':row['FEN'],'moves':moves,'rating':rating,
                      'themes':sorted(tags),'popularity':pop,'plays':plays}
                for tag in tags:
                    key=(tag,band);seen[key]+=1
                    bucket=chosen.setdefault(key,[])
                    if len(bucket)<CAP:bucket.append(item)
                    else:
                        j=rng.randrange(seen[key]);
                        if j<CAP:bucket[j]=item
            except (ValueError,KeyError,StopIteration):continue
    finally:
        stream.close()
        if process:
            code=process.wait()
            if code:raise RuntimeError('zstd 압축 해제 오류: '+str(code))
    unique={p['id']:p for bucket in chosen.values() for p in bucket}
    with open(out,'w',encoding='utf-8') as f:
        for item in sorted(unique.values(),key=lambda x:x['id']):f.write(json.dumps(item,ensure_ascii=False,separators=(',',':'))+'\n')
    print('원본 테마별 선별 수:',len(unique),'버킷 수:',len(chosen),'저장:',out)
    for key,n in sorted(seen.items()):
        if n<15:print('부족한 테마·난이도:',key,n)
if __name__=='__main__':
    if len(sys.argv)<2:raise SystemExit('사용법: python import_lichess.py lichess_db_puzzle.csv.zst [puzzles_lichess.jsonl]')
    main(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else str(Path(__file__).with_name('puzzles_lichess.jsonl')))
