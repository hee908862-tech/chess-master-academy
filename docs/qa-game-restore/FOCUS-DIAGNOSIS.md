# 교육 → 관련 기초 포커스 검사 한정 진단

## 원본 실패
79011c0 전체645 중 `tests/test_education_browser.py:96`의 즉시 `document.activeElement.dataset.course == 'king-check'` assertion이 None으로 실패했다. 목록 open 및 대상 카드 visible은 앞서 통과했다. 원본 로그는 activeElement의 id/tag를 수집하지 않았으므로 당시 실제 대상을 소급 확정하지 않는다.

## 선행 조건과 재현
원본은 모듈 단위 로컬 서버/SQLite, 테스트별 새 Chromium/page, enter()에서 새 임시 계정 생성. 앞선 동일 파일 테스트는 다른 임시 계정을 사용한다. 교육 탭 진입 및 계정별 기초 조회로 카드가 미리 렌더될 수 있다. 전체는4개 pytest 프로세스 병렬 실행이었다. 프로세스 부하가 직접 원인이었다는 증거는 없다.

최소 재현은 같은 실제 컨트롤러/API에서 현재 계정 기초를 한 번 조회하여 캐시를 만들고 다음 /foundations 응답만 보류한다. 클릭 후 기존 두 visible/open 조건이 모두 통과하지만 H2 `foundationHeading`에 포커스가 있다. 응답 해제 후 ARTICLE `foundation-card-king-check`로 이동하고 300ms 후에도 유지된다. GET1회/POST0, 서버 기초 데이터 불변.
순서: 클릭 BUTTON → foundationHeading → GET 응답 해제 → foundation-card-king-check. logs/focus-timeline.json 및 focus-diagnosis.log, 재현 파일 focus_diagnosis.py. 1통과8.48초.

## 원인과 최소 보완
learning-navigation.go()가 목록을 표시하고 제목에 먼저 포커스한다. education.js의 클릭 handler는 cmaFoundations.load()를 await한 뒤 목표 카드로 이동한다. 캐시된 카드 visible은 이 await의 완료 신호가 아니다. 재현에서 제품의 의도한 목표 포커스는 정상 완료되므로 확인된 문제는 검사 동기화이다.
기존 즉시 assertion을 Playwright `expect(exact target).to_be_focused()`로 바꾼다(기존6초 timeout 유지). 다른 대상 허용/고정 sleep/포커스 검사 삭제 없음. 보류된 GET 전 제목 포커스, 해제 후 정확한 카드 포커스, 쓰기0/기존 상태 불변을 별도 회귀로 추가한다. 런타임 변경 없음.

## SHA 차이 및 검사 계획
7c36cc6→79011c0: public/ 및 서버 코드 차이0. tests/test_puzzle_catalog_ready.py에서 독립 추천 GET과 재시도 GET 집계를 구분했고 나머지는 문서/로그다. 교육 런타임/기존 포커스 테스트는 이 구간에서 바뀌지 않았다.
먼저 교육 브라우저 모듈 전체를 실행하여 앞선 테스트 순서를 포함한다. 최종 전체는 지금 반복 실행하지 않는다. 644/1 결과는 이전 실행의 사실로 유지하고 후속 focused 결과를 분리한다. 추가 기능/감사/운영 접근 없음.

후속 검사: tests/test_education_browser.py 전체12통과,43.98초(logs/education-focus-fixed-12.log). 기존 선행 테스트11개와 새 지연응답1개 포함. diff --check 통과. 전체646건 재실행은 아직 하지 않음.
