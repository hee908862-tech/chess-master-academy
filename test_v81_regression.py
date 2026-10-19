"""Static/isolated regression tests. Does not replace full server integration tests."""
from pathlib import Path
import ast, subprocess, sys, types
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
      ("7개 영역 중 메이트 한 영역", "('mate','체크메이트 패턴','mate')" in (BASE/'assessment_v8.py').read_text() and "('king','킹 안전과 기물 보존','capture')" in (BASE/'assessment_v8.py').read_text()),
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
    for label,value in topics:check(value,label)
    # isolated test of scoring with stub imports, no chess package available in build environment
    sys.path.insert(0,str(BASE))
    for key in ('chess','exercises','assessment_v3'):
        if key not in sys.modules:sys.modules[key]=types.ModuleType(key)
    sys.modules['exercises'].bank=lambda:[]
    sys.modules['assessment_v3']._opening=lambda rng:None
    sys.modules['assessment_v3']._endgame=lambda rng:None
    from assessment_v8 import points, finalize, DOMAINS
    check(points(False,1,7)==0,'오답은 언제나 0점')
    check(points(True,5,7)==100,'정답 시간 보너스 제한')
    check(points(True,1000,7)>=92,'오래 걸려도 정답 중요')
    mock=[]
    for name,_,_ in DOMAINS:
        for diff in range(1,8):
            mock.append({'domain':name,'correct':True,'seconds':60.0,'points':points(True,60,diff),'difficulty':diff})
    result=finalize(mock,[0]*10,True,10)
    check(result['index']==1000,'최고점은 1000점')
    check(result['game_score']==100.0,'0cp 손실은 100점')
    print(f'PASS: {len(topics)} structural checks + 5 score assertions + Python/JS parsers')

if __name__=='__main__':run()
