# Sprint 1 실행 계획 — Foundation & Data Layer

작성일: 2026-05-10

## 1. Sprint 목표

Sprint 1의 목표는 **Swing이 Quant shared infra에 안전하게 연결되고, Swing 전용 runtime/DB/schema 골격이 실행 가능한 상태로 올라오는 것**이다.

즉, Sprint 2에서 스크리닝/전략을 구현할 수 있도록 아래 기반을 완성한다.

1. 프로젝트 부트스트랩
2. 공유 데이터 접근 계층
3. Swing 전용 schema/migration/init
4. `/healthz` 및 CLI skeleton
5. 최소 smoke test

## 2. Sprint 입력 전제

- `swing_trading_system/docs/architecture_contract.md`
- `swing_trading_system/docs/shared_data_contract.md`
- `swing_trading_system/docs/infra_runtime_contract.md`
- `swing_trading_system/docs/plan/sprint_1_readiness_checklist.md`
- `swing_trading_system/docs/plan/sprint_0_review.md`

위 문서 기준으로 Sprint 1은 **Ready** 상태다.

## 3. Sprint 범위

### 포함
- package/bootstrap 구성
- env/config/storage/db 연결 계층
- Quant shared relation read-only access
- Swing repo 및 domain persistence skeleton
- Swing schema init 또는 migration
- web health endpoint
- CLI command skeleton
- smoke test / connectivity test

### 제외
- screening 알고리즘 본 구현
- pullback/breakout 전략 본 구현
- 백테스트 엔진 본 구현
- alert/execution 본 구현
- UI 기능 확장

## 4. Sprint 완료 기준(DoD)

아래가 모두 만족되면 Sprint 1 종료로 본다.

- `uv run swing-system --help` 실행 가능
- `/healthz` 응답 가능
- Quant shared DB read 연결 가능
- MinIO 연결 가능
- `swing_meta`, `swing_mart` schema init 가능
- shared relation readiness check 가능
- smoke test 통과
- Sprint 2 작업자가 사용할 수 있는 repository/interface가 준비됨

## 5. 작업 스트림

---

## S1-01. 프로젝트 부트스트랩

### 목적
Swing 런타임의 최소 실행 뼈대를 만든다.

### 작업
- `pyproject.toml` 정리 또는 초기화
- package structure 확정
- `.env.example` 정리
- entrypoint skeleton 생성
- FastAPI app skeleton 생성
- CLI skeleton 생성
- test directory skeleton 생성

### 산출물
- 실행 가능한 프로젝트 골격
- `swing-system` CLI 골격
- web app skeleton

### Acceptance Criteria
- 프로젝트가 import 에러 없이 시작 가능
- CLI help 출력 가능
- app 모듈이 health endpoint를 노출할 준비가 됨

### 필요한 subagents
- `senior-backend-engineer-python`
- `project-manager`
- `qa-engineer`

---

## S1-02. Config / Storage / DB 연결 계층 구현

### 목적
INFRA_HOST 중심 runtime contract를 실제 설정 로직에 반영한다.

### 작업
- config loader 정리
- `INFRA_HOST` 기반 host resolution
- PostgreSQL/MinIO client setup
- connection test utility
- env validation

### 산출물
- `config.py`
- `storage.py`
- `db.py`

### Acceptance Criteria
- `INFRA_HOST`만으로 기본 연결 대상이 결정됨
- PostgreSQL/MinIO 연결 실패 시 명확한 에러 메시지 제공
- local/remote 운영 예시와 일치

### 필요한 subagents
- `senior-backend-engineer-python`
- `scout`
- `paranoid-staff-engineer-reviewer`

---

## S1-03. Shared market repository 구현

### 목적
Quant shared relation을 읽는 최소 repository 계층을 만든다.

### 대상 relation
- `stg.stg_daily_prices`
- `stg.stg_security_master`
- `stg.stg_benchmark_series`
- optional: `stg.stg_listing_status_history`

### 작업
- read-only query functions
- symbol/date range fetch
- readiness/freshness check
- support symbol validation

### 산출물
- `repositories/shared_market.py`
- shared relation access interface

### Acceptance Criteria
- read-only contract 준수
- 핵심 shared relation 조회 가능
- readiness check가 성공/실패를 구분해 반환

### 필요한 subagents
- `scout`
- `senior-backend-engineer-python`
- `qa-engineer`

---

## S1-04. Swing repository skeleton 구현

### 목적
Swing 전용 schema에 저장될 domain object의 persistence 골격을 만든다.

### 대상
- strategy config
- screening run
- signal
- trade plan
- position snapshot
- alert
- execution order

### 작업
- repository interface 정의
- domain-to-table mapping skeleton
- insert/get/list 패턴 정의
- 아직 business logic은 최소화

### 산출물
- `repositories/swing_repository.py`
- domain persistence interface

### Acceptance Criteria
- Swing write namespace만 사용
- Quant schema write 없음
- Sprint 2/3에서 확장 가능한 형태

### 필요한 subagents
- `senior-backend-engineer-python`
- `quant-trading-expert`
- `paranoid-staff-engineer-reviewer`

---

## S1-05. Swing schema init / migration 추가

### 목적
Sprint 0에서 확정한 schema/table 계약을 실제 init 또는 migration으로 연결한다.

### 작업
- `swing_meta` schema 생성
- `swing_mart` schema 생성
- 필요 시 `swing_raw` schema 생성
- 최소 테이블 init 초안 작성
- 권한/소유자 정책 반영

### 산출물
- init SQL 또는 migration
- schema bootstrap 절차

### Acceptance Criteria
- Quant schema와 충돌 없음
- 재실행 가능한 idempotent 형태
- DB 권한 범위 내에서 실행 가능

### 필요한 subagents
- `senior-backend-engineer-python`
- `paranoid-staff-engineer-reviewer`
- `qa-engineer`

---

## S1-06. Web health endpoint 구현

### 목적
운영/개발에서 Swing 런타임 생존 여부를 빠르게 확인할 수 있게 한다.

### 작업
- `/healthz` endpoint 구현
- DB connectivity check 포함
- shared relation readiness check 포함
- fail reason 반환 형식 정의

### 산출물
- health endpoint
- health check response schema

### Acceptance Criteria
- HTTP 200/5xx 판정 가능
- 의존성 실패 원인을 읽을 수 있음
- Sprint 1 smoke test로 검증 가능

### 필요한 subagents
- `senior-backend-engineer-python`
- `qa-engineer`

---

## S1-07. CLI skeleton 구현

### 목적
운영자가 최소한의 명령으로 init/check를 수행하게 한다.

### 작업
- `swing-system --help`
- `init-db`
- `check-connection`
- `check-readiness`
- 명령별 exit code 정의

### 산출물
- CLI entrypoint
- command docs 초안

### Acceptance Criteria
- help/command tree 확인 가능
- exit code가 자동화에 적합함
- health/readiness 검사와 연동됨

### 필요한 subagents
- `senior-backend-engineer-python`
- `project-manager`
- `qa-engineer`

---

## S1-08. Smoke test 및 connectivity test 작성

### 목적
Sprint 1 산출물이 실제로 작동하는지 검증한다.

### 작업
- config test
- DB connection test
- MinIO connection test
- shared relation read test
- health endpoint test
- CLI smoke test

### 산출물
- `tests/` 하위 smoke/connectivity test

### Acceptance Criteria
- 주요 연결 실패가 테스트로 드러남
- shared read contract 위반이 감지됨
- CI 또는 로컬에서 재현 가능

### 필요한 subagents
- `qa-engineer`
- `paranoid-staff-engineer-reviewer`
- `senior-backend-engineer-python`

---

## S1-09. 문서/운영 가이드 보강

### 목적
Sprint 2 착수 전에 개발자/운영자가 참고할 최소 문서를 정리한다.

### 작업
- 실행 순서 정리
- init/check/readiness 절차 정리
- 실패 시 확인 포인트 정리
- 환경변수 사용법 정리

### 산출물
- Sprint 1 구현 노트
- 운영 메모 초안

### Acceptance Criteria
- 문서만 보고 local bootstrap 가능
- shared infra 접근/검증 절차가 명확함

### 필요한 subagents
- `project-manager`
- `qa-engineer`

## 6. 권장 실행 순서

### Day 1
1. S1-01 프로젝트 부트스트랩
2. S1-02 Config / Storage / DB

### Day 2
3. S1-03 Shared market repository
4. S1-04 Swing repository skeleton

### Day 3
5. S1-05 Schema init / migration
6. S1-06 `/healthz`

### Day 4
7. S1-07 CLI skeleton
8. S1-08 Smoke test

### Day 5
9. S1-09 문서/운영 가이드 보강
10. Sprint review / blocker cleanup

## 7. Sprint 1 종료 조건

Sprint 1은 아래 조건이 충족되면 종료한다.

- [x] 프로젝트 골격이 실행 가능함
- [x] shared infra 연결 가능함
- [x] shared relation read 가능함
- [x] Swing schema init 가능함
- [x] health/CLI skeleton 제공됨
- [x] smoke test 통과
- [x] Sprint 2 작업 항목으로 분해 가능한 수준의 코드/문서가 준비됨

## 8. Sprint 2 진입 조건

1. shared relation access가 안정적이다.
2. Swing schema init 및 persistence 구조가 준비되었다.
3. health/readiness check가 동작한다.
4. Sprint 2의 screening/strategy workstream이 repository 위에서 시작 가능하다.
