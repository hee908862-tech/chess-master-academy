# 기초 보드 피드백 PR1 재개 기록
기준 main: 8dbee0b80a03b7003d775312fcc5d8918b5e881e. 브랜치 feat/foundation-board-feedback.
범위: 기초10과정26단계의 안내/판정·저장 표시/승격/앙파상 교육예시/위협·보호 해설. 다른 화면의 전체 모션/레이아웃 적용은 후속 PR.
현재: 서버 표시 메타데이터/상호작용 결과 및 규칙 검사 구현. 서버 8개 통과 (/tmp/cma-foundation-server-final.log). UI는 로컬 구현 중이며 브라우저 8통과7실패: 승격 버튼의 기물 문자 포함 접근성 이름에 테스트 불일치, 저장 실패 복구 버튼 비활성 결함 확인 후 보완 중. 전체 검사는 아직 미실행. 기존 기록·운영 QA에 쓰기하지 않음.
환경: 같은 환경 /tmp/cma-foundation-feedback; /tmp 약7.8GiB, 루트0. Docker/PG 미검증 제한 유지.
실행: PYTHONPATH=tests STOCKFISH_PATH=/tmp/chess-stockfish/usr/games/stockfish CMA_JOURNEY_INDEX=/tmp/chess-journey-index.json.gz /tmp/chess-venv/bin/python -m pytest tests/test_foundations.py tests/test_foundations_browser.py -q
다음: 서버 읽기 전용 표시 메타데이터·규칙 테스트, 기초 전용 UI, 브라우저 경합/배치 검사, 최종 전체 회귀.
주의: 서버 CAS/기초 완료·진단·도움 집계 보존. GET/재보기는 쓰기0. 실패/미확인 저장을 성공으로 표시하지 않음. 기존 타 worktree의 미커밋 캡처를 지우지 않음. 실제 사용량/미저장 작업 복구 보장 없음.
