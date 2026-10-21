# PR27 배포 패키징 복구

기준 main83c484bfa0fe64045fdd74c973c702c59faf9825. 실패배포 dep-dbc9k168bjmc73dbo6a0는 update_failed, 2026-10-21T10:57:11.079246Z 종료. 같은 시각 확인한 직전 dep-dbc2u3m7bikc73fjc6e0(6295dd728b58666d35d13feeadecddd3ca236dc1)는 live.

Render app로그 2026-10-21T10:57:07.403915934Z: `ModuleNotFoundError: No module named 'board_facts'`. `learning_server.py`가 새 모듈을 import하지만 Dockerfile의 명시적 COPY목록에 누락됐다. .dockerignore는 이 파일을 제외하지 않는다. public의 새JS/CSS는 기존 COPY public으로 포함된다. 인프라 일시 오류나 비밀키 문제가 아니다.

수정: 기존 명시적 COPY목록에 board_facts.py 하나 추가. 저장/채점/인증/운영설정 변경 없음.

검증:
- 수정전 새 packaging test: learning_server.py→board_facts 누락을 정확히 실패로 검출(before.log).
- 수정후 `tests/test_image_runtime_package.py tests/test_board_facts.py`: **5 passed**,29.38초(after.log).
- 실제 Dockerfile COPY목록과 현재 .dockerignore 범위만 임시디렉터리에 복제. 모든 복제Python파일의 local import존재 확인, 실제 `python build_journey_index.py` 실행, 체크아웃을 PYTHONPATH에서 제외한 별도 프로세스로 `import server` 및 board_facts 경로를 검증. board_facts를 임시복제본에서만 제외한 음성대조는 실제 ModuleNotFoundError를 재현.
- COPY parser는 현재 사용 중인 명시적 로컬 source 형식만 지원하며 COPY옵션/JSON/glob/ignore negation을 임의로 처리하지 않고 검사 실패로 추가 구현을 요구한다. 일반 Dockerfile 해석기라고 주장하지 않는다.
- Python AST/구문 및 git diff --check 통과.

한계: DockerRootDir /var/lib/docker가 있는 루트 filesystem 여유0이므로 실제 Docker build/run과 PostgreSQL 검사는 이번에도 미실행. 이 검사는 COPY 산출물의 소스/런타임 일치 검사이며 Linux 이미지 레이어/apt/pip/Render rollout 검증의 대체가 아니다. 이전630개 소스회귀 통과가 이미지 패키징을 보장하지 못했던 검증 공백을 인정하며 구분한다. 추가 비용, 비밀키/환경변수 변경, DB삭제/초기화, 운영 계정 쓰기 없음. 부모가 PR 검토 후 병합·Render 배포를 확인한다.
