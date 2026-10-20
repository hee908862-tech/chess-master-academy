# 학습 이어하기와 입문 경로 후속 QA

기준 main `4da24ba3d55460891521a47c4bde150a28019981`. 수정 브랜치 `fix/learning-continuity-audit`. 기존 사용자/PIN/대국/학습/문제은행을 삭제하거나 재채점하지 않는다. 모든 실행 검증은 새 임시 계정과 격리 SQLite 또는 loopback PostgreSQL을 사용한다. 운영 FRESH 계정은 건드리지 않는다.

## 문제 구분과 수정

사용자가 전달한 실제 브라우저 QA의 현상과 이 브랜치에서 확인한 코드를 구분한다. 과거 운영 요청의 전체 로그가 없으므로 당시 모든 현상을 특정 원인으로 확정하지 않는다.

| QA 현상 | 코드에서 확인한 원인/제약 | 수정 및 검증 범위 |
|---|---|---|
| 추천 수순 도중 일반 훈련 시작 시 진행 소실 | 새 시작이 active를 교체 | 현재 세션/리비전을 확인한 명시적 전환만 허용. paused에 착수·도움·추천 슬롯 보존. 재개 시 리비전 변경으로 지연 요청 차단 |
| 아카데미 새로고침 후 이어하기 부재 | 서버 과정은 남지만 UI 복원 진입점이 없음 | 저장 과정/보존 과정 목록, 재개 버튼, 새 과정 확인. 교체 토큰·기존 저장 CAS 사용. 재개 시 요청 식별자를 갱신하여 이전 요청 거부 |
| 참고 오프닝 저장 버튼 무반응 | 참고 수순은 저장 API 지원 밖 | 버튼 비활성화와 이유 표시. 이전 해설 강의의 저장 위치임을 명시 |
| 참고 수순 초기화 시 다른 강의로 이동 | 공통 초기화가 강의 시작 호출 | 참고 수순 컨텍스트 유지, 별도 해설 강의 복귀 버튼 |
| 400px 메뉴의 목적지 접근 어려움 | 가로 메뉴가 넘침 | 홈·진단·훈련실·기록·더보기. 네이티브 dialog, Escape/탭 포커스와 복귀 검사 |
| 훈련 카드 식별과 행동 과다 | 반복 제목과 동급 버튼 | 주제·자료 ID·출처·날짜·최근 결과, 주 행동 하나와 접힌 추가 행동 |
| 현재 주기와 누적 완료 혼동 | 동일한 완료 용어 | 현재 추천 주기와 누적 완료를 분리. 대국 지표와 전체 수순 훈련 근거는 접어 읽기 |
| 과정이 문제 개수 위주 | 개념 설명이 부족 | 직접 작성 학습 목표와 일반 예시. 간섭/추크츠방 포함. 현재 정답 해설로 과장하지 않음 |
| 로딩/무대국 액션 불명확 | 카탈로그 실패 및 액션 가능 상태 안내 부족 | 오프닝 준비·실패·재시도, 무대국 기권/힌트/무르기 비활성 사유 |
| 첫 수 연습과 전체 수순 지도 혼동 | 독립 새 문제는 first_move | 기존 채점을 보존하고 첫 수/전체 수순 라벨·횟수를 분리. 과거 첫 수 기록을 완주 기록으로 승격하지 않음 |
| 7일 기억 확인 준비 방법 부재 | 기존 gate는 진단 연결 미노출 full_line verify·도움 없음만 허용 | 별도 준비 액션을 추가. 추천5개는 연습임을 명시. 기존 노출 시각·7일 대기·판정 의미 유지 |
| 적용 과제의 난도 부담과 교체 | 고정 범위/무작위 및 교체 경로 없음 | 실제 진단 관찰 기반 난도, 근거 부족 시 600–1200. 같은 추천 슬롯에서 실제 더 낮은 난도만 교체. 교체 전 세션 보존, 중복 완료 차단, 후보 없음은 원상 유지 |

훈련 설명은 현재 체크 공격 기물과 실제 상대 기준 응수의 SAN·규칙 사실을 보강했다. 일반 전술 예시와 규칙 설명은 심층 분석으로 부르지 않는다. 기존 대안 수 판단 보류 정책과 Stockfish 예산은 유지한다.

## 시작 수준과 실제 출제

계정에 `learner_start`를 추가로 저장한다. 룰부터/초보/경험 있음/잘 모르겠음/나중에를 선택·변경할 수 있다. 기존 활동이 있으면 자동 팝업을 미루고 이어하기를 우선한다. 일반 사용 안내는 수동으로 계속 열 수 있다. 선택은 실제 실력이나 Elo 점수가 아니다.

- 룰부터: 말 이동·잡기·체크·왕 안전의 4단계 보드 연습. 설명을 보며 재시도 가능, 감점·진단 점수·문제 완료 크레딧 없음.
- 초보/잘 모르겠음/나중에/미선택: `gentle` 입문 관찰. 난도 600 이상 1000 미만, 기준 수순 최대 5반수, 분야별 최대 한 문제(총 최대6). 충분한 조건의 문제가 없으면 어려운 문제로 몰래 대체하지 않음.
- 대국 경험 있음: 기존 균형 24문항. 선택 도전으로 기초·응용 12문항도 명시적으로 제공.
- 현재 진행 중 진단은 선택 변경으로 교체되지 않는다. 각 새 세션/보고서에 자기 선택, 실제 모드·출제 난도·전체 수순 범위를 별도로 저장하며 실제 문항/착수/도움/결과는 기존 증거 기록에 남긴다.
- 입문은 `journey-entry-v1` 및 별도 모드로 저장하고 균형 성장 snapshot을 생성하지 않는다. 기존 자료와 다른 난도 결과를 하나의 성장선으로 합치지 않으며 과거 기록을 재채점하지 않는다.

## 추가 리뷰 전 검증 기록

추가 리뷰 전 애플리케이션 코드 커밋 `73c5f9958515efbeac8d4348042fb01a858535cd`의 기록이다. 현재 수정 후 검증은 마지막 절에 별도로 기록한다.

| 검사 | 결과 |
|---|---|
| 전체 pytest (실제 Chromium·Stockfish 포함) | **350 통과**, 실패/건너뛰기 0, 586.13초 |
| 격리 PostgreSQL17 통합 검사 | **14 통과**, 36.07초; 동시 선택 CAS·훈련 전환·도움 보존·지연 요청 포함 |
| 최종 관련 브라우저/API 재검사 | 25 통과; 카드 페이지네이션 4 통과 |
| 배포 Dockerfile 빌드 | 통과; 이미지 `sha256:20e147a74bced16615fa9db9a94251e1316c988b96272ced9db57917d68f82b6` |
| 새 이미지 실제 HTTP, 1 CPU/512MiB/임시 PostgreSQL | 기초→입문, 진단/훈련/과정 재시작 복원, 도움 보존, 허위 완료 없음 통과 |
| 기존 복기·오프닝 실제 HTTP | Stockfish 응수, 원본 비변경, 저장 위치 재시작 복원, OZElq/Qc3 판정 통과; OOM 없음, 해당 실행 메모리 최고 398,675,968바이트 |
| 구문·공백 | Python AST 77파일, `node --check` 19파일, `git diff --check` 통과 |
| 별도 타입/린트 도구 | 프로젝트에 전용 설정이 없어 미실행. 위 구문 검사를 타입 검사로 표시하지 않음 |
| 원격 CI | 커밋 상태 및 PR 트리거 Actions 조회에 실행 기록 없음. CI 성공으로 표시하지 않음 |

중간 전체 실행의 335통과/11실패는 새 명시적 전환·더보기·입문 경로·접힌 지표와 맞지 않는 기존 기대값 및 테스트 계정의 미완료 세션 전환에서 발생했다. 테스트를 새 계약으로 갱신하고 미확인 전환 거부 검사를 별도로 유지했다. 더보기 포커스 이탈과 같은 문제 재개의 불필요한 전환 확인도 관련 검사에서 수정했다. 위 **최종 전체 재실행**이 모두 통과했다. 경고 1개는 Starlette의 httpx TestClient 사용 중단 예고이며 실패가 아니다.

실행 재현:

```sh
CMA_JOURNEY_INDEX=/tmp/chess-journey-index.json.gz python build_journey_index.py
DATABASE_URL='' SQLITE_FILE=/tmp/cma-audit-final.sqlite STOCKFISH_PATH=/path/to/stockfish CMA_JOURNEY_INDEX=/tmp/chess-journey-index.json.gz PYTHONPATH=. python -m pytest -q
# disposable loopback cma_predeploy DB만 허용하는 검사:
CMA_TEST_PG_URL="$LOCAL_TEST_PG_URL" STOCKFISH_PATH=/path/to/stockfish CMA_JOURNEY_INDEX=/tmp/chess-journey-index.json.gz python -m pytest -q scripts/predeploy_postgres.py
# 이름·이미지·메모리·loopback DB를 검증하는 전용 로컬 컨테이너 검사:
python scripts/predeploy_study_http.py
python scripts/predeploy_continuity_http.py
```

[전체 검사 로그](docs/qa-continuity/pytest-final.txt), [PostgreSQL 로그](docs/qa-continuity/postgres.txt), [기존 기능 HTTP](docs/qa-continuity/container-study.json), [새 흐름 HTTP](docs/qa-continuity/container-continuity.json), [실행 버전](docs/qa-continuity/runtime.json)을 보존했다.

수동 화면 확인: 실제 Chromium 400px 캡처의 [참고 오프닝](docs/qa-continuity/reference-mobile.png) 저장 비활성/설명과 강의 복귀, [입문 진단](docs/qa-continuity/entry-mobile.png)의 보드·차례·메뉴를 직접 읽었다. [데스크톱 복기](docs/qa-continuity/review-desktop.png)는 테스트용 2반수 기보로 보드 상단 정렬과 탐색 액션을 확인한 화면이며 운영 실사용 증거가 아니다.

실제 휴대폰/Safari와 보조기술은 미검증이다. 운영 당시 전체 요청 로그가 없어 과거 현상의 원인을 모두 단정하지 않는다. 운영 실사용은 독립 리뷰·배포 이후 클라우드 브라우저의 별도 테스트 계정으로 확인한다. 여기서는 Render 배포나 main 병합을 실행하지 않았다.

## 독립 리뷰 후 추가 수정

- 입문 결과 상단에 관찰 근거의 수순 연습, 입문 새 문제 재확인, 표준 12/24문항 도전, 시작 수준 변경을 제공한다. 입문에는 존재하지 않는 5개 계획을 약속하지 않고 표준 추천 주기와 구분한다. 기존 입문 결과에도 적용하며 별도 점수나 snapshot을 생성하지 않는다.
- 상태 응답의 `latest`는 실제 마지막 완료 결과다. 이전 표준 추천은 `cycle`/`cycle_report`로 별도 보존하고 최신 입문·추가 결과 아래에서 펼쳐 이어갈 수 있다. 균형/간이 진단의 단서 비공개와 입문 안내 조건을 문구로 구분하며 기초 4단계는 첫 안내임을 명시한다.
- 같은 카드 시작·현재 세션 재개·보관 세션 재개·경로 복원·추천/진단 연결 경로 재개는 마지막 보드 노출 시각을 갱신한다. 훈련 화면 재진입도 인증된 세션/리비전의 노출 기록을 요청한다. 홈·대시보드의 일반 GET 조회는 노출 시각을 변경하지 않는다. 착수·도움 이력을 보존하고 기존 gate에 성공 조건을 새로 추가하지 않았다.
- 10월1일 기존 근거와 도움 기록, 7일 전후/10월20일 재노출/10월27일 조건을 제어한 5가지 회귀가 통과했다. 관련 API 24개, 실제 입문 완주를 포함한 브라우저 17개가 통과했다. 위 350개 결과는 추가 수정 전 코드의 검증 기록이다.

## 추가 리뷰 후 검증

검사 대상 애플리케이션 커밋은 `55a4597b956b37c6493656e85e8b4cb293ae4d51`이다.

첫 전체 재실행은 358통과/1실패였다. 새 표준 진단 완료 직후 서버 상태 재조회 전 이전 추천 주기가 잠깐 중복 표시되는 원인을 확인했다. 이전 주기 패널을 입문·추가 결과로 한정하고, 표준 재완료 뒤 패널이 없음을 검증했다. 해당 브라우저 재검사 4건이 통과했다. 이전 표준→입문 완료→새로고침의 최신 입문/이전 주기 보존도 포함한다.

- 격리 PostgreSQL17: 14통과, 50.40초. 일반 dashboard GET은 노출을 변경하지 않고 인증된 보드 노출 기록만 변경함을 포함한다.
- Python AST 79파일, JavaScript `node --check` 19파일 통과. 전용 타입/린트 설정은 없어 미실행이다.
- Docker 이미지 `sha256:703475556f87e37cb080d2b68ff0cdd24d5c107323ad5ac5ba8b866e75e24c12` 빌드 통과. 1CPU/512MiB 및 임시 PostgreSQL에서 입문·진단/훈련/과정 재시작 복원·도움 보존·복기·오프닝 HTTP 검사 통과. 기존 복기 검사 메모리 최고 398,860,288바이트, OOM 없음.
- [입문 완료 후 모바일 다음 단계](docs/qa-continuity/entry-next-mobile.png)는 실제 입문 완료 후 400px Chromium 화면을 직접 확인한 캡처다.
- [최초 전체 재검사 실패 기록](docs/qa-continuity/pytest-review-before-fix.txt), [브라우저 수정 재검사](docs/qa-continuity/browser-review-final.txt), [PostgreSQL](docs/qa-continuity/postgres-review.txt), [현재 이미지 새 흐름](docs/qa-continuity/container-continuity-review.json), [현재 이미지 복기/오프닝](docs/qa-continuity/container-study-review.json)을 보존한다.

최종 전체 pytest는 **359통과**, 실패/건너뛰기 0, 552.67초다. 실제 Chromium·Stockfish를 포함하며 [최종 전체 로그](docs/qa-continuity/pytest-review-final.txt)를 보존한다. 경고 1개는 Starlette httpx TestClient 사용 중단 예고다. `git diff --check`도 통과했다. 원격 CI는 최종 증거 커밋을 push한 뒤 PR에서 확인하며 실행 기록이 없으면 성공으로 표시하지 않는다. main 병합·Render 배포·운영 데이터 변경은 하지 않았다.
