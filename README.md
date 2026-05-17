# Swing Trading System

An end-of-day swing-trading research and review system built on top of the shared Quant Data Platform infrastructure.

The project screens a point-in-time equity universe, generates swing-trading signals, runs event-driven backtests, stores Swing-owned results, and provides a FastAPI web UI for reviewing signals and backtest detail.

> Research and educational use only. This repository does not provide investment advice or a production trading guarantee.

Korean documentation: [README.ko.md](README.ko.md)

## What It Does

- Connects to shared PostgreSQL and MinIO infrastructure created by the Quant Data Platform
- Checks readiness of required shared Quant relations before Swing workflows run
- Initializes Swing-owned schemas and tables
- Builds daily screening context in `screening_v2_context`
- Generates signals for three strategies:
  - `pullback`
  - `breakout`
  - `quality_momentum`
- Backfills historical signals over daily, weekly, or monthly date selections
- Runs event-driven backtests with T+1 open entry, stop/target/max-hold exits, target scale-out, trailing stops, and SPY benchmark comparison
- Provides a browser UI for dashboard, signal review, backtest runs, and backtest detail pages

## Architecture

```text
Shared Quant Platform
  PostgreSQL marts + MinIO
        |
        v
Swing repositories and readiness checks
        |
        v
Universe selection, feature generation, screeners
        |
        v
Pullback / breakout / quality momentum strategies
        |
        v
Swing-owned schemas, event backtests, FastAPI web UI
```

Core runtime components:

- Python package: `swing_trading_system`
- CLI entry point: `swing-system`
- Screening pipeline: `swing_trading_system.screening`
- Strategy implementations: `swing_trading_system.strategies`
- Backtest engine: `swing_trading_system.backtest`
- Web app: `swing_trading_system.web.app`

## Requirements

- Python 3.13 or newer
- `uv`
- Access to the shared Quant PostgreSQL and MinIO infrastructure
- Quant marts populated enough for Swing readiness checks

Copy the sample environment file and fill in local values:

```bash
cp .env.example .env
```

Important environment behavior:

- `INFRA_HOST` is the canonical shared infrastructure host override.
- `POSTGRES_HOST` defaults to `INFRA_HOST` unless explicitly set.
- `MINIO_ENDPOINT` defaults to `http://${INFRA_HOST}:9000` unless explicitly set.
- Runtime defaults such as account equity, slippage, fees, position limits, and Swing ports live in `.env.example` and `src/swing_trading_system/config.py`.

Do not commit `.env` files or real credentials.

## Quick Start

Install dependencies and verify shared infrastructure:

```bash
uv sync
uv run swing-system check-connection
uv run swing-system check-readiness
uv run swing-system init-db
```

Start the Web UI:

```bash
uv run uvicorn swing_trading_system.web.app:app --host 0.0.0.0 --port 8401
```

Run the Web UI in the background:

```bash
chmod +x infra/web/serverctl.sh
infra/web/serverctl.sh start
infra/web/serverctl.sh status
infra/web/serverctl.sh logs
infra/web/serverctl.sh stop
```

The helper stores the PID and logs under `.run/`.

Health check:

```bash
curl http://localhost:8401/healthz
```

## Main CLI Commands

```bash
uv run swing-system --help
uv run swing-system check-connection
uv run swing-system check-readiness
uv run swing-system init-db
uv run swing-system backfill-bootstrap
uv run swing-system run-daily --max-universe 10 --dry-run
uv run swing-system run-daily --max-universe 10
uv run swing-system backfill-signals --start-date 2025-01-01 --end-date 2026-05-01 --frequency weekly --max-universe 10
uv run swing-system run-backtest --start-date 2025-01-02 --end-date 2026-05-01 --dry-run
uv run swing-system run-backtest --start-date 2025-01-02 --end-date 2026-05-01
```

## Screening And Strategies

`run-daily` reads point-in-time end-of-day data and writes features and signals into Swing-owned schemas.

`screening_v2_context` includes:

- Price and volatility features
- Sector, industry, and market-cap context
- SPY 20-day return and MA50/MA200 market-regime context
- Point-in-time fundamentals
- Recent SEC filing metadata

The screener focuses on liquid, constructive setups:

- `relative_strength_60d >= 0`
- `return_60d >= 0`
- `atr_pct <= 0.08`
- New signals are rejected when SPY is below MA200

Strategy notes:

- `pullback`: favors higher-quality and stronger relative-strength names with larger target multiples
- `breakout`: filters weak-volume breakouts more aggressively and rewards stronger quality/relative-strength names
- `quality_momentum`: continuation setup using quality and momentum confirmation

Market-regime sizing:

- R1-R5 market regimes are classified from SPY MA50/MA200 trend plus FRED `VIXCLS`
- The default aggressive profile keeps R1/R2 offensive, reduces R3 exposure, and blocks new R4/R5 entries
- Load VIX data from the Quant repo with `uv run python -m quant_data_platform.cli sync-fred --series VIXCLS`

## Backtest Model

`run-backtest` reads saved signals from `swing_meta.signal`, runs the event-driven engine, and stores:

- `swing_mart.backtest_trade_log`
- `swing_mart.backtest_equity_curve`
- `swing_mart.backtest_run_summary`

The backtest supports:

- T+1 open entry
- Stop, target, and max-hold exits
- Target scale-out
- Trailing moving-average stop
- Position count and gross exposure limits
- Fee and slippage assumptions
- SPY benchmark comparison

## Web UI

Routes:

- `/`: dashboard
- `/signals`: recent signals
- `/backtests`: recent backtest runs
- `/backtests/run`: run and save a backtest from the browser, including combined strategy selections such as `breakout+pullback`
- `/backtests/{run_id}`: detail page with strategy vs SPY chart, contribution views, slice metrics, trade log, and daily equity table

End-user workflow and screen guide: [docs/user_manual.md](docs/user_manual.md)

## Data Ownership

Swing writes only to:

- `swing_meta.*`
- `swing_mart.*`
- `swing_raw.*`

Swing must not write to Quant-owned schemas:

- `raw.*`
- `stg.*`
- `meta.*`
- `mart.*`

See [docs/architecture_contract.md](docs/architecture_contract.md), [docs/shared_data_contract.md](docs/shared_data_contract.md), and [docs/infra_runtime_contract.md](docs/infra_runtime_contract.md) for the shared boundary.

## Testing

Run the test suite:

```bash
uv run pytest
```

Run linting:

```bash
uv run ruff check
```

## Related Documentation

- [User Manual](docs/user_manual.md)
- [Architecture Contract](docs/architecture_contract.md)
- [Shared Data Contract](docs/shared_data_contract.md)
- [Infrastructure Runtime Contract](docs/infra_runtime_contract.md)
- [Swing Trading System Plan](docs/swing_trading_system_plan.md)
- [Market Regime Switching Strategy Plan](docs/market_regime_switching_strategy_plan.md)

## Public Repository Notes

- `.env`, local data volumes, caches, and generated result folders are ignored.
- Keep API keys, broker credentials, personal account identifiers, and local database dumps out of commits.
- Backtest output is research evidence, not a forward-looking performance guarantee.
