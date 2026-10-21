# 재개 체크포인트 · 기초 보드 피드백 PR1

- 작업트리: /tmp/cma-foundation-feedback (같은 환경). 브랜치 feat/foundation-board-feedback.
- PR: https://github.com/hee908862-tech/chess-master-academy/pull/25 (draft). 직접 병합/배포 금지.
- 기준 main: 8dbee0b80a03b7003d775312fcc5d8918b5e881e.
- 최종 코드: d748a63454d25e432e2616494568ae533f239f18. 전체 검사 head: 3c8215f68748d4634073409dbd57cb0c9d5e4583. 이후 문서/로그/캡처만 추가.
- 완료: 기초 안내/완료 경로/L자, 체크·보호·위협, 판정/저장 구분, 공통 승격 선택, 앙파상 전후 교육 예시, 완료 후 보드 위치 유지, 계정/지연/취소 가드.
- 전체587통과0실패, 집중 브라우저16통과, JS28구문/Python2컴파일/diff check 통과. REPORT.md와 full-suites.json 및 로그 참조. 최종 검사 종료, 계속 실행할 테스트 없음.
- 미실행: 루트0/Docker root=/var/lib/docker로 Docker·PostgreSQL. 실제 모바일/스크린리더/운영 QA/교육 효과 미검증. 같은 /tmp 여유 약7.7GiB. 데이터·DB볼륨·기존 자료 삭제하지 않음.
- 다음: 부모의 PR25 독립 검토/운영 QA. 후속 단계는 공통 기물 모션·전체 보드 체크/레이아웃이며 이번에 완료하지 않음. 임의 다음 단계 착수 전 부모와 조율.
- 재접속 확인: git status --short; git rev-parse HEAD; git ls-remote origin refs/heads/feat/foundation-board-feedback. 소스 미커밋 변경은 없어야 한다. 기존 테스트가 생성한 다른 docs PNG/캐시는 로컬에 보존돼 있을 수 있다.
- 중간 실패/중단은 REPORT.md에 분리. /tmp/cma-foundation-final-* 및 -v2-*는 중단 결과, 최종은 -v3-*이다. 연결 오류가 있어도 실행됐을 수 있으므로 프로세스/로그 확인 후 재실행. 사용량/미저장 작업 복구를 보장하지 않음.

PR25 독립 검토 후속: 시범 중 판정은 읽기 전용 교육 안내, 저장 문구는 실제 실습 상태라는 접두사와 시범 비저장 안내로 구분한다. 복귀하면 저장해 둔 원래 판정/저장 문구를 정확히 복원한다. 시범 진입에서 selected를 비우고 렌더에서도 선택/합법목적지를 억제한다. e5 선택→전/후 시범→복귀, 최초/합법 대안 판정 각각 복원, 잔여 표시0/서버쓰기0을 포함한 집중 브라우저17개 통과(demo-followup.log), JS구문/diff check 통과. 이전 전체587은 3c8215f 기준이며 이 작은 후속에는 전체를 반복하지 않았다.

후속 시각 검수에서 오른쪽 해설의 선택 안내도 시범 문구로 전환하고 복귀 시 실제 저장 실습 해설로 복원했다. 최종 후속17통과(45.55초), ep 전/후 캡처와 manifest 갱신. 전체587 결과와 별도인 표시 영향 검사다.
