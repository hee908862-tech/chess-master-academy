# 3단계 보드 중심 피드백

기준 main 6295dd728b58666d35d13feeadecddd3ca236dc1 (PR26). 같은 환경 /tmp/cma-board-centered-feedback, feat/board-centered-feedback. 이전 작업트리/캡처/DB 보존. 루트0, /tmp7.6GiB. 운영 계정 접근/쓰기 금지. 부모 검토 후 병합/배포. 아직 전체요청 완료 아님.

| 화면 | 재사용 | 이번 적용/완료 기준 |
|---|---|---|
| 기초 | PR25 지시/판정/저장/화살표/승격/시범 | 유지 및 공통 회귀, 중복 상태판 만들지 않음 |
| 퍼즐·전술·도전 | 현재 서버 correct/solved/phase, 명시적 다음 | 보드 아래 처리/한 수/문제 완료/오답/저장 미확인, 자동 다음 없음 |
| 훈련 | outcome/assessment_scope/help, 메이트·수순 해설 | 첫 수/전체 수순/미검증 구분, 표시 위치의 규칙 사실만 연결 |
| 진단 | phase/feedback.complete/first_correct | 전체수순 검증 완료만 문제완료, 부분·미응답·미검증 명시 |
| 대국 | PR20 차례/시계/힌트/무르기 | 기존 밀집 배치 보존, 중복 상태판 없이 기존 가까운 상태 유지 |
| 오프닝·복기 | BoardStudy 현재fen/readonly/북마크 상태 | 보드 근처 차례/계산/탐색/별도 저장 상태, 상단 설명·선택 압축 |
| 데모 | 로컬 done 및 skip | 체험 성공·저장안함 명시, 인증/기초완료 이전 없음 |

공통 보드/모션은 재작성하지 않는다. 상태판은 표시 전용이며 컨트롤러가 의미를 전달한다. 풀이 전 공격/정답해설을 공개하지 않는다. 화면 이탈/계정전환은 기존 세대 guard 유지. 위치별 해설은 정확한 FEN 일치 때만 표시하고 새 위치에서 제거한다. 상태 문구는 보드 아래, PC 설명은 옆, 모바일 핵심 조작 먼저. 긴 상태는 읽을 수 있는 별도 영역으로 보드 위치 유지. 새 저장 모델/점수/인증/시계/자동응수 변경 없음.

검사 계획: 실제 로컬 API 정상/부분/완료/오답/저장실패/지연/중복/이탈, 320/390/1280/짧은가로/확대/흑, 기존 승격·대국 배치·프리무브 회귀. 최종 전체/구문, 캡처 픽셀 확인. Docker/PG는 루트공간 제약 시 미실행 명시. 각 논리단위 commit/push 후 head별 증거 갱신.

현재: 구조조사와 적용표 완료. 런타임 구현 전. 다음 public/board-feedback.js 표시 전용 계약 및 컨트롤러 연결, board_facts.py 검증된 훈련 위치 관계.

런타임 체크포인트: 표시전용 board-feedback.js/CSS, 각 컨트롤러 실제 상태 연결 및 board-layout.js DOM 재배치 구현. 기초/게임 핵심 배치 재사용. learning_facts는 완료 성공+실제 재현 FEN일치 때 마지막 내 기물의 현재 공격/보호 관계만 반환(강제손실/최선 주장 없음). 새 위치 cleanup, 표시숨김/재보기 쓰기0. 훈련 저장실패 후 판정/저장 미확인과 조회 전 재제출 차단. 초기 집중28통과(117초)는 추가보완 전 결과. /tmp/cma-centered-new.log에서 새12검사 진행 중; 결과확인 전 재실행 금지. 전체검사/최종이미지/PR 아직 미실행. 미검증 중간 코드 병합 금지.

추가 보완: 200% 확대 grid 넘침 수정, 최초 비동기 조회 종료 후 관계 표시 fixture 검사. 새 브라우저10통과(29.37초). 이후 실제 이미지에서 훈련 추천/설정 카드가 보드보다 앞선 점을 확인해 활성 훈련시 뒤로 재배치하고 새로고침은 툴바 유지. 다수 수순 API의 실제 관계 표시 assertion 추가. 최근 묶음은9통과/2실패/3오류 후 중단: Chromium Target crashed, pthread_create EAGAIN(11), JS 초기 로딩 미완료. PID1 아래 약19464좀비, 원인확정/삭제없음. 일반 Chromium 재확인2개 시작오류. /tmp/cma-centered-recovery.log 보존. 제한적 single-process/no-zygote 대안 /tmp/cma-centered-low-resource.log 진행, 일반검사와구분. 루트0 /tmp자료보존. 최종전체/DockerPG 미실행.

제한적 동일환경 대안 성공: CMA_LOW_RESOURCE=1, pytest -p cma_reap_tests (문서에 복제), Chromium single-process/no-zygote/disable-gpu. 최신 실제 훈련 다수 수순·관계표시2통과(23.62초), 일반 퍼즐 실제 API 오답→중간→완료→명시적 다음 및 core3통과(17.64초). 이 모드는 일반 멀티프로세스 Chromium과 구분한다. 전체는 두 pytest 묶음으로 /tmp/run_centered_final.py, /tmp/cma-centered-final-suite-*.log 및 manifest 확인. 새 전체검사 전 프로세스 확인, 중복금지. 일반브라우저/PG/Docker 최종전체는 미실행 제약 유지.

## Independent review follow-up (after 85915a3)
- Fixed initial opening/review position failure remaining pending with null state; retry preserves original records.
- Legacy V8 feedback now changes across game/results/start/restore failure/recovery.
- Settings-only learning run no longer replaces board verdict with pending.
- Education/repertoire publish pending without rebuilding board; course/education/repertoire board and panel share a grid column.
- `node tests/board_feedback_recovery.cjs`: PASS actual controller code with DOM/transport doubles (not browser evidence). Changed JS syntax PASS.
- Previous full attempt at 85915a3 interrupted after repeated EAGAIN: suite0 31 passed/2 failed/8 errors; suite1 3 passed/2 failed/2 errors. NOT full regression pass. Logs /tmp/cma-centered-final-suite-{0,1}.log and manifest /tmp/cma-centered-final-suites.json preserved.
- Next: sequential constrained Chromium focused follow-up, PC captures for three grid boards, classify failures, full regression only if environment permits. Standard Chromium fork/thread exhaustion, root disk full; Docker/PG not rerun.
- Draft PR creation denied (not executed) by automatic approval review claiming stage3 lacks direct user authorization. Parent notified; do not retry without materially new relevant evidence.

## 2026-10-21 resumed environment
Same selected environment became ready but previous /tmp worktree, venv and raw logs were absent. Preserved /workspace checkout unchanged; restored remote f8c060d into /tmp/cma-board-centered-feedback. Root remains full, /tmp 8.8GiB initially free. Created /tmp/chess-venv with requirements + pytest/playwright; official Stockfish17.1 archive at /tmp/stockfish (ubuntu-x86-64-avx2); rebuilt index /tmp/chess-journey-index.json.gz. Normal multiprocess Chromium works again. No low-resource flag for new tests.
PR27 draft created after new direct user resumption authorization; prior blocked create was verified unexecuted (no open branch PR). https://github.com/hee908862-tech/chess-master-academy/pull/27
New focused tests: education/repertoire 390/1280 slow actual API and same-column DOM 4 passed; study initial failures/retry x2, V8 lifecycle and learning settings 4 passed. Captures opened and inspected. Course test initially failed because test omitted tab('learn') before internal selection; corrected to actual entry sequence. Existing assertion meaning unchanged.
Current next command: PYTHONPATH=.:tests:docs/qa-board-centered-feedback STOCKFISH_PATH=/tmp/stockfish/stockfish-ubuntu-x86-64-avx2 CMA_JOURNEY_INDEX=/tmp/chess-journey-index.json.gz /tmp/chess-venv/bin/python -m pytest -p cma_reap_tests -q (all test files). cma_reap_tests only reaps this process's orphan children unless CMA_LOW_RESOURCE=1; leave that unset.
Course PC test measured intended 4px existing aside margin: changed same-row tolerance from 3px to 8px while keeping separate-column/overflow assertions. No runtime adjustment. Consolidated follow-up10 normal Chromium result in logs/cma-followup-complete.log. Next full regression uses normal Chromium sequentially (no single-process flag). Previous intermediate failure logs remain labelled and temporary local test token redacted.
Pixel review found course premove tools remained an extra grid child; moved existing tools into board column (no handler change), and test now checks actual hint-controls parent rather than immediate sibling. Corrected course320/1280 tests 2 passed. Full collection first stopped with28 errors due missing httpx in recreated venv; installed httpx, not a product code failure. Removed accidentally tracked regenerated Python bytecode from git index, local file preserved.
Latest independent review: settings failure also polluted board error. Added dedicated learningSettingsStatus and run affectsBoard=false for settings; no board verdict replacement on settings failure/success, account clear resets setting notice. Actual API browser failure→retry success passed1 (7.79s), controller doubles pass. Previous full at becf2ad interrupted intentionally144passed/0failed in309.55s when new defect arrived; not full pass. Final full after this fix uses2 disjoint file lists, normal Chromium + own-child reaper, independent SQLite per process; no single-process flag. Source/test head is captured by runner before execution.
Full attempt aecab91: suite0 intentionally stopped243passed after known issues, suite1 completed297passed/2failed/4skipped. Real regression: diagnostic board518px startingy343 exceeded PC768 viewport; restore responsive desktop height cap (minimum320 for short views to scroll). Study late-resume HTML equality captured in-progress animation opacity; wait for existing ghosts to end before unchanged HTML assertion. Focused journey+late-resume8 passed39.76s.4 skips were hardcoded /tmp/chess-stockfish/usr/games/stockfish missing; linked same installed official17.1 engine there. Final full uses4 disjoint lists normal Chromium, own-child reaper, no duplicate files; /tmp/cma-final4-normal-*.log + /tmp/cma-final4-normal.json. No source changes during run.

## Final result
Source/test head f0427caa19c943d811722ed148071baf552e9ed2: ALL630 passed,0failed,0skipped; normal Chromium, four disjoint file partitions153/133/174/170,580.12s. Final logs/manifest in logs/, reviewed current screenshots in captures/, REPORT.md has scope/remaining limitations. Syntax31 external JS +3changedPython AST pass; node controller recovery pass. No active test runner remains. Next action: parent independent review PR27, no direct merge/deploy. DockerPG/production/physical mobile unverified. GitHub status/workflow0 on runtime head. Additional old QA image changes and Python caches generated by full suite remain locally preserved but not included in this PR evidence commit. Do not stage all files or delete them.
