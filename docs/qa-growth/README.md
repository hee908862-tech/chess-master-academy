# 성장 주기 화면 검증

임시 로컬 계정과 Chromium으로 생성했다. `tests/test_growth_browser.py`는 실제 브라우저에 제어된 완료/부분/미응답/오류/로딩 응답을 주입한다. 운영 계정이나 실제 사용자의 실력 수치가 아니다. 긴 한국어 설명은 줄바꿈 스트레스 사례다.

- `home-*`, `diagnosis-*`, `profile-*`: 320/360/390/430/768/900/1024/1280/1440px. 홈·진단·프로필 캡처와 훈련·도움말·복기 가로 넘침 검사를 수행한다.
- `empty-error-200percent.png`: 점수가 없는 진단, 분석 API 오류/재시도, Chromium CSS zoom 200%. 실제 브라우저 네이티브 확대나 물리 기기 배율과 동일하다고 주장하지 않는다.
- `partial-analysis-loading.png`: 간이/부분/결측 진단 사이의 선 끊김과 분석 중 대국에 점수를 만들지 않는 상태.

별도의 `tests/test_journey_browser.py`는 실제 로컬 API로 24문항 건너뛰기→저장·재개→미관찰 결과→원본 추천 훈련 연결을 PC/모바일에서 검사한다. 추가된 `tests/test_growth_real_browser.py`는 실제 API에서 정답·부분 수행을 포함한 진단, 기존 개념 경로와 추천 과제 충돌, 추천5개 실제 완주, 힌트 후 새로고침 재개, 재진단 해제와 새 주기 생성을 확인한다. 모든 진단 문항을 정답 처리했다고 주장하지 않는다.

최종 실행 수와 한계는 [성장 주기 안내](../../README_GROWTH_CYCLE.md)에 기록한다.

- `real-five-tasks-unlocked.png`: 실제 API/브라우저에서 추천5개 완료 후 재진단 해제.
- `internal-rating-unlimited.png`, `internal-rating-bullet.png`: 제어된 응답으로 시계별 내부 베타 지표·전후 값·제외 사유 표시를 확인한 캡처다. 실제 AI 대국의 갱신·복원은 별도 HTTP 검사로 검증했다.
- `review-old-512m-oom.json`, `review-engine-overlap.json`: 이전 이미지의 동시 엔진 OOM 재현과 최종 이미지의 512MiB 동시 부하 결과.
- `review-image-http.json`, `review-image-source-sha256.json`: 최종 이미지 실제 HTTP/재시작 결과와 소스 일치 목록.

최신 결과·한계는 [후속 검증 문서](../../README_REVIEW_BETA_RATING.md)를 기준으로 한다.
