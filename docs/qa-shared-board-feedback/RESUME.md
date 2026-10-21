# 2단계 공통 보드 체크·모션 재개

상태: 구조 조사/설계 체크포인트. 런타임 구현·검사는 아직 시작하지 않음. PR25의 추가 검토 지적을 우선 수정한다.

- 작업트리 /tmp/cma-shared-board-feedback, 브랜치 feat/shared-board-feedback.
- 의존 기준: feat/foundation-board-feedback의 590bde31d71f2236215b519599e0f862cf9d504d (PR25 미병합). 후속 PR은 이 브랜치 의존을 명시하고 부모가 PR25 병합 후 main 기준으로 정리한다.
- 운영 계정/기보/학습 상태는 변경하지 않는다. 기존 /tmp/cma-foundation-feedback의 증거/미커밋 생성 캡처를 보존한다. 루트0, /tmp 여유 약7.7GiB. Docker/PG 제약 지속.

## 확인한 구조

- public/app.js drawBoard는 모든 칸을 재생성한다. animateBoardTransition은 대국의 한 기물 ghost만 이동하며 210ms Web Animations를 사용한다. 캐슬링 두 기물/앙파상/승격/역방향 및 공통 cancellation/reduced-motion은 별도 보강 대상이다.
- server.py의 대국 응답에는 fen/check/last_move/ply가 있다. study_server.py view는 fen/legal/terminal/ending을 반환하며 체크킹 좌표는 없다. public/study.js의 draw는 현재 cursor의 state.fen을 사용한다. 과거 복기 위치는 현재 게임 체크 상태를 재사용하면 안 된다.
- PR25 foundation_server.visual_context는 실제 board.is_check/checkers를 사용한다. 이 규칙 근거를 공통 응답 표시 메타데이터로 재사용하되 점수/도움/저장 상태에 포함하지 않는다.

## 구현 순서와 수용 기준

1. 현재 FEN에 대한 표시 메타데이터와 검증된 before/after/UCI 전환 계약을 정리한다. 합법성은 python-chess에서 검증하고 프런트엔드에서는 주어진 두 위치가 전환과 일치하는지 확인한다. 단순 위치 교체/강좌 변경/계정 변경은 가짜 착수로 애니메이션하지 않는다.
2. 보드별 취소 가능한 모션 수명주기를 만든다. 저장/시계/입력 승인은 애니메이션 완료를 기다리지 않는다. 캐슬링 양 기물, 잡기/앙파상 제거, 승격 교체, 역방향 복원 위치를 정확히 처리한다. 프리무브 중복 제출과 이동 후 stale callback을 차단한다.
3. 대국/학습/퍼즐/진단/오프닝/복기/데모 렌더러를 조사해 현재 위치만 표시한다. 체크는 빨간 표시+라벨이며 핀된 공격도 포함한다. 체크메이트/스테일메이트를 혼동하지 않는다. 독립 풀이 정답/위협 노출을 추가하지 않는다.
4. reduced-motion 즉시 표시, 화면 이탈/계정 변경/빠른 복기 탐색 cancellation, 흑 시점/키보드/승격 취소/시계/프리무브/느린 응답을 검사한다. 새 FEN에서 잔여 표시는0이다.

단계3 전체 레이아웃/피드백 확장은 포함하지 않는다. 첫 논리 단위 구현과 검사 후 작은 commit/push로 보존하고 해당 SHA·실행한 검사·미검증을 이 문서에 갱신한다. 새 전체 검사 전 이전 프로세스/로그를 확인해 중복 실행하지 않는다.
