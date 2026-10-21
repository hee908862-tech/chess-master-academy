# 집중 검사 명령

공통 환경:
```
PYTHONPATH=.:tests:docs/qa-board-centered-feedback
STOCKFISH_PATH=/tmp/stockfish/stockfish-ubuntu-x86-64-avx2
CMA_JOURNEY_INDEX=/tmp/chess-journey-index.json.gz
```
위 환경에서 `/tmp/chess-venv/bin/python -m pytest -p cma_reap_tests -q` 실행.
- account-race-7.log: `tests/test_game_restore_feedback.py tests/test_refresh_identity.py` (3fbfe9f 코드)
- review-context-12.log: `tests/test_review_context_feedback.py tests/test_study_browser.py tests/test_review_assistance_browser.py` (a177c22의 문구 수정)
- review-owner-14.log: 같은 명령, A→B 로그인 및 늦은 성공/실패 2개 회귀 추가 후. 이후 테스트에 로그인 완료 버튼 활성 대기도 추가했다. 최종 전체 실행이 최종 테스트 소스의 근거다.

모든 계정과 서버는 임시 로컬 SQLite이며 운영 계정/기보를 사용하지 않았다.

카탈로그 보완 ba13b6c:
- catalog-fix-14.log: 같은 공통 환경 + `tests/test_puzzle_catalog_ready.py tests/test_board_feedback_browser.py` (14 통과).
- 이전 catalog-diagnosis.log / catalog_diagnosis.py는 수정 전 0459e5d의 실패 원인 재현 자료로 유지한다.

7c36cc6 최종 카탈로그 보완: 같은 집중 명령으로 catalog-confirmed-14.log (14 통과). 빈 보드 실패 안내를 함께 검증하며, 파라미터별 별도 계정을 사용해 기존 문제 복원 검사와 구분한다.

79011c0 최종 테스트 보완: 같은 집중 명령으로 catalog-synced-14.log (14 통과, 46.03초). 독립 v8 추천 카탈로그 조회를 먼저 관찰한 다음 퍼즐 재시도의 증가분을 검사한다. 제출 차단·중복 클릭·실패·준비 후 정상 출제 assertion을 유지했다.
별도 이미지 검사: 같은 환경에서 `pytest -p cma_reap_tests -q /tmp/pr29_catalog_visual.py` (1 통과, 22.01초). 재현 파일 catalog_visual.py; 로컬 API 및 공개 카탈로그 응답 대역, 390/1280 CSS. 전체 645에 합산하지 않음.
최종 전체 명령은 verified-final/runner.py, 수집 대조는 verified-final/audit.py에 보존 예정.

최종 79011c0: verified-final/runner.py 4묶음 실행, collection.log의645 node ID와 audit.py JUnit 대조. 실패1로 audit 마지막 all-pass assertion은 실패함(의도된 정직한 결과).
동일 코드 단독 재확인: 공통 환경 + `tests/test_education_browser.py::test_prerequisite_link_opens_exact_existing_card_without_writes` → education-focus-recheck.log, 1통과. 전체 실패를 대체하지 않음.
