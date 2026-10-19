# v9.2 QA 후속 수정 및 검증 (2026-10-19)

기준 main: `1da777ade6084dea088a13bddea26b86d6e4f0f8` (작업 시작 시 fetch 확인).
배포된 QA 대상과 이 커밋이 같다는 증거는 없다. 운영 배포/병합/DB 마이그레이션은 하지 않는다.

## 근거와 수정

- 제공받은 보고서 분석: quietMove/interference 추천이 advantage로 연결되고 동일 이유로 표시됨. 클라이언트의 reason 키워드 재해석을 제거하고 catalog의 실제 이름 및 canonical ID를 사용한다. 같은 ID만 중복 제거하며, 알 수 없는 ID는 비활성화한다. catalog 준비 전 요청은 준비 완료를 기다린다.
- 제공받은 보고서 분석: 과정 완료 및 흑 불릿 시간패 후 새로고침 전 통계가 남음. 기존 `/me` 렌더링을 공통 함수로 추출하여 과정/퍼즐 완료, 일반 대국 착수·종료·시간패·기권, 홈/프로필 진입 때 부수 효과 없는 요약 갱신을 사용한다. 대국 재개나 문제 재출제를 수행하지 않는다.
- 제공받은 보고서 분석: 진단 결과 화면에도 이전 보드 클릭/임시 착수가 남음. 결과 전환에서 phase·선택·시계·입력을 함께 종료한다. 서버 최종 보드는 비활성 표시하고, recent 결과에 보드가 없으면 이전 판을 제거한다. 복구를 기다리는 동안 입력을 잠그고 요청 순서 번호로 오래된 응답을 무시한다.
- 원인 미확정: “현재 진행 중인 문제가 없습니다” 두 사례. 실패한 start/move/hint/next 이후 오래된 판을 제거하고 재시작을 안내한다. 과목 변경 후 늦게 온 응답도 무시한다. 이 조치가 서버 세션 유실 원인 해결을 의미하지 않는다.
- API에서 재현: 원본 FEN `6k1/3P1pp1/p6p/8/1p6/1P1Q3P/P5PK/2qq4 w - - 0 1`의 d7d8q/d7d8r는 모두 메이트다. 기록 수순이 남으면 기존 코드는 대체 메이트 뒤 불법 상대 응수를 push하여 예외가 났다. 확정 메이트 시 기록 수순을 종료하고 결과를 한 번만 저장하도록 수정했다. 여러 수에 걸친 동등 최선 분기 지원을 추가한 것은 아니다.

## 테스트 실행

```sh
python -m venv /tmp/cma-qa-venv
/tmp/cma-qa-venv/bin/pip install -r requirements.txt pytest httpx playwright
# Chromium 실행 파일 필요. 기본 /usr/bin/chromium; 다른 경로는 CHROMIUM_PATH 지정.
/tmp/cma-qa-venv/bin/pytest -q tests/test_qa_behavior.py tests/test_qa_browser.py
/tmp/cma-qa-venv/bin/python test_qa_work_regression.py
/tmp/cma-qa-venv/bin/python test_v9_static.py
/tmp/cma-qa-venv/bin/python -m compileall -q .
for f in public/*.js; do node --check "$f" || exit; done
git diff --check
```

API 테스트는 메모리 상태와 임시 SQLite만 사용한다. 브라우저 테스트는 임시 서버/계정을 생성하며 핵심 응답을 제어한다. 운영 계정/학습 기록에 접근하지 않는다. 브라우저의 실제 15문항 연속 풀이 또는 운영 Stockfish E2E와 동일하지 않다. API에서는 실제 문제은행의 중급 mateIn1 과정 15문항을 완주하고 결과가 한 번만 저장되는 것을 검증했다.

최종 결과: 행동 회귀 **23개 통과** (API 10개, Chromium 13개, 40.66초). Starlette/httpx deprecation 경고 1개. QA 정적 계약, v9 정적 검사, Python compileall, 전체 public JS 문법, git diff 공백 검사를 통과했다. main UI 비교에서는 종료/세션 오류/흑 불릿 관련 5개 테스트가 실패했으며 수정본에서는 통과했다. main API 비교에서는 남은 수순이 있는 대체 메이트 2개가 실패했고 수정본에서는 통과했다.

행동 검증 범위:

- API: 원본 d8 퀸/룩, 남은 수순이 있는 대체 메이트, 중복 완료 거부, 오답·힌트 정확도 보존, 세션 부재 409, 진단 시간패 뒤 착수 거부.
- 일반 대국 API: 지정한 AI 응수로 앙파상과 나이트 언더프로모션의 합법 적용/판 직렬화 확인. 실제 엔진이 그 수를 선택하는 품질은 검증하지 않았다.
- Chromium: 추천 ID/라벨/중복/미등록 ID, catalog 로딩 대기, 시간패→다른 메뉴→진단 복귀 후 입력 잠금, 실패한 임시 착수 복구 대기, 오래된 status 응답 무시, 원본 d8 퀸/룩 선택, 과정 완료 통계 즉시 갱신, 세션 부재 후 입력 잠금, 흑 불릿 시간패 통계.
- 모바일은 Chromium 390×844 viewport에서 승격 및 가로 넘침 검증. 실제 iOS/Android 기기 검증은 미실행.

기존 `test_qa_work_regression.py`의 추천 문자열 검사를 canonical ID에 맞췄다. 문제은행 파일이 없어야 한다는 ZIP 제작 환경용 조건도 존재·비어있지 않음 검사로 고쳤다. 문제은행 보존은 별도로 main 대비 Git blob 동일성을 확인했다: `efb19b7b720cc5f3a1c033c41d212c0cd708ec89`.

기존 `test_v81_regression.py`는 이전 진단 영역명 기대값에서 실패하고, `test_v3_static.py`는 v3의 2개 script 목록 기대값에서 실패한다. 두 실패는 변경 전 main에서도 동일하다. 이 테스트들을 통과로 기록하지 않는다. 저장소에는 별도의 타입 검사/린트 설정과 GitHub Actions workflow가 없으며, 타입 검사 및 전용 린트는 미실행이다.

## 남은 제한

- Library ID `libfile_e9209a9182e88191a05e1bd67fd93e09`, `Chess_Master_Academy_v9_2_QA_Report.zip`: 현재 Library skill의 resolved-reference materialization 및 현재 전송 helper를 사용했으나 두 번 모두 `library file transfer failed: download failed`. 로컬 ZIP이 생성되지 않아 report.html과 스크린샷은 직접 열지 못했다. 원격 materialization 준비는 성공했으나 바이트 전송은 실패했다. 제공된 후속 분석을 보고서 근거로 사용했다. 보고서 이미지는 저장소에 포함하지 않는다.
- 계정 전체 JSON read/modify/write의 lost-update 위험은 코드상 존재하지만 보고된 세션 부재의 원인이나 실제 데이터 손실로 확인되지 않았다. 스키마·저장 경로·운영 DB는 변경하지 않았다. 서버 다중 탭/동시 요청의 원자성은 별도 작업이 필요하다.
- QA-02/04/06~11의 보고서상 해결 상태를 전체 재검증 완료로 확대하지 않는다. 낮은 우선순위인 백/흑 설명 라벨, 정확도 대비 칭찬 문구, UI 버전 표시는 이번 수정 범위에 포함하지 않았다.
- 원본 보고서 시각 검토, 운영 배포 검증, 전체 49문항+AI 평가 완주, 실제 엔진 선택 품질, 실제 모바일 기기 테스트는 미실행이다.
