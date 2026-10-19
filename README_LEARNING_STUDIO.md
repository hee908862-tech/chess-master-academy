# 학습 중심 훈련실 · PR #3 확장

기준 main `89e65955976fba0cd42a1ba6ecbf2866724d978e`, 기존 PR #3 head `48222ad4a07ad06ba914d4f1e9f609ae050ff08d` 위에 구현한다. 기존 PR의 직전 수·흑 방향·결과 혼재·프리무브 변경을 그대로 포함한다. 병합/배포/운영 DB 변경은 실행하지 않는다.

## 설계와 실제 지원 범위

| 요청 | 구현 | 한계 |
|---|---|---|
| 1. 복기 → 개인 훈련 | 기존 복기 분석 재사용, 내 착수만 필터, 96cp 이상 손실을 짧게 재분석해 최대 3개 저장. 답을 숨긴 재도전, 3단계 힌트, 실제 실수 뒤 엔진 응수 재생, 같은 영역의 새 문제 | 부분 지원: 복기 200반수 이하, 짧은 엔진 탐색의 근사값. 유사 문제는 지원 영역 일치이며 정교한 전술 구조 유사도 검색은 아님. 엔진 없으면 실수 추출을 차단 |
| 2. 근거 있는 설명 | 직전 수의 포획/체크/승격/캐슬링 등 규칙 사실, 관련 기물 → 정확한 수, 원본/엔진 수순, 최선 대비 손실. 45cp 이내 엔진 확인 대안과 즉시 메이트 허용 | 부분 지원: 전략적인 장기 목적을 자연어로 추론하지 않음. 최초 힌트는 영역별 점검법. 강제 메이트의 비종결 대안을 완전히 증명하지 않음. 엔진 없는 다른 수는 미검증으로 기록하고 성공률에서 제외 |
| 3. 오답노트·재검증 | 정답 공개/도움/무도움 첫 성공/다른 날짜 무도움 성공/같은 날 재시도 구분. 서버 저장·새로고침 복원, 1·3·7일 간격 변경 가능. 검증 주제 숨김 및 서버 도움 차단 | 부분 지원: 날짜는 UTC. 새 문제는 저장된 ID 기준; ID 없는 옛 진단의 출제 이력까지는 복구 불가. 기존 퍼즐 전체 기록을 소급하여 새 숙련도로 환산하지 않음 |
| 4. 능력 지도 | 수읽기·엔드게임·승격·메이트·포획/교환·방어 6영역, 표본 수·최근/이전 5회·새 문제 검증 성공·근거 부족 | 지원 범위를 위 6영역으로 제한. 공식 Elo/종합 체스 실력 지수가 아님. 새 경로 기록만 사용, 기존 기록 메뉴 보존 |
| 5. 상황 대국 | 실제 저장 위치에서 엔진 상대 6수 연습/검증, 시작 평가 100cp 이내 유지 목표. 연습 힌트/무르기, 검증 금지. 시작 FEN과 전체 착수 스택 유지. 모드별 기록 | 부분 지원: 우세 유지·방어의 짧은 평가 목표만 제공. 특정 폰 구조·장기 계획·테이블베이스 완주 목표는 미지원. 엔진 없으면 시작 금지. 짧은 탐색/100cp는 교육용 기준 |
| 6. 오늘의 경로 | 복습 예정 위치 → 짧은 개념 → 미출제 검증 → 상황 연습. 최근 무도움 결과가 낮은 영역 우선, 근거 없는 첫 사용 안내, 자유 이동 유지 | 부분 지원: 4단계 진입 경로이며 하루 전체 완료를 강제하는 별도 코스 상태는 없음. 처음에는 실수 대신 새 문제로 기록 시작 |

PC는 보드/설명/노트 2열, 1050px 이하는 보드 우선, 760px 이하는 설명 접기와 세로 배치. 일반 조작 버튼 최소 44px, 보드는 화면 폭에 맞추므로 작은 화면의 각 칸은 44px 미만일 수 있다. 모바일 훈련실에서는 고정 하단 내비게이션 대신 문서 흐름 안의 상단 이동 버튼을 사용해 보드를 가리지 않는다. 다른 화면의 기존 메뉴는 유지한다. 새 훈련에는 프리무브가 없으며 안내를 표시한다. 기존 대국·진단 AI·v9 퍼즐의 프리무브는 유지한다.

## 저장과 안전 경계

- 새 `learning_progress(code PRIMARY KEY, state TEXT)` 테이블을 startup의 `CREATE TABLE IF NOT EXISTS`로 추가한다. 기존 accounts/sessions/progress/문제은행을 변경하거나 초기화하지 않는다. Docker COPY에 새 모듈만 추가한다.
- 새 학습 기록의 읽기→변경→저장은 한 트랜잭션: SQLite `BEGIN IMMEDIATE`, PostgreSQL `INSERT ... ON CONFLICT DO NOTHING` 후 `SELECT ... FOR UPDATE`. session ID와 revision이 일치해야 동작한다. 실패는 rollback한다.
- 기존 progress JSON을 쓰는 화면이 새 테이블을 덮어쓸 수 없다. **기존 progress 자체의 전체 read-modify-write 경쟁은 해결 범위 밖**이다.
- PostgreSQL SQL 경로는 구현했지만 이 환경에 서버가 없어 실제 PostgreSQL 동시성/업그레이드 검증은 미실행이다. 운영 반영 전 백업 및 별도 스테이징 확인 필요. 이번 작업은 운영에 연결하지 않았다.
- 새 테이블을 기존 프로필의 기록 초기화 기능과 자동 연결하지 않는다. 기존 초기화 화면의 문구는 새 훈련 기록까지 지운다고 보장하지 않으며, 사용자 요청 없이 삭제 범위를 넓히지 않는다.
- 엔진은 기존 STOCKFISH_PATH만 사용한다. 유료 API/새 비밀키/외부 서비스가 없다. 엔진 탐색은 동기 실행이며 상황 학습 중 계정 row lock을 유지한다. 대규모 동시 사용 부하 검증은 미실행이다.

## 로컬 검증 방법

```sh
python -m pytest -q tests/test_learning.py tests/test_learning_browser.py
python -m pytest -q tests/test_board_interaction.py tests/test_qa_behavior.py tests/test_qa_browser.py tests/test_qa_followup_browser.py
python test_qa_work_regression.py
python test_v9_static.py
python -m compileall -q server.py learning_server.py tests
for f in public/*.js; do node --check "$f" || exit; done
git diff --check
```

테스트는 임시 SQLite/임시 QA 계정만 사용한다. 엔진 테스트는 로컬 `/tmp/chess-stockfish/usr/games/stockfish`가 있을 때 실행하고 없으면 skip한다. Chromium 테스트는 실제 새 학습 API를 호출하며 기존 v9 catalog/diagnostic 응답만 격리한다. 1440×1000, 390×844, 844×390, 768×1024에서 새 문제→힌트→착수→기록→reload→검증과 가로 넘침을 검사한다. 실제 모바일 기기/운영 Work QA는 아니다.

기존 `test_v81_regression.py`와 `test_v3_static.py`는 main부터 구형 영역명/script 목록 기대값으로 실패한 테스트이며 통과했다고 주장하지 않는다. 전용 lint/type 설정은 없어 구문 검사와 실행 테스트로 검증한다.

## 최종 확인 결과

- 신규 **16개 통과**: API 12개(실제 Stockfish 3개 포함), 실제 새 API를 사용하는 Chromium 4개. 31.85초. 계정 분리, SQLite 새 앱 인스턴스 복원, 4개 동시 중복 착수 중 단 한 번 저장, 기존 progress JSON 동시 쓰기 보존, 엔진 미연결 rollback, 숨겨진 답안, 검증 도움 차단, 정답 공개/힌트/날짜별 성공 구분, 6수 상황 기록/무르기를 확인했다.
- 기존 행동 회귀 **73개 통과**, 166.76초. 기존 보드 방향·직전 수·추천 이동·프리무브·취소·승격·진단 상태 흐름 포함.
- QA 정적 계약, v9 UI/파일 검사, Python 구문, 전체 public JavaScript 구문, git diff 공백 검사 통과. Starlette/httpx deprecation 경고 1개.
- 기존 v81/v3 정적 검사 실패는 유지. 전용 lint/type 검사, PostgreSQL 실서버, 운영 Work QA, 물리 모바일, 대규모 부하는 미실행.
- 문제은행 blob은 main과 동일한 `efb19b7b720cc5f3a1c033c41d212c0cd708ec89`. 계정/PIN/기존 학습 데이터는 변경·삭제하지 않았다.

스크린샷은 임시 로컬 QA 계정의 실제 Chromium 캡처다. 캡처 이미지 자체를 열어 확인했으며, 고정 메뉴 겹침 수정 후 갱신했다.

- [PC 1440×1000](docs/qa-learning/learning-1440x1000.png)
- [모바일 세로 390×844](docs/qa-learning/learning-390x844.png)
- [모바일 가로 844×390](docs/qa-learning/learning-844x390.png)
- [중간 폭 768×1024](docs/qa-learning/learning-768x1024.png)

배포 후 별도 확인 순서: 복기에서 개인 훈련 생성 → 힌트 없이 재도전 → 답안/응수 재생 → 새 문제 검증 → 오답노트 새로고침 복원 → 상황 연습 무르기/상황 검증 도움 차단 → 다음 날짜 복습. 현재는 배포하지 않았다.
