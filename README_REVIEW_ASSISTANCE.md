# AI 대국 복기의 힌트·무르기 출처 표시

기준 main: `2ae4c9a22e49d50238dcb002ea4cdf4c733f8715`.
이 문서는 PR #4 최초 도움 표시 구현 기록이다. 이후 승인된 오류·사용성 수정은 [후속 QA 보고서](README_QA_POSTLIVE.md)에 정리한다. 기존 도움 표시를 유지하며 같은 초안 PR을 확장했다. 병합·배포하지 않는다.

## 원인과 구현

기존 `hint_plies`는 다음 반수 번호만 저장했다. 추천 수와 실제 착수의 일치 여부를 알 수 없고, 무르기로 수순을 바꾸면 같은 반수의 다른 위치에 잘못 표시할 수 있었다. 무르기 자체의 기록도 없었다.

새 대국의 `assistance`에는 버전, 도움 사건, 위치별 도움 참조, 실제 착수별 고유 ID/반수/전체 FEN/UCI를 저장한다. 도움 사건은 당시 수순 prefix와 위치를 함께 갖는다. 힌트 사건에는 실제 제공한 추천 UCI가 있다. 실제 합법 착수가 저장될 때 제공된 추천과 일치하는지 판정한다. 여러 추천을 받았다면 그 중 하나와 일치하는 경우 채택으로 표시한다.

무르기는 제거된 수의 반수·FEN·UCI·기존 착수 ID 및 도움 참조를 사건에 보존하고, 현재 기보의 착수 목록만 잘라낸다. 복원 위치의 다음 재착수에는 새로운 착수 ID와 무르기 참조를 부여한다. 제거된 수에 붙었던 도움을 단순히 같은 반수의 다른 위치에 복사하지 않는다. 같은 대국에서 동일 위치로 되돌아오면 앞서 제공한 힌트/무르기 기록을 유지한다. 위치 동일성은 기물 배치·차례·캐슬링 권한·앙파상 권한으로 판단하며 반수/반복 시계 숫자는 제외한다.

- `힌트 채택`: 제공된 추천과 실제 착수가 일치.
- `힌트 제공 · 다른 수`: 이 위치에서 추천은 제공했지만 실제 수는 다름.
- `무르기 후 재착수`: 되돌린 위치에서 다시 둔 수. 힌트 라벨과 함께 표시 가능.
- `도움 기록 없음`: 과거 데이터에 위치별 근거가 없음. 사용 안 함으로 추정하지 않음.
- `도움 제공 기록 없음`: 처음부터 추적된 새 대국의 해당 수에 기록된 도움이 없음.
- `이전 도움 기록 불명`: 구형 진행 대국을 이어서 사용해, 새 도움은 알지만 과거 도움 부재를 보장할 수 없음.
- AI의 수는 `AI 착수`로 표시한다.

복기 API는 반수/FEN/UCI가 저장된 착수와 모두 맞을 때만 라벨 근거를 돌려준다. 오래된 `hint_plies`만으로는 라벨을 복원하지 않는다. 해당 레거시 필드는 호환을 위해 보존한다. 기권/시계 종료/규칙 종료 모두 대국 session ID와 사건 목록을 완성 기록에 복사한다. 새 게임에는 새 기록을 사용한다. 계정/PIN/기존 기록/문제은행을 삭제하거나 초기화하지 않는다.

## 요청 및 저장 경계

힌트/무르기는 선택적 session ID와 expected FEN을 검사한다. 새 UI는 이를 보내며 대기 중 다른 착수를 막고, 응답 후 계정/게임 변경을 확인한다. 종료 시간·내 차례·합법 추천·되돌릴 내 수가 있는지 확인한 뒤 저장한다. 흑의 첫 착수가 아직 없으면 AI 첫 수만 무르는 요청을 거절한다. 불법 수와 실패한 AI 응답은 도움 적용 기록을 커밋하지 않는다.

같은 계정의 new/get/move/resign/hint/undo는 프로세스 내 계정별 RLock으로 순서를 보장한다. 엔진 대기 중 공유 DB lock을 점유하지 않아 다른 계정의 DB 접근을 불필요하게 막지 않는다. 후속 수정에서 progress JSON의 변경 필드 병합과 동일 필드 충돌 거절을 DB 트랜잭션으로 추가했다. SQLite 경합 회귀는 통과했지만 운영 PostgreSQL/여러 서버 실행 검증은 하지 않았다. 외부 DB 스키마/서비스/환경 설정 변경은 없다. 모든 도움 기록은 해당 계정의 기존 저장소에만 저장하며 외부 분석 서비스로 전송하지 않는다.

서버가 힌트를 제공한 사실을 기록하며, 네트워크 응답 유실이나 사용자가 실제로 화면을 읽었는지는 판별하지 않는다. 성공 응답을 잃어버린 무르기 역시 실제 저장 상태가 기준이다. 브라우저 재접속은 서버 상태를 복원한다.

## 검증 방법

```sh
python -m pytest -q tests/test_review_assistance.py tests/test_review_assistance_browser.py
python -m pytest -q tests/test_learning.py tests/test_learning_browser.py tests/test_board_interaction.py tests/test_qa_behavior.py tests/test_qa_browser.py tests/test_qa_followup_browser.py
python test_qa_work_regression.py
python test_v9_static.py
python -m compileall -q assistance.py server.py v7_server.py tests
for f in public/*.js; do node --check "$f" || exit; done
git diff --check
```

API는 임시 SQLite/실제 인증·저장 경로를 사용하고 AI 선택만 제어한다. 힌트만/무르기만/둘 다/다른 수/여러 번 무르기/분기 뒤 같은 반수/흑 ply/저장 복원/과거 기록/새 게임/종료/실패/동시 힌트를 검사한다. 실제 체크메이트 API 종료도 확인한다.

Chromium은 실제 로컬 API로 힌트 → 착수 → 무르기 → reload → 재착수 → 기권 → 복기 → reload를 수행한다. 1440×1000 및 390×844에서 두 라벨과 선택 수 설명을 확인한다. 별도 제어 응답 테스트는 추천과 다른 수 및 레거시 무근거 라벨을 확인한다. 운영 사용자 계정이나 실서비스 기록은 사용하지 않는다. 실제 iOS/Android 기기 및 다중 서버 경쟁은 미검증이다.

## 최종 결과와 별도 발견

- 신규 **15개 통과**: API 12개, Chromium 3개. 24.92초. 마지막 응답의 session ID 노출 추가 후 API 12개도 재확인했다.
- 기존 행동 회귀 **100개 통과**, 216.10초. 계정별 동시 요청 보호 조정 후 핵심 기존 API 16개도 별도로 통과했다.
- Python/전체 public JS 구문, QA 정적 계약, v9 정적 검사, git diff check 통과. Starlette/httpx deprecation 경고 1개.
- `test_v81_regression.py`는 구형 7영역명 기대값, `test_v3_static.py`는 구형 script 목록 기대값에서 기존과 동일하게 실패. 전용 lint/type 설정은 없어 미실행.
- 문제은행 blob은 main과 동일한 `efb19b7b720cc5f3a1c033c41d212c0cd708ec89`.
- [PC 캡처](docs/qa-review-assistance/review-assistance-1440.png), [모바일 캡처](docs/qa-review-assistance/review-assistance-390.png): 임시 로컬 QA 계정의 실제 Chromium 이미지이며 직접 열어 확인했다. 운영 사이트 QA나 물리 모바일 테스트가 아니다.

최초 구현 때 발견했고 이번 후속 수정에서 해결한 문제: 복기 재진입 직후 대국 목록 응답이 오기 전에 `이 대국 분석`을 누르면 초기 옵션 문자열이 index로 전송되어 `Input should be a valid integer, unable to parse string as an integer`가 표시될 수 있다. 기존 v5HistoryList의 비동기 완료 전에 분석 버튼이 활성인 경로다. 후속 승인에 따라 목록 로딩/실패/빈 상태에서는 분석을 막고 서버에도 명확한 입력 검증을 추가했다. 라벨 테스트의 저장된 대국 선택값 동기화도 유지한다.
