# PR #6 배포 전 실제 이미지·PostgreSQL 검증

대상 시작 head: `924794e81ecc3dc68189e21bbbfeb5940ea9693c`. 운영/main 기준은 `a70558bc291790b00ea6a5ca3ae17655f2337a24`. 이번 작업은 로컬 검증과 관련 수정만 수행한다. 운영 DB·계정·설정·서비스에는 접근하지 않고, main 병합·배포·외부 DB/유료 서비스 생성도 하지 않는다.

## 환경과 실제 빌드

Debian 13, Linux amd64, Docker Engine 28.4.0, Buildx 0.31.0. 호스트 PostgreSQL 도구 대신 공식 `postgres:17` 이미지의 **PostgreSQL 17.11**을 사용했다. 데이터는 별도 컨테이너의 tmpfs이며 호스트 연결은 `127.0.0.1:55432`에만 바인딩했다. 모든 계정/기록은 임시 가짜 데이터다. 테스트용 앱도 `127.0.0.1:18080`에만 노출했다.

실제 Dockerfile로 빌드했다. 원본 첫 시도는 Buildx 기본 캐시의 읽기 전용 경로로 실패했으며, 허용된 `/tmp/cma-buildx` 경로로 변경했다. 이어 pip HTTPS 인증서 검증이 이 환경 프록시의 CA 부재로 실패했다. TLS 검증을 해제하지 않고 **선택적 BuildKit CA secret 마운트**를 Dockerfile에 추가해 빌드에 성공했다. CA는 pip RUN 단계에서만 보이며 최종 이미지의 `/run/secrets/pip_ca_bundle`은 존재하지 않는다. 입력이 없으면 pip의 기본 신뢰 저장소를 사용한다. 일반 Render 환경에서 이 CA 입력이 필요하다고 가정하거나 운영 CA/설정을 변경하지 않았다.

- 최종 로컬 이미지 ID: `sha256:bd87a5ef228ea99f17443b6dbf131d2318170f111378961cbf48869bdc4b1434`
- 이미지 크기: 261,295,580 bytes, linux/amd64. 레지스트리에 push하지 않은 로컬 이미지다.
- Python base digest: `sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1`
- PostgreSQL image digest: `sha256:2d2b8998d31037bf721cfdf764d76ba74171b4fab3431b7f72c27c56ddbdf9e3`
- 이미지 Python 3.12.15 / FastAPI 0.149.0 / Uvicorn 0.54.0 / psycopg 3.3.6 / chess 1.11.2.
- 호스트 전체 회귀는 FastAPI 0.148.0, 나머지 같은 서버 라이브러리 및 pytest 9.1.1 / Playwright 1.64.0. 이미지의 실제 HTTP와 PostgreSQL 검사를 별도로 실행해 환경 차이를 구분한다.

최종 이미지의 소스·공개 파일 63개를 작업 코드와 SHA256으로 비교해 일치했다. `/app/journey-index.json.gz`는 40,713개 고유 적격 문항을 포함하며, 정책 `journey-index-v1`, 원본 SHA256 `241c7a902d7952b7a7501f383aaef4a4b7a189113b61c3b3c51e91d4881b7310`이 일치한다. 원본 40,721개 자체는 변경하지 않았다. 이미지 안에서 `build_inventory` 호출 시 실패하도록 만든 별도 읽기 검증으로 재생성 없이 인덱스를 로드함을 확인했고, 실제 이미지 시작 후 HTTP 진단도 성공했다. 원시 메타데이터는 [evidence.json](docs/qa-predeploy/evidence.json)에 보존한다.

## 확인된 수정

1. 빌드 환경의 검증 가능한 CA를 선택적으로 전달하는 secret 마운트. 인증서/토큰을 이미지에 저장하거나 TLS 검증을 끄지 않는다.
2. 컨테이너 시작 명령의 `exec uvicorn`. 실제 기존 재시작에서 정상 종료 로그 없이 Docker `die exitCode=137`을 확인했다. 수정 후 두 번의 재시작 모두 정상 종료 로그와 `exitCode=0`을 확인했고, 재시작 명령은 0.700초에 끝났다. 셸이 종료 신호를 가로막아 종료 유예 후 강제 종료되는 문제를 해결했다.
3. `.dockerignore`로 Git·환경 파일·로컬 DB·캐시·로그를 빌드 문맥에서 제외했다. 테스트 빌드의 소스는 별도 `git archive` 작업 디렉터리에서 가져왔다.

평가·학습 로직의 새 결함은 이번 검증에서 발견하지 않아 변경하지 않았다. PostgreSQL 첫 실행의 4개 실패는 테스트 코드가 계정 정규화 전 소문자 키로 SQL 조회·잠금을 수행한 fixture 오류였다. 생성 계정을 서버와 동일하게 대문자로 사용한 뒤 검증했다.

## 실제 PostgreSQL 검증 범위

`scripts/predeploy_postgres.py`는 명시적 `CMA_TEST_PG_URL`의 loopback + `cma_predeploy` DB만 허용하고 호출 환경의 운영 DATABASE_URL을 사용하지 않는다. 실제 `server.db`, 인증, 계정 등록, API, 원본 코퍼스와 PostgreSQL 잠금을 사용한다. 8개 검사는 다음을 포함한다.

- 두 계정의 동시 진단/로그인/새 대국, 동일 계정 두 탭의 시작·착수 경쟁(200/409), stale progress CAS, 진단/훈련 간 같은 후보 예약 경쟁(200/409).
- 연결 설정 5초/잠금 2초/SQL 8초를 실제 연결에서 확인한다. 로컬 TCP가 PostgreSQL handshake를 완료하지 않는 상황에서 약 5초 후 API 503, 실제 advisory lock 경합에서 약 2초 후 API 503/Retry-After, `pg_sleep(10)`에서 약 8초 후 503 예외/전체 트랜잭션 rollback을 확인한다. 잠금을 푼 뒤 조회/재시작은 성공하고 중복 시작은 409다.
- 구형 진단 보고서·진행 세션, 구형 첫 수 학습 기록과 레거시 수업/평가 이력을 심어 additive 초기화 및 재개 후 원본 JSON/기록 보존을 확인한다. 이전 학습 기록은 현재 전체 수순 집계에 합치지 않는다.
- PostgreSQL에서 복원한 안내형·단서 비공개·구형 결과의 난도 선택 범위를 분리한다.

같은 8개 검사를 호스트와 실제 최종 이미지의 일회성 테스트 컨테이너에서 실행한다. 이미지 테스트 컨테이너에만 pytest/httpx와 검증용 공개 CA를 임시 설치하며 최종 앱 이미지에는 추가하지 않는다. 중복 실행을 16개 고유 검사로 합산하지 않는다. 기존 225개 회귀와도 별도로 보고한다.

`scripts/predeploy_image_http.py`는 실제 Uvicorn 이미지로 TCP 요청을 보낸다. 프록시가 upstream 저장 응답을 받은 직후 클라이언트 연결을 끊는 실제 응답 유실을 만들고, 상태 조회로 같은 session_id를 복구하고 재전송은 409임을 확인했다. 컨테이너 프로세스 재시작 후 진단 session/revision과 연결 훈련의 hint/session/revision/path도 보존됐다. 이는 단순 TestClient 응답 무시가 아닌 실제 TCP/프로세스 검증이다.

## 성능·메모리

앱과 PostgreSQL 각각 1 CPU/512MiB 제한, 로컬 Docker 네트워크/loopback HTTP, 새 앱 프로세스, 서로 다른 임시 계정, 단일 표본이다. A의 첫 진단과 B의 세 요청을 동시에 시작한 뒤 C로 warm을 측정했다. Docker 기동/이미지 pull 시간은 endpoint 시간에 포함하지 않는다.

| 항목 | 관측 |
|---|---|
| cold 진단 | 0.3829초 |
| warm 진단 | 0.1040초 |
| 동시 `/me` / `/onboarding` / `/game/new` | 0.0329 / 0.0408 / 0.0445초 |
| Uvicorn RSS 시작 전 / 후 | 149,100 / 250,064 KiB |
| Uvicorn peak RSS (`VmHWM`) | 250,840 KiB |
| 실제 앱 재시작 명령 | 0.6998초, 정상 종료 |

프로세스 RSS 수치이며 컨테이너 전체 메모리·PostgreSQL 메모리·장기 누수/P95를 의미하지 않는다. 단일 로컬 결과를 Render의 cold start, 운영 DB 지연, 동시 사용자 용량 보장으로 해석하지 않는다.

## 재현 명령과 최종 검증 기록

빌드 문맥에는 해당 커밋의 추적 파일만 export하고 수정 Dockerfile/.dockerignore를 포함했다. 다음 명령의 CA 경로는 이 코딩 환경에서 검증된 공개 신뢰 묶음이다.

```sh
BUILDX_CONFIG=/tmp/cma-buildx docker build \
  --secret id=pip_ca_bundle,src=/etc/ssl/certs/ca-certificates.crt \
  -t cma-predeploy:verified /tmp/chess-predeploy-context
docker network create cma-predeploy-net
docker run -d --name cma-predeploy-pg --network cma-predeploy-net \
  --memory=512m --cpus=1 --tmpfs /var/lib/postgresql/data:rw \
  -p 127.0.0.1:55432:5432 -e POSTGRES_PASSWORD=local-ephemeral-only \
  -e POSTGRES_DB=cma_predeploy postgres:17
docker run -d --name cma-predeploy-app --network cma-predeploy-net \
  --memory=512m --cpus=1 -p 127.0.0.1:18080:10000 \
  -e DATABASE_URL=postgresql://postgres:local-ephemeral-only@cma-predeploy-pg:5432/cma_predeploy \
  cma-predeploy:verified
CMA_TEST_PG_URL=postgresql://postgres:local-ephemeral-only@127.0.0.1:55432/cma_predeploy \
  CMA_JOURNEY_INDEX=/tmp/chess-journey-index.json.gz \
  python -m pytest -q -rP scripts/predeploy_postgres.py
python scripts/predeploy_image_http.py
DATABASE_URL='' STOCKFISH_PATH=/tmp/chess-stockfish/usr/games/stockfish \
  CMA_JOURNEY_INDEX=/tmp/chess-journey-index.json.gz python -m pytest -q tests
```

실제 계정 비밀번호가 아닌 삭제할 로컬 컨테이너 전용 가짜 값이다. 검증 후 이번 작업에서 만든 앱/테스트/PG 컨테이너와 전용 네트워크를 제거한다. 운영 데이터 삭제나 전역 Docker prune을 하지 않는다. 최종 커밋의 전체 회귀 수·시간, PostgreSQL 결과, 구문/정적 검사와 정확한 head는 PR 검증란/완료 보고에 기록한다. 이전 225개 통과 기록을 이번 결과에 더하지 않는다.

운영 배포 전 남은 범위는 부모의 변경 검토·병합 판단, 실제 Render 빌드/기동과 배포 후 브라우저 점검이다. 운영 PostgreSQL 버전/네트워크/권한/연결 수, 운영 데이터 규모와 플랫폼 cold start는 이 일회성 PG 17 검증으로 보장하지 않는다. 이 작업에서는 병합·배포하지 않는다.
