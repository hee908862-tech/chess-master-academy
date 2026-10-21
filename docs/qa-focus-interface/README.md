# 집중형 UI 검증 근거

검사 코드: `19992bf8ac980ce0543ef56c6fbda6090fdad4ba`, 기준 main: `931fc3d0d15ac6a8249d7f044d595dff0e25614b`.

## 요구사항과 반영

| 요구 | 구현 | 증거 |
|---|---|---|
| 기초 보드·판정·다음 중심 | 기존 노드를 PC 옆 패널/모바일 보드 아래로 이동, 짧은 이유와 상세 펼침 | `test_focus_interface_browser`, 6개 viewport 캡처 |
| 활동과 선택/기록 분리 | 훈련 Library/현재 훈련, 교육·레퍼토리 범위/기록/상세 패널 | `test_focus_panels_browser`, `test_focus_lessons_browser` |
| 기능 유지 | 기존 소유 컨트롤러와 버튼/이벤트 재사용 | `feature-map.csv` 58행, `source-control-index.tsv`, 기존 전체 회귀 |
| 내 정보/설정/계정 구분 | 허용된 profile 하위 UI 경로, hidden/inert와 포커스 | PC/320/390 패널 검사, 기존 인증/계정 전환 회귀 |
| 설정 실제 값 보존 | 조회 준비 잠금, 실패/재조회, 계정 및 요청 세대 검증 | 지연 조회+실제 B 로그인, 늦은 저장 실패, 같은 화면 저장 중 재진입 |
| 게스트 확대/정확성 | 기존 비숍·나이트·한 수 메이트, 로컬 임시 상태 | Python 합법 수 전수 대조, 무서버쓰기, 새로고침/뒤로/오류/연속 키보드 |
| 배포 포함 | 기존 Docker public 디렉터리 COPY 재사용 | `test_image_runtime_package.py`의 import/COPY/static 검사 |

## 결과 구분

- 단계1: 31건 통과(원격 ecc78ad). 전체 최종 결과와 구분한다.
- 최초 전체 e535fa3: 648통과/12실패, 총660, 누락·중복0. 원시 결과는 `full-e535/`.
- 중간 선택군 b712: 59통과/8실패 후 중단, 미실행 나머지 존재. 원시 로그 보존.
- 후속 선택군: 40통과/3실패. 남은3건은 복원 조회 전 선택 화면을 클릭하던 검사 동기화; 조회 및 실제 active 보드 준비 후 공개 선택 경로를 거치게 수정했다.
- 최신 반응형9건 전부 통과. 실제 판정·데이터·포커스·폭 assertion을 유지했다.
- 변경 JavaScript12개 `node --check`, Python 생성기 `py_compile` 통과.
- 전체17c4d8b: 671통과/1실패,672실행,누락/중복0. 새 계정 검사가 /me의 user 갱신만으로 로그인 완료를 판단했다. /game 지연→홈 복귀 완료→설정 이동으로 동기화 보완; 기존 설정값·버튼 활성 assertion과 늦은 A 응답 검증 유지. 런타임 추가 변경 없음. 원인 한정 검사1건 통과. 원시 로그 `full-17c4/`.
- 최종 전체672건: **672통과/실패0/오류0/건너뜀0**, 681.78초. 수집672/실행672, 누락0/중복0/예상외0. `full-final/verification.json`과 4개 원시 로그/JUnit/manifest에 확정. 정상 Chromium·격리 SQLite 실행. 코드·검사 파일 SHA256 대조 일치. Starlette httpx 사용 중단 예정 경고가 각 군1개이며 실패가 아니다.

## 실행 방법과 한계

`PYTHONPATH=.:tests:docs/qa-board-centered-feedback`, `STOCKFISH_PATH=/tmp/stockfish/stockfish-ubuntu-x86-64-avx2`, `CMA_JOURNEY_INDEX=/tmp/chess-journey-index.json.gz`를 사용한다. 최종 실행 스크립트는 파일 단위로 4개 격리 SQLite 검사군에 배분하고 정상 multiprocess Chromium을 사용한다. 로그·JUnit·수집 목록과 동일 코드 SHA를 보존한다.

실제 Docker 빌드/컨테이너 HTTP 및 PostgreSQL은 루트 디스크0 여유로 **미실행**. 패키징 검사 통과를 실제 이미지 실행으로 주장하지 않는다. 물리 모바일, 실제 초보자 사용성, 운영 계정 QA 역시 이 로컬 검증에 포함하지 않는다. 긴 문장·짧은 화면·모바일의 긴 조작에는 문서 스크롤을 허용한다. 운영 DB/계정/기보 변경이나 사용자 기록 초기화, 병합·배포를 실행하지 않았다. 테스트는 임시 로컬 계정/격리 DB 또는 제어된 응답 대역을 사용한다.
