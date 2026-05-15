# Swing Trading System

EOD swing-trading runtime for screening, signal generation, backtesting, Web UI review, and Swing-owned persistence on top of shared Quant infrastructure.

## What Is Implemented

- Shared infra connectivity and readiness checks
- Swing-owned schema bootstrap
- Daily screening pipeline with `screening_v2_context`
- Three signal strategies:
  - `pullback`
  - `breakout`
  - `quality_momentum`
- Signal backfill over historical dates
- Event-driven daily backtest with:
  - `t+1` open entry
  - stop / target / max-hold exit
  - target scale-out + trailing stop
  - SPY benchmark comparison
- Web UI for dashboard, signals, backtests, and backtest detail review

## Quick Start

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

Health check:

```bash
curl http://localhost:8401/healthz
```

## Main Commands

```bash
uv run swing-system --help
uv run swing-system backfill-bootstrap
uv run swing-system run-daily --max-universe 10 --dry-run
uv run swing-system run-daily --max-universe 10
uv run swing-system backfill-signals --start-date 2025-01-01 --end-date 2026-05-01 --frequency weekly --max-universe 10
uv run swing-system run-backtest --start-date 2025-01-02 --end-date 2026-05-01 --dry-run
uv run swing-system run-backtest --start-date 2025-01-02 --end-date 2026-05-01
```

## Screening And Strategies

`run-daily` reads point-in-time EOD data and writes features/signals into Swing-owned schemas.

- `screening_v2_context` stores price features plus:
  - sector / industry / market cap
  - SPY 20d return and MA50 / MA200 regime
  - PIT fundamentals
  - recent SEC filing metadata
- Screener tightens alpha quality with:
  - `relative_strength_60d >= 0`
  - `return_60d >= 0`
  - `atr_pct <= 0.08`
  - market regime rejection when SPY is below MA200
- Strategy notes:
  - `pullback`: stronger quality / RS names get a larger target multiple
  - `breakout`: weak volume breakout is filtered harder and strong quality / RS names get a larger target multiple
  - `quality_momentum`: continuation setup using quality + momentum confirmation
- Market regime sizing:
  - SPY below MA50 and 20d return negative: new signals use `0.5x` size
  - SPY below MA200: new signals are blocked

## Backtest And UI

`run-backtest` reads saved signals from `swing_meta.signal`, runs the event-driven engine, and stores:

- `swing_mart.backtest_trade_log`
- `swing_mart.backtest_equity_curve`
- `swing_mart.backtest_run_summary`

Web UI routes:

- `/` dashboard
- `/signals` recent signals
- `/backtests` recent runs
- `/backtests/run` run and save a backtest from the browser (supports selecting single or combined strategies like `breakout+pullback`)
- `/backtests/{run_id}` detail page with:
  - strategy vs SPY chart
  - symbol contribution
  - strategy / exit summary
  - monthly / strategy / exit / sector slice metrics
  - trade log and daily equity table

## Data Ownership

Swing writes only to:

- `swing_meta.*`
- `swing_mart.*`
- `swing_raw.*`

Swing must not write to Quant-owned:

- `raw.*`
- `stg.*`
- `meta.*`
- `mart.*`

## Environment

- `INFRA_HOST` is the canonical shared host override
- `POSTGRES_HOST` defaults to `INFRA_HOST` unless explicitly set
- `MINIO_ENDPOINT` defaults to `http://${INFRA_HOST}:9000` unless explicitly set

Important runtime defaults live in [config.py](/Users/kyle/Documents/Workspace/auto_trading_system/swing_trading_system/src/swing_trading_system/config.py:1).

## User Manual

End-user workflow and screen guide: [docs/user_manual.md](/Users/kyle/Documents/Workspace/auto_trading_system/swing_trading_system/docs/user_manual.md:1)
