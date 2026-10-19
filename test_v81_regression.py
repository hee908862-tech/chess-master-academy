"""Static/isolated regression tests. Does not replace full server integration tests."""
from pathlib import Path
import ast, subprocess
from assessment_v8 import points, finalize, DOMAINS, DOMAIN_TAGS, questions, public_question
from v9_server import LIB
BASE=Path(__file__).resolve().parent

def check(condition, message):
    if not condition:raise AssertionError(message)

def run():
    py=[BASE/'server.py',BASE/'v7_server.py',BASE/'v8_server.py',BASE/'assessment_v8.py']
    for f in py:ast.parse(f.read_text(encoding='utf-8'))
    for f in (BASE/'public').glob('*.js'):
        subprocess.run(['node','--check',str(f)],check=True,capture_output=True)
    server=(BASE/'server.py').read_text()
    v7=(BASE/'v7_server.py').read_text()
    v8=(BASE/'v8_server.py').read_text()
    client=(BASE/'public/app.js').read_text()
    browser=(BASE/'public/v8.js').read_text()
    html=(BASE/'public/index.html').read_text()
    topics=[
      ('지원 진단 영역과 49개 실제 출제 계약', {x[0] for x in DOMAINS}=={'mate','defense','calculation','capture','tactics','strategy','endgame'} and len(DOMAINS)==7 and set(DOMAIN_TAGS)=={x[0] for x in DOMAINS}),
      ('진단 풀 수 종료 조건 삭제','count>=12' not in v8 and 'target_white_moves\':None' in v8),
      ('평가시간 10분+5초','600000' in v8 and '5000' in v8 and 'clock_started_at' in v8),
      ('일반대국 시계 규칙 4종',all(x in server for x in ("'unlimited'","'rapid'","'blitz'","'bullet'"))),
      ('앙파상 즉시 제거','const taken=s[0]+from[1]' in client),
      ('승률 계산 힌트 여부 보장',"g.get('hint_used') is False" in server),
      ('힌트 이용 표시',"g['hint_used']=True" in v7 and "hint_plies" in v7),
      ('복기 힌트 착수 하이라이트','hint-assisted' in (BASE/'public/v5.js').read_text()),
      ('유저 시간제한 선택','id="timeMode"' in html),
      ('프로필 승률 표시','id="gameModeStats"' in html),
      ('구현 누락 확인: 점수 공식','math.exp' in (BASE/'assessment_v8.py').read_text()),
    ]
    failures=[label for label,value in topics if not value]
    for label,value in topics:print('PASS' if value else 'FAIL',label)
    check(not failures, '; '.join(failures))
    items=questions(20261020)
    check(len(items)==49 and len({q['puzzle_id'] for q in items})==49,'49개 중복 없는 원본 문항')
    for domain,_,_ in DOMAINS:
        selected=[q for q in items if q['domain']==domain]
        check({q['difficulty'] for q in selected}==set(range(1,8)),domain+' 난이도 7개')
        check(all(set(LIB[q['puzzle_id']]['themes']) & set(DOMAIN_TAGS[domain]) for q in selected),domain+' 실제 원본 태그')
    check(all('answers' not in public_question(q) and 'mate_explanation' not in public_question(q) for q in items),'정답 사전 비공개')
    check(points(False,1,7)==0,'오답은 언제나 0점')
    check(points(True,5,7)==100,'정답 시간 보너스 제한')
    check(points(True,1000,7)>=92,'오래 걸려도 정답 중요')
    mock=[]
    for name,_,_ in DOMAINS:
        for diff in range(1,8):
            mock.append({'domain':name,'correct':True,'seconds':60.0,'points':points(True,60,diff),'difficulty':diff})
    result=finalize(mock,[0]*12,True,12)
    check(result['index']==1000,'최고점은 1000점')
    check(result['game_score']==100.0,'0cp 손실은 100점')
    check(finalize(mock,[0]*11,True,11)['game_score'] is None,'12개 미만 정확도 미포함')
    print(f'PASS: {len(topics)} structural checks + 6 score assertions + corpus/domain contracts + Python/JS parsers')

if __name__=='__main__':run()
