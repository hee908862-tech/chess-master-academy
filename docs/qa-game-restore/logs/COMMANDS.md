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
