# 관계를 먼저 배우는 기초 레슨

기준 main: `0828d13585c26a91d8339aac2a888024c91c0a0c` (PR #51 이후 별도 변경).

## 교육 흐름과 범위

처음 시작하거나 명시적으로 다시 시작하는 관계 레슨은 **설명 → 안내 따라 하기 → 안내 없이 직접 확인**으로 진행한다. 자동 재생하지 않으며, 단계 이동·재생/멈춤·처음부터·건너뛰기·다시 보기를 제공한다. 첫 설명은 현재 배치의 공격자와 대상 이름, 방향 화살표, 경로 강조로 한 관계씩 보여준다. 공격은 파선, 따라 둘 수는 실선이다. 나이트는 중간 칸을 공격한다고 오해하지 않도록 꺾인 화살표와 뛰어넘는다는 문장을 쓴다.

17개 레슨: `rules-avoid-loss`, `rules-protect-piece`, `rules-shield-piece`, `rules-capture-safely`, `rules-give-check`, `rules-escape-king`, `rules-escape-block`, `rules-escape-capture`, `rules-escape-knight`, `rules-mate-queen`, `rules-mate-rook`, `rules-castle-attacked`, `rules-make-stalemate`, `rules-avoid-stalemate`, `rules-value-safety`, `rules-value-legal-first`, `rules-check-plan`.

독립 단계는 **같은 문제의 안내 제거**이지 처음 보는 문제로의 전이·숙련 인증이 아니다. 새 위치나 기존 점수 정의를 추가하지 않는다. 안내를 줄인 단계에서는 정답 화살표와 목적지 표시를 숨긴다.

## 규칙·기록 경계

- 공격칸은 python-chess의 `attacks/attackers`로 계산한다. 핀된 말의 공격칸과 합법 포획을 구분한다. 슬라이더는 첫 장애물에서 멈추고 폰 전진을 공격으로 취급하지 않는다.
- 보호 설명의 상대 포획과 되잡기는 각각 변경된 보드의 합법 수로 검증한다. 가상의 불법 킹 이동을 실제 수처럼 재생하지 않는다.
- 메이트/스테일메이트는 전체 합법 수 0개를 확인한다. 왕 이동 가능성은 이동·포획 뒤의 보드로 계산한다. 메이트는 체크, 왕 이동, 포획 대응, 가로막기 대응을 나누어 설명한다.
- `movement_v1` 안의 `teaching`에 설명/따라 하기 상태와 `guide_moves`를 저장한다. 이 이동들은 기존 `moves`, `done`, `result`, 완료 개수에 들어가지 않는다.
- 독립 단계의 완료는 기존 완료/판정 방식으로 계산한다. 추가 `practice_result`는 `independent_application_after_intro` 또는 `assisted_application`이다. 독립 단계에서 다시 시연을 본 경우 후자로 기록한다. 이미 완료한 결과는 나중의 시연 열람으로 다시 쓰지 않는다.
- 새 UI는 시작 요청에 `relationship_flow` 지원을 명시한다. 이전 UI의 요청은 기존 계약을 유지하며, 다른 탭에서 단계가 바뀌면 새로고침 안내를 반환한다.
- 기존 세션은 GET이나 이어하기로 마이그레이션·초기화하지 않는다. 기존 레슨에도 ‘기록 보존 · 설명부터 새로’ 진입점을 제공한다. 명시적 재시작은 기존 history 보존 규칙을 따른다. 진단·실력 점수·계정/게스트 연결 모델은 바꾸지 않는다.
- 모든 단계 변경은 계정, active session, revision을 검사한다. 늦은 응답은 계정/세션/화면의 상태를 덮어쓰지 않는다.

## 직접 확인한 공식 자료

- [Chess.com Lessons](https://support.chess.com/en/articles/8609703-how-do-lessons-work-on-chess-com): 설명과 상호작용 연습을 연결하는 구조를 참고했다.
- [Chess.com How to Play](https://www.chess.com/article/view/how-to-play-chess): 체크·체크 탈출·메이트를 짧은 시각 설명으로 도입하는 방식을 참고했다.
- [Lichess Learn](https://lichess.org/learn), [Practice](https://lichess.org/practice): 기초와 개념별 연습 구분을 확인했다. 웹 본문 도구로 Learn의 동적 상세 UI까지 검증했다고 주장하지 않는다.
- [FIDE 3.1.3](https://handbook.fide.com/chapter/e012023)의 공식 검색 발췌에서 핀된 말도 공격칸을 만든다는 원칙을 확인했다. 본문 열기는 타임아웃이었다. 해당 규칙은 별도 회귀 테스트로 검증한다.

문구·배치·보드·코드는 자체 작성했으며 외부 영상/이미지를 복제하지 않았다.

## 검증

`test_relationship_lessons.py`: 17개 레슨의 단계 분리, 기존 데이터 보존, 같은 문제 독립 결과와 도움 결과 구분, 공격/합법 수 차이, 핀·장애물·폰·왕 포획·메이트, 다른 계정과 revision 충돌.

`test_relationship_lessons_browser.py`: Chromium 320×650, 390×844, 844×390, 1366×768에서 실제 보드, 화살표, 클릭 가능성, 키보드 포커스, 저장 후 재진입, 재생/멈춤, 움직임 감소, 단계 건너뛰기, 재시작, 화면 이탈, 지연/유실 응답, 로그아웃을 검사한다. 기존 시연·기초 전체 레슨·계정/게스트 보존 회귀도 유지한다.

검증 결과와 최종 head CI는 PR에 기록한다. 화면은 Chromium 에뮬레이션이며 물리 Kakao/iOS 검증은 아니다. 이번 변경은 새 draft PR로 준비하며 운영 배포 완료를 주장하지 않는다.

로컬 결과(서로 겹치므로 합산하지 않음): 기존 시연·기초 전체 레슨·계정/게스트 회귀 66 passed. 새 단계/규칙/패키징 묶음은 92 passed 이후 로그인 완료 전에 화면을 옮긴 새 테스트의 fixture 경합 1건을 확인했고, 회원가입의 실제 홈 복귀를 기다리도록 보정했다. 별도 새 게스트 연결·키보드·4개 화면 크기 검사 5 passed. 최종 head 전체 CI 결과는 PR에서 구분해 기록한다. 기존 assertion을 삭제하거나 skip/xfail을 추가하지 않았다.

화면 증거: `explain-320.png`(공격선), `guided-320.png`(공격과 안내 구분), `independent-320.png`(안내 제거와 완료), `protection-recapture.png`(합법 되잡기), `mate-attack.png`(체크 관계). 실제 픽셀을 확인했으며, 모두 로컬 Chromium에서 렌더한 화면이다.

최종 경계 재검증: 회원가입의 홈 복귀 동기화 후, 지연 응답을 명시적으로 보류하고 로그아웃 뒤 해제하는 방식으로 계정 경계를 검사했다. 해당 검사와 기존 기록 보존 진입, 설명 취소 복구 3 passed (`/tmp/relationship-release-boundaries.log`). 전체 수집 1,319개; 최종 전체 CI는 로컬 부분 실행과 별개다.

방어 수 뒤에도 같은 편의 보호 대상을 기준으로 공격 관계를 다시 계산한다(체크 중에는 체크당한 쪽을 기준으로 한다). 예: d2–d4 후 g7 비숍의 화살표는 a1 룩이 아니라 d4 폰에서 끝난다. 이 전환을 고정하는 검사와 새 흐름·기존 시연·실제 UI 묶음 90 passed (`/tmp/relationship-recomputed.log`).
