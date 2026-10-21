# 2단계 공통 보드 체크·모션 재개

상태: 런타임 구현 및 집중 검사 완료, 최종 전체 회귀 준비. 아래 이전 체크포인트는 작업 이력이다.

- 작업트리 /tmp/cma-shared-board-feedback, 브랜치 feat/shared-board-feedback.
- 의존 기준: feat/foundation-board-feedback의 590bde31d71f2236215b519599e0f862cf9d504d (PR25 미병합). 후속 PR은 이 브랜치 의존을 명시하고 부모가 PR25 병합 후 main 기준으로 정리한다.
- 운영 계정/기보/학습 상태는 변경하지 않는다. 기존 /tmp/cma-foundation-feedback의 증거/미커밋 생성 캡처를 보존한다. 루트0, /tmp 여유 약7.7GiB. Docker/PG 제약 지속.

## 확인한 구조

- public/app.js drawBoard는 모든 칸을 재생성한다. animateBoardTransition은 대국의 한 기물 ghost만 이동하며 210ms Web Animations를 사용한다. 캐슬링 두 기물/앙파상/승격/역방향 및 공통 cancellation/reduced-motion은 별도 보강 대상이다.
- server.py의 대국 응답에는 fen/check/last_move/ply가 있다. study_server.py view는 fen/legal/terminal/ending을 반환하며 체크킹 좌표는 없다. public/study.js의 draw는 현재 cursor의 state.fen을 사용한다. 과거 복기 위치는 현재 게임 체크 상태를 재사용하면 안 된다.
- PR25 foundation_server.visual_context는 실제 board.is_check/checkers를 사용한다. 이 규칙 근거를 공통 응답 표시 메타데이터로 재사용하되 점수/도움/저장 상태에 포함하지 않는다.

## 구현 순서와 수용 기준

1. 현재 FEN에 대한 표시 메타데이터와 검증된 before/after/UCI 전환 계약을 정리한다. 합법성은 python-chess에서 검증하고 프런트엔드에서는 주어진 두 위치가 전환과 일치하는지 확인한다. 단순 위치 교체/강좌 변경/계정 변경은 가짜 착수로 애니메이션하지 않는다.
2. 보드별 취소 가능한 모션 수명주기를 만든다. 저장/시계/입력 승인은 애니메이션 완료를 기다리지 않는다. 캐슬링 양 기물, 잡기/앙파상 제거, 승격 교체, 역방향 복원 위치를 정확히 처리한다. 프리무브 중복 제출과 이동 후 stale callback을 차단한다.
3. 대국/학습/퍼즐/진단/오프닝/복기/데모 렌더러를 조사해 현재 위치만 표시한다. 체크는 빨간 표시+라벨이며 핀된 공격도 포함한다. 체크메이트/스테일메이트를 혼동하지 않는다. 독립 풀이 정답/위협 노출을 추가하지 않는다.
4. reduced-motion 즉시 표시, 화면 이탈/계정 변경/빠른 복기 탐색 cancellation, 흑 시점/키보드/승격 취소/시계/프리무브/느린 응답을 검사한다. 새 FEN에서 잔여 표시는0이다.

단계3 전체 레이아웃/피드백 확장은 포함하지 않는다. 첫 논리 단위 구현과 검사 후 작은 commit/push로 보존하고 해당 SHA·실행한 검사·미검증을 이 문서에 갱신한다. 새 전체 검사 전 이전 프로세스/로그를 확인해 중복 실행하지 않는다.

런타임 체크포인트: main 140f97760a1b1c9935612219fe1c92b865bcdf71을 병합했다. PR25 원격 최종590bde3는 main에 포함된다. 공통 board-presentation.js는 모든 drawBoard 배치의 기하학적 공격(핀된 공격 포함)을 계산하고, 명시적 UCI와 전후 배치가 정확히 맞는 경우만 모션을 생성한다. 기존 animateBoardTransition은 새 공통 구현으로 대체했다. 초기 규칙 대조/특수 수·역방향 계획2검사 통과(/tmp/cma-board-presentation-core.log). 아직 모드별 연결/브라우저/전체 검증 전이며 중간 코드 병합 금지.

다음: BoardStudy/복기 cursor/무르기, 기초/훈련/진단의 명시적 수순 연결, 전환 연속 프레임 계약. 실제 브라우저 cancellation/중복모션/resize/reduced-motion 및 모든 기존 기능 회귀. 현재 큰 레이아웃 개편은 하지 않는다.

모드 연결 중간 체크포인트: 기존 대국 모션 단일 대체, BoardStudy/원본 복기1반수 전후, 대국 무르기의 서버가 반환한 실제 제거 수순, 전술 상대 응수, 기초/훈련/레퍼토리/교육/도전/진단의 명시적 착수와 읽기 전용 복기 프레임을 연결했다. 기초·훈련·도전의 played_moves 및 undo 응답 undone_moves는 이미 적용된 수순만 반환하며 저장 모델은 바꾸지 않는다. 최대2반수 계획과 특수 수/역방향을 검증한다. 단순 배치 diff는 모션을 만들지 않는다.
초기 공통+기초 집중25통과(/tmp/cma-shared-board-focused.log). 이후 두 반수/모드 연결 추가분은 /tmp/cma-shared-board-integrated.log 실행 중: 완료/실패 확인 전 재실행하지 말 것. 전체회귀/최종캡처/DockerPG는 아직 미실행. 미검증 중간 코드 병합 금지. 운영은 부모 담당, 계정 접근 시도 안 함.

최종 회귀 준비: 원격 ffd653f452a9aa8d523b96356cfbb2bc116d1d20 이후 v8 실제 표시 착수와 모션 경계 검사를 보완했다. 통합 70통과/1실패는 이동 중 opacity DOM 비교였으며, settled DOM을 기다리고 기존 동일성/CAS 검증을 유지한 후속11검사 통과(36.38초). 규칙/경계11통과, 초기공통+기초25통과는 각 이전 코드 기준이다. 최종 전체 회귀는 /tmp/run_shared_board_final.py 및 /tmp/cma-shared-board-final-suite-*.log, manifest JSON을 확인한다. 실행 중이면 중복 시작하지 않는다. 루트0, /tmp7.6GiB; Docker/PostgreSQL 미실행. 운영 변경 없음.

최종 검사 완료: 런타임 소스 9f002da24717d8f4f04f318e6a440204633bb174. 전체601 중599통과/2실패(671.85초), 두 실패는 복기 메뉴 테스트의 이동 중 opacity DOM 비교. 테스트 대기1줄만 보완하고 해당파일 전체12통과(43.82초). 애플리케이션 변경 없이 전체 재실행은 하지 않았다. docs/qa-shared-board-feedback/REPORT.md, 원본로그/manifest/PC·모바일 캡처 참조. 구문33통과, diff-check통과. 테스트가 만든 타 단계 캡처/캐시는 미커밋 보존.
초안PR create는 자동승인검토에서 사용자 직접 승인 미확인으로 미실행 거절. 부모에 전달했고 새 관련 승인 근거 없이 반복/우회하지 않음. 다음: 부모의 직접 승인 원문이 오면 미실행인 PR생성만 한번 재시도 판단, 여전히 거절이면 중단. 별도 단계3 구현 시작하지 말 것. 원격 codehead와 최종 문서 commit은 구분한다.

2026-10-21 후속: 추가 직접 승인 근거로 미실행 PR생성을 한 번 재시도했고 draft PR26 생성 성공: https://github.com/hee908862-tech/chess-master-academy/pull/26 . 승인 차단 해소. e62e75c707023999d08b3b141baef9121a499ff7 기준 전체 재검사 실행 중. /tmp/run_shared_board_final_v2.py, /tmp/cma-shared-board-final-v2-suite-{0,1,2}.log 및 완료 manifest 확인. 기존 final 로그는 덮어쓰지 않는다. 코드/테스트 수정 없이 진행 중이며 완료 결과 전 통과로 집계하지 말 것.

독립 검토 wiring 수정: v8 응답의 feedback.answer 경로 사용. 기초/훈련/도전은 과거 마지막2수를 그대로 재생하지 않고 제출 수1개와 실제 전후배치의 완전일치를 먼저 확인하며, 실제 제출 수로 시작하는 기록된2수도 완전일치할 때만 선택. 따라서 과거응수+마지막수, offset불변 도전완료 모두 마지막 제출수만 표시. 저장·채점·offset 변경 없음. 실제 로컬 API 완료/중간/실패/첫수 browser5검사 + 공통core4검사=9통과(27.54초). 훈련 full-line은 임시 SQLite 계정에 합법5반수 fixture를 구성, 실제 endpoint/브라우저로 검증. v2전체는 이 실제 결함 발견으로 중단했고 최종통과로 집계하지 않는다. 다음 /tmp/run_shared_board_final_v3.py 실행/결과확인, 중복금지.

최종 확정: b7fe03bb2e18f4505c89e0951c230196c2c27f7a 전체607통과(195+240+172), final-v3-suites.json/로그 보존. 구문33통과, 최신 캡처 픽셀 확인. 이후 증거 commit은 docs만 변경. PR26 draft, 승인차단 해소. Docker/PG/운영/물리모바일은 미실행. 부모 독립검토 대기, 병합/배포/단계3 시작 금지. 테스트 생성 타 단계 캡처/캐시는 미커밋 보존.
