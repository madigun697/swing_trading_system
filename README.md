# Swing Trading System

Foundation runtime for EOD swing-trading screening, strategy, backtest, alerts, and paper execution.

## Sprint scope

This repository shares Quant PostgreSQL/MinIO infrastructure but keeps Swing code and write schemas separate.

Implemented foundation commands:

- `uv sync` — installs project dependencies and prepares the local env.
- `uv run swing-system --help` — shows available CLI commands and options.
- `uv run swing-system check-connection` — checks PostgreSQL and MinIO connectivity.
- `uv run swing-system check-readiness` — verifies required Quant shared relations are readable.
- `uv run swing-system init-db` — creates Swing-owned schemas and tables.
- `uv run swing-system backfill-bootstrap` — seeds Sprint 2 bootstrap configs and feature rows.
- `uv run swing-system run-daily --max-universe 10 --dry-run` — runs screening/strategy without writing.
- `uv run swing-system run-daily --max-universe 10` — runs screening/strategy and writes feature/signal rows.
- `uv run swing-system backfill-signals --start-date 2025-01-01 --end-date 2026-05-01 --frequency weekly --max-universe 10` — generates historical screening/strategy signals over a date range.
- `uv run swing-system run-backtest --start-date 2026-05-01 --end-date 2026-05-01 --dry-run` — simulates backtest without saving results.
- `uv run swing-system run-backtest --start-date 2026-05-01 --end-date 2026-05-01` — runs backtest and persists trade/equity results.
- `uv run uvicorn swing_trading_system.web.app:app --host 0.0.0.0 --port 8401` — starts the Web UI/API server.

Health endpoint:

```bash
curl http://localhost:8401/healthz
```

## Runtime contract

- `INFRA_HOST` is the canonical shared host override.
- `POSTGRES_HOST` defaults to `INFRA_HOST` unless explicitly set.
- `MINIO_ENDPOINT` defaults to `http://${INFRA_HOST}:9000` unless explicitly set.
- Swing compose starts only Swing services; PostgreSQL and MinIO are provided by shared Quant infra.

## Swing-owned schemas

`uv run swing-system init-db` creates idempotent Swing-owned schemas/tables:

- `swing_meta.*`
- `swing_mart.*`
- `swing_raw.*`

Swing must not write to Quant-owned `raw.*`, `stg.*`, `meta.*`, or `mart.*`.

## Sprint 2 daily screening

`uv run swing-system run-daily`는 기준일(as-of date) 기준으로 스크리닝과 전략 생성을 한 번에 수행한다.

### 주요 command
- `uv run swing-system run-daily --dry-run` — 실제 DB에 쓰지 않고 후보/시그널만 계산해 확인할 때 사용한다.
- `uv run swing-system run-daily --max-universe 10 --dry-run` — 유니버스를 좁혀서 로직과 결과를 빠르게 점검할 때 사용한다.
- `uv run swing-system run-daily --max-universe 10` — 계산 결과를 `swing_mart.swing_feature_store`와 `swing_meta.signal`에 저장한다.

### 수행 내용
- 기준일 이전의 point-in-time EOD 데이터를 읽는다.
- 유동성/추세/상대강도/ATR/거래량 feature를 계산한다.
- Screener v1로 후보를 추린다.
- Pullback/Breakout v1 전략으로 signal을 생성한다.
- 결과를 Swing-owned schema에 저장한다.

### 출력 결과
- feature rows 수
- candidate 수
- signal 수
- 저장 여부(dry-run / write)

### Historical signal backfill
- `uv run swing-system backfill-signals --start-date 2025-01-01 --end-date 2026-05-01 --frequency weekly --max-universe 10`
- `--frequency`는 `daily`, `weekly`, `monthly`를 지원한다.
- 기본적으로 이미 signal 또는 feature row가 있는 날짜는 중복 생성을 피하기 위해 skip하며, 재생성이 필요하면 `--force`를 사용한다.
- 백테스트는 저장된 `swing_meta.signal.signal_date`를 기준으로 기간을 필터링하므로, 과거 기간 백테스트 전에는 해당 기간의 signal backfill이 필요하다.

## Sprint 3 backtest and UI

`uv run swing-system run-backtest`는 Sprint 2에서 생성된 signal을 입력으로 사용해 일봉 백테스트를 수행한다.

### 주요 command
- `uv run swing-system run-backtest --dry-run` — 저장 없이 signal/price 연결과 백테스트 결과를 먼저 검증한다.
- `uv run swing-system run-backtest --start-date 2026-05-01 --end-date 2026-05-01 --dry-run` — 특정 signal date 구간만 대상으로 백테스트 논리를 확인할 때 사용한다.
- `uv run swing-system run-backtest --start-date 2026-05-01 --end-date 2026-05-01` — trade log와 equity curve를 실제로 저장한다.

### 수행 내용
- `swing_meta.signal`을 읽고 `--start-date/--end-date`를 `signal_date`에 적용한다.
- 실제 trade date는 `t+1` 진입과 이후 exit 때문에 지정한 signal date 범위보다 뒤로 확장될 수 있다.
- `stg.stg_daily_prices`에서 signal 이후 가격을 조회한다.
- `t+1` 시가 진입, stop/target/max-hold exit을 적용한다.
- 결과를 `swing_mart.backtest_trade_log`와 `swing_mart.backtest_equity_curve`에 저장한다.
- total return, MDD, win rate, profit factor 등의 metric을 계산한다.

### Web UI v1
- `/` — 데이터 상태와 최신 백테스트 개요
- `/signals` — 최근 signal 목록
- `/backtests` — 최근 backtest run 목록
- `/backtests/{run_id}` — 특정 run의 trade log/equity curve 상세
