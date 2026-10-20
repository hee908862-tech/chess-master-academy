# 탐색·도전 개편 검증 증거

검증 대상 main 기준: `c4f7d3f2b6f9c58780e37ec9345c2d7f452653e4`. 최종 원격 head와 CI 상태는 PR에 기록한다. 운영 브라우저/운영 계정 검증을 주장하지 않는다.

## 증거 구분

- 실제 Chromium + 로컬 API: 아카데미 메뉴의 클릭/Enter/Escape/포커스/바깥 클릭, 세 하위 경로, 도움말 열기 무변경, 도전 시작·힌트·착수·3회 건너뛰기 종료·실수 복습·탭/새로고침 복원.
- UI 통제 응답 검사: 승격 선택 중 이동 시 취소, 나이트 언더프로모션 제출. 실제 승격·앙파상·캐슬링 서버 규칙은 별도 API 검사로 검증한다.
- 실제 SQLite/PG: 계정 분리, revision 충돌, 동시 제출 1회 저장, 10문제 완주 95점(힌트1개), 원본 일반 퍼즐/진단/훈련/대국 상태 불변.
- 실제 Docker HTTP: 이미지 1CPU·512MiB/PG17/고유 임시 계정, 프로세스 재시작 후 저장 상태 복원, 실제 Stockfish 응수와 기존 진단 대안 판정.
- 미검증: 운영 계정 실사용, 물리 모바일/Safari, 장기 학습 효과, 완전한 대안 최선 수 판정. Library 메뉴 참고 이미지의 직접 픽셀 확인은 다운로드 프록시403으로 불가했다.

## 실행 기록

최종 전체 결과는 아래 최종 검증 표에 별도로 기록한다. 중간 통과 수를 최종 전체 통과로 합산하지 않는다.

| 검사 | 중간 결과 |
|---|---|
| 퍼즐 API·오프닝·브라우저 최초 관련 검사 | 24통과/1실패: 동일 동시 전이 2건이 모두200 응답. 점수 중복은 없었으나 write_id CAS로 두 번째409를 보장하도록 보완 |
| 수정 후 관련 검사 | 30통과, 50.87초 |
| 탐색·도전 취소·기초 회귀 | 17통과, 94.15초 |
| 첫 전체 회귀 | 384통과/1실패, 689.54초. PC1366×768 진단 보드가 새 도움말 줄 높이만큼 화면 아래로 벗어남. 개별 재현도 실패해 실제 레이아웃 결함으로 분류. 높이 계산 보완 후 관련8개 통과(45.99초) |
| 승격 취소 추가 중 관련 검사 | 52통과/1실패(190.30초): 취소 후 출발 칸 선택이 남아 재선택이 끊김. 도전 선택 초기화와 연구 보드 재활성화 수정 후 각각 단일 회귀 통과(10.51초/9.15초); 최종 전체에도 포함 |
| 두 번째 전체 실행 | 수동 Shift+Tab 검사에서 새 메뉴의 포커스가 BODY로 빠지는 실제 결함을 발견해 102통과/220.09초에서 중단. 전체 통과로 계산하지 않음. 기존 더보기와 같은 명시적 순환 처리 추가 |
| 수동 전체 도움말 검사 최초 | 퍼즐 모드 버튼까지 선택한 strict selector 오류. `header.feature-toolbar`로 검사 선택자를 좁힘 |
| 수동 전체 도움말 재실행 | 390/1280폭 각10화면, 도움말 POST0, Escape 포커스·바깥 클릭·훈련 보드/해설 통과 |

검증 명령은 다음과 같다. DB는 반드시 격리된 임시 파일/지정 loopback만 사용한다.

```sh
DATABASE_URL='' SQLITE_FILE=/tmp/cma-nav-final.sqlite STOCKFISH_PATH=/tmp/chess-stockfish/usr/games/stockfish CMA_JOURNEY_INDEX=/tmp/chess-journey-index.json.gz PYTHONPATH=. /tmp/chess-venv/bin/python -m pytest -q
CMA_TEST_PG_URL=postgresql://cma:temporary-local-only@127.0.0.1:55432/cma_predeploy STOCKFISH_PATH=/tmp/chess-stockfish/usr/games/stockfish CMA_JOURNEY_INDEX=/tmp/chess-journey-index.json.gz /tmp/chess-venv/bin/python -m pytest -q scripts/predeploy_postgres.py
/tmp/chess-venv/bin/python scripts/predeploy_challenge_http.py
/tmp/chess-venv/bin/python scripts/predeploy_study_http.py
/tmp/chess-venv/bin/python scripts/predeploy_continuity_http.py
/tmp/chess-venv/bin/python scripts/predeploy_foundations_http.py
```

전용 타입/린트 설정은 없으므로 해당 검사를 실행했다고 주장하지 않는다. Python AST, Node `--check`, `git diff --check`를 사용한다. TestClient/httpx deprecation 경고는 별도 남아 있다.

## 화면

- [모바일 아카데미 메뉴](menu-390.png) / [PC 메뉴](menu-1280.png)
- [모바일 오프닝 해설·도구](opening-390.png) / [PC 오프닝](opening-1280.png)
- [모바일 퍼즐 결과·실수 복습](challenge-390.png) / [PC 퍼즐](challenge-1280.png)
- [모바일 실제 훈련](training-390.png) / [PC 실제 훈련](training-1280.png)
- [보드 높이 수정 후 PC 진단](diagnosis-pc.png) / [모바일 진단](diagnosis-mobile.png)
- [분기 후 원본 복귀](review-original-preserved.png)

화면의 계정 코드는 격리 QA 계정이며 운영 사용자가 아니다. 수동 검사 스크립트 `manual-guide-probe.py`도 지정된 loopback 전용이다. 이전 PR의 화면은 전체 회귀가 다시 생성하더라도 이번 변경에 포함하지 않는다.

## 최종 검증

기능·회귀 검사 소스 커밋: `60ae56a66a252d5e4b3e547e3ce62570318927b1`. 이후 커밋은 검증 문서·로그·화면만 포함한다. [파일별 SHA-256](source-sha256.json)으로 실제 검사 소스를 확인한다.

| 검사 | 최종 결과 |
|---|---|
| 전체 회귀 | **386통과 / 0실패 / 736.15초**, [전체 로그](full-final.log) |
| 관련 최종 상호작용 | **9통과 / 50.52초**, 메뉴·도움말 Tab/Shift+Tab/Escape, 승격 취소·재조작, PC/모바일 진단 보드 |
| PostgreSQL17 | **16통과 / 34.20초**, 새 퍼즐 동시 제출409·계정 분리·복원 포함 |
| Docker 실제 HTTP 4종 | **모두 통과**, 퍼즐/오프닝·엔진/연속 학습/기초 보존 |
| PC/모바일 전체 도움말 | **390/1280폭 각10화면 통과**, 열기 POST0, Tab 포커스 순환·Escape·바깥 클릭·원래 버튼 복귀, JS 오류0 |
| 구문 | 루트·tests·scripts Python90개 AST / public JavaScript22개 Node `--check` 통과 |
| 타입·린트 | 전용 설정 없음, 별도 실행하지 않음. `git diff --check` 사용 |

최종 Docker 이미지: `sha256:13e59528f290e7e0d28fb7821f8dea343947d6c0b7cdc8e83c2612677b83396e`. 1CPU/512MiB에서 실제 Stockfish17.1 응수 및 OZElq 대안 판정 깊이16/16을 확인했다. HTTP 검사 중 관측한 최대 메모리400,478,208바이트, OOM 없음. 검사 종료 후 임시 앱·PG 컨테이너를 중지했다. 운영 배포가 아니다.

[PG 로그](postgres.log), [퍼즐 HTTP](http-challenge.json), [오프닝/엔진 HTTP](http-study.json), [연속 학습 HTTP](http-continuity.json), [기초 HTTP](http-foundations.json), [수동 도움말 결과](manual-guides.json), [최종 상호작용 로그](interactions-final.log). 최초 전체 실패 및 중단 로그는 별도로 보존한다.
