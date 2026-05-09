# Swing Trading System 실행 계획

## Context
- 목표: `quant_trading_system`과는 독립적으로 운영되는 미국 주식 Swing trading 시스템을 `swing_trading_system/`에 신설한다.
- 핵심 제약:
  - 데이터 적재 중복은 피한다.
  - 기존 Quant 인프라인 `PostgreSQL`, `MinIO`는 최대한 공유한다.
  - 기존 Quant 서비스 포트와 충돌하지 않아야 한다.
- 참고 초안: `swing_trading_system/docs/swing_trading_system_draft.md`
- 현재 Quant 시스템에서 확인한 사실:
  - 런타임: `PostgreSQL + MinIO + Airflow + FastAPI/Jinja`
  - 현재 호스트 포트: `55432`(Postgres), `9000`/`9001`(MinIO/API console), `5050`(pgAdmin), `8080`(Airflow), `8000`(web)
  - 공용 원천 데이터는 이미 `raw.*`, `stg.*`, `mart.*`, `meta.*` 스키마로 정리되어 있음

## Approach
- 권장 방향은 **인프라는 공유하고 도메인 코드는 분리**하는 것이다.
- 즉, Swing 시스템은 별도 패키지/별도 compose/별도 UI/API/별도 배치로 구성하되, 아래 공용 데이터 계약을 사용한다.
  - Quant가 계속 소유하는 공용 데이터: `raw.market_daily_prices`, `raw.market_corporate_actions`, `raw.sec_*`, `raw.alpha_vantage_*`, `stg.stg_daily_prices`, `stg.stg_security_master`, `stg.stg_benchmark_series`
  - Swing가 새로 소유하는 전용 데이터: `swing_meta.*`, `swing_mart.*`, 필요 시 `swing_raw.*` 및 MinIO `swing-*` 버킷/프리픽스
- 현실적인 1차 구현에서는 **코드 공통화보다 데이터 계약 공유를 우선**한다.
  - 이유: Quant 코어 모듈을 먼저 공통 패키지로 추출하면 기존 시스템 회귀 위험이 커진다.
  - 따라서 초기에 Swing는 Quant의 구현 패턴을 참고하되 자체 코드베이스로 작성하고, 운영이 안정화되면 공통 모듈 추출을 2차 과제로 둔다.
- 전략 범위는 단계적으로 확장한다.
  1. EOD 기반 스크리닝/시그널/백테스트
  2. 포지션 관리와 알림
  3. Alpaca paper execution 연동
  4. 필요 시 실거래 자동화
- Swing 런타임은 Quant와 독립 배포하되, 로컬에서는 Quant의 Postgres/MinIO에 외부 접속하는 방식으로 구성한다.
  - 즉 `swing_trading_system/docker-compose.yml`은 원칙적으로 `postgres`, `minio` 컨테이너를 새로 띄우지 않는다.
  - 대신 환경변수로 기존 Quant 인프라(`POSTGRES_HOST/PORT`, `MINIO_ENDPOINT`)를 바라보게 한다.
- 포트는 84xx 대역을 Swing 전용으로 예약한다.
  - 권장: `8401`(swing web), `8402`(swing api or admin), `8403`(optional metrics/debug)

## Files to modify
- 문서/계획
  - `swing_trading_system/docs/swing_trading_system_plan.md`
  - `swing_trading_system/docs/swing_trading_system_draft.md` (최종 계획 반영 시 정리 가능)
- Swing 신규 생성 예상 경로
  - `swing_trading_system/pyproject.toml`
  - `swing_trading_system/.env.example`
  - `swing_trading_system/docker-compose.yml`
  - `swing_trading_system/src/swing_trading_system/config.py`
  - `swing_trading_system/src/swing_trading_system/storage.py`
  - `swing_trading_system/src/swing_trading_system/db.py`
  - `swing_trading_system/src/swing_trading_system/pipeline/`
  - `swing_trading_system/src/swing_trading_system/screening/`
  - `swing_trading_system/src/swing_trading_system/backtest/`
  - `swing_trading_system/src/swing_trading_system/execution/`
  - `swing_trading_system/src/swing_trading_system/web/`
  - `swing_trading_system/dbt/`
  - `swing_trading_system/dags/` 또는 `swing_trading_system/jobs/`
  - `swing_trading_system/tests/`
- Quant 쪽에서 변경 가능성이 있는 파일(가능하면 최소화)
  - `quant_trading_system/README.md` 또는 운영 문서류 — shared infrastructure 사용법 명시 시
  - `quant_trading_system/infra/postgres/init/*.sql` — Swing 전용 스키마/테이블을 같은 DB에 초기화해야 할 경우

## Reuse
- 인프라/설정 패턴
  - `quant_trading_system/docker-compose.yml` — 현재 공유 인프라와 사용 포트 기준점
  - `quant_trading_system/src/quant_data_platform/config.py` — env 기반 설정 구조
  - `quant_trading_system/src/quant_data_platform/storage.py` — `postgres_connection()`, `make_s3_client()` 패턴
  - `quant_trading_system/src/quant_data_platform/object_store.py` — `upload_json()`, `upload_bytes()` 패턴
- 원천/정규화 데이터
  - `quant_trading_system/infra/postgres/init/01_bootstrap.sql` — 현재 raw/meta 스키마와 테이블 구조
  - `quant_trading_system/dbt/models/sources.yml` — 공용 source 정의
  - `quant_trading_system/dbt/models/staging/stg_daily_prices.sql` — canonical price source 우선순위 규칙(Tiingo > yfinance)
  - `quant_trading_system/dbt/models/staging/stg_security_master.sql` — 종목 마스터 결합 규칙
  - `quant_trading_system/dbt/models/intermediate/int_point_in_time_fundamentals.sql` — PIT 재무 정합성 로직
  - `quant_trading_system/dbt/models/intermediate/int_prices_universe_daily.sql` — 가격/유니버스/PIT 재무 결합 패턴
  - `quant_trading_system/dbt/models/staging/stg_benchmark_series.sql` — SPY/FRED 벤치마크 재사용 가능
- 배치/파이프라인 패턴
  - `quant_trading_system/src/quant_data_platform/pipeline.py` — ingestion orchestration 패턴
  - `quant_trading_system/src/quant_data_platform/cli.py` — CLI 진입점 패턴
  - `quant_trading_system/dags/daily_incremental_pipeline.py` — 소스 수집 → dbt → test 파이프라인 순서
- 웹/API 패턴
  - `quant_trading_system/src/quant_data_platform/web/app.py` — FastAPI + Jinja 앱 구성
  - `quant_trading_system/src/quant_data_platform/web/routes/backtest.py` — form 처리/healthz 패턴
  - `quant_trading_system/src/quant_data_platform/web/repositories/backtest_repo.py` — readiness 검사, DB repository 패턴
  - `quant_trading_system/src/quant_data_platform/web/services/backtest_service.py` — page service 계층화 패턴
- 실행 연동 패턴
  - `quant_trading_system/src/quant_data_platform/clients/alpaca.py` — paper trading client 재사용 후보
  - `quant_trading_system/src/quant_data_platform/web/routes/alpaca.py`
  - `quant_trading_system/src/quant_data_platform/web/services/alpaca_service.py`

## Steps
- [x] **Phase 0 — 아키텍처 계약 확정**: `docs/architecture_contract.md`에 Swing/Quant 경계, shared relation, 포트/배포 계약을 문서화했다.
- [x] **Phase 1 — 프로젝트 부트스트랩**: `uv` 기반 프로젝트, `.env.example`, `docker-compose.yml`, `infra/web/Dockerfile`, 테스트 골격, 기본 FastAPI 앱을 생성했다.
- [x] **Phase 2 — 공유 데이터 접근 계층 구축**: `config.py`, `storage.py`, `repositories/shared_market.py`, `repositories/swing_repository.py`를 만들어 shared PostgreSQL/MinIO 접근 계층을 구성했다.
- [x] **Phase 3 — Swing 전용 스키마 설계**: `sql/01_swing_schema.sql`에 `swing_meta`, `swing_mart`, `swing_raw`와 핵심 테이블을 정의했다.
- [x] **Phase 4 — 스크리너 1차 구현**: `screening/`에 공용 `stg.*` 기반 유동성/추세/상대강도/ATR/거래량 확장 스크리너를 구현했다.
- [x] **Phase 5 — 전략 엔진 1차 구현**: `strategies/pullback.py`, `strategies/breakout.py`에 2개 전략을 구현했다.
  - 눌림목(pullback): 상승 추세 유지 + 최근 조정 + 지지/ATR 기준 손절
  - 돌파(breakout): 박스/고점 돌파 + 거래량 증가 + 손절/추적손절
- [x] **Phase 6 — 백테스트 엔진 구축**: `backtest/engine.py`에 event-driven 일봉 상태 머신 백테스터를 구현했다.
- [x] **Phase 7 — 웹 UI 1차 구현**: `web/`에 readiness, 후보, 백테스트, trade plan, position/alert 화면을 FastAPI/Jinja로 구현했다.
- [x] **Phase 8 — 모니터링/알림**: `monitoring/`과 `end-of-day` 파이프라인에 후보 digest/포지션 alert 및 Slack/Telegram/Email notifier를 추가했다.
- [x] **Phase 9 — Paper execution 연동**: `execution/`에 Alpaca paper execution adapter와 trade plan 제출 흐름을 추가했다.
- [x] **Phase 10 — 운영 안정화**: `dbt/`, `tests/`, `docs/operations_runbook.md`, CLI healthcheck/init-db/end-of-day 절차를 추가했다.

## Verification
- 인프라/포트
  - `quant_trading_system/docker-compose.yml` 기준 기존 포트(`55432`, `9000`, `9001`, `5050`, `8080`, `8000`)와 Swing 포트가 겹치지 않는지 확인
  - Swing compose가 Postgres/MinIO를 중복 기동하지 않고 외부 연결만 수행하는지 확인
- 데이터 계약
  - Swing가 읽는 공용 테이블/뷰(`raw.*`, `stg.*`)가 실제로 존재하고 최신화되는지 확인
  - Swing가 쓰는 스키마(`swing_meta`, `swing_mart`, `swing_raw`)가 Quant 테이블과 충돌하지 않는지 확인
  - MinIO 버킷/프리픽스가 `quant-*`와 분리되는지 확인
- 전략/백테스트
  - 신호 생성 시 미래 데이터가 사용되지 않는지 점검
  - 손절/익절/슬리피지/포지션 사이징이 일관되게 적용되는지 단위 테스트
  - 저장된 trade log와 equity curve가 재현 가능한지 검증
- UI/운영
  - `/healthz` 또는 동등 endpoint에서 DB readiness와 필수 relation 존재 여부를 확인
  - 후보 생성 → 백테스트 → 시그널 저장 → 알림 생성 흐름을 수동 E2E로 점검
  - Paper trading 연동 시 dry-run / mock / sandbox 시나리오를 별도 검증
