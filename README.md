# Swing Trading System

Foundation runtime for EOD swing-trading screening, strategy, backtest, alerts, and paper execution.

## Sprint 1 scope

This repository shares Quant PostgreSQL/MinIO infrastructure but keeps Swing code and write schemas separate.

Implemented foundation commands:

```bash
uv sync
uv run swing-system --help
uv run swing-system check-connection
uv run swing-system check-readiness
uv run swing-system init-db
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
