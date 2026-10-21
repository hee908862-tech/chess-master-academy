# PR29 最終 전체 검증 중

브랜치 fix/game-restore-feedback / draft PR29.
최종 코드/테스트 SHA: 0459e5d7dfcedc40e76c1cd8920cab9673b99743.
- 계정 전환 중 A 착수/새 대국 대기 소유권 해제, B 복원과 늦은 A 응답 보호.
- 복기 원본 위치 안내/탭 복귀 동기화. 계정 owner 변경 시 이전 읽기 캐시 무효화.
- 늦은 분석 성공/실패/정리는 계정·목록 revision으로 보호.
집중 로그와 정확한 실행 명령은 logs/COMMANDS.md (7/12/14 통과의 각 범위 구분).

현재 실행: /tmp/cma-pr29-owner-final.py, exec session 94692.
/tmp/cma-pr29-owner-final/manifest.json, collection.log, suite-*.log/xml.
77개 파일 / 642개 수집. 같은 최종 소스 고정, 4개 중복 없는 묶음 실행 중.
종료 후 `/tmp/pr29-owner-audit.py`로 전체 JUnit과 수집 식별자를 대조하고 로그/PR 본문 갱신.
중복 실행 전에 반드시 process/manifest/log 확인.

이전 후보 /tmp/cma-pr29-verified: 640 통과(140+184+180+136), 소유권 보완 전 시작한 실행이므로 최신 전체 통과로 재사용하지 않음.
더 이전 /tmp/cma-pr29-full: 636 통과/1 실패(구형 refresh 단독 대역 ReferenceError).
/tmp/cma-pr29-final: 첫 2묶음 통과 후 후속 수정으로 나머지 2묶음 SIGINT 종료. 모든 로그 보존.

일반 Chromium, 임시 SQLite. 루트 여유 0으로 실제 Docker/PG 미실행; Docker COPY payload/import 검사 포함.
부모가 검토/병합/배포/운영 QA. 운영 QA e4/c6 및 계정/기보 변경 금지.
검사가 생성한 기존 QA PNG는 미스테이징 보존. 소스 전체는 push 완료.
