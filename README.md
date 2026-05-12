# Swing Trading System

Foundation runtime for EOD swing-trading screening, strategy, backtest, alerts, and paper execution.

## Sprint scope

This repository shares Quant PostgreSQL/MinIO infrastructure but keeps Swing code and write schemas separate.

Implemented foundation commands:

```bash
uv sync
uv run swing-system --help
uv run swing-system check-connection
uv run swing-system check-readiness
uv run swing-system init-db
uv run swing-system backfill-bootstrap
uv run swing-system run-daily --max-universe 10 --dry-run
uv run swing-system run-daily --max-universe 10
uv run swing-system run-backtest --start-date 2026-05-01 --end-date 2026-05-01 --dry-run
uv run swing-system run-backtest --start-date 2026-05-01 --end-date 2026-05-01
uv run uvicorn swing_trading_system.web.app:app --host 0.0.0.0 --port 8401
```

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

`uv run swing-system run-daily` loads point-in-time EOD data, computes screening features, runs Pullback/Breakout v1, stores features in `swing_mart.swing_feature_store`, and stores strategy signals in `swing_meta.signal`.

Use `--dry-run` to compute without writing.

## Sprint 3 backtest and UI

`uv run swing-system run-backtest` reads `swing_meta.signal`, enters at `t+1` open, applies stop/target/max-hold exits, and stores results in `swing_mart.backtest_trade_log` and `swing_mart.backtest_equity_curve`.

Web UI v1 exposes `/`, `/signals`, `/backtests`, and `/backtests/{run_id}`.
