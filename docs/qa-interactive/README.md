# 로컬 검증 증거

운영 계정이나 운영 DB를 사용하지 않았다. 브라우저는 설치된 Chromium의 headless 실행이다. 실제 휴대폰 및 Safari 검증은 아니다.

- `opening-390.png`, `opening-1280.png`: 실제 임시 계정/API. 프렌치 어드밴스 6반수 입력과 c5 해설, 다른 화면 복귀, 혼자 풀기의 후보 숨김, 저장·새로고침, 미등록 합법 수, 초기화 및 참고 검색을 검사한 화면.
- `review-original-preserved.png`: 원본 기보 응답은 제어된 2반수 fixture, 분기 합법 수는 실제 API. 흑 시점, 이전/다음, 네트워크 실패 복원, 원본 복귀 후 늦은 엔진 응답 무시, 원본 JSON 및 계정 상태 불변을 검사했다.
- `diagnosis-five-complete.png`: 실제 임시 계정/API에서 충분한 진단 응답으로 분야 점수·성장 비교 조건을 만든 후 추천 5개 완료와 재진단 해제를 확인했다.
- `latest-image-http.json`: 최종 로컬 이미지의 실제 HTTP/Stockfish/PostgreSQL 결과. 1CPU·512MiB, OOM 없음. 운영 당시 판정 보류의 원인을 소급 증명하는 자료는 아니다.
- `image-source-hashes.json`: 검증 이미지의 애플리케이션 Python·JS/CSS/정적 자료·오프닝 원본·requirements 81개 파일 SHA256. 작업 트리와 일치함을 확인했다.

이미지: `cma-interactive:review`, SHA256 `699f245af594b68dc95fe384eb3683311a6e3c57ffd36d00238c848279b6f78b`.
