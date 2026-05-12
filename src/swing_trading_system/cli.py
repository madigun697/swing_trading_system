"""Command-line interface for Swing system operations."""

from __future__ import annotations

import argparse
import json
from datetime import date
from typing import Any, Sequence

from swing_trading_system.backfill import backfill_sprint2_bootstrap
from swing_trading_system.backtest.engine import BacktestEngine
from swing_trading_system.backtest.models import BacktestConfig
from swing_trading_system.backtest.repository import BacktestRepository
from swing_trading_system.config import Settings
from swing_trading_system.db import check_database_connection, initialize_schema
from swing_trading_system.repositories.shared_market import SharedMarketRepository
from swing_trading_system.repositories.swing_repository import SwingRepository
from swing_trading_system.screening.input_loader import ScreeningInputLoader
from swing_trading_system.screening.pipeline import ScreeningPipeline
from swing_trading_system.screening.screener import Screener, ScreenerConfig
from swing_trading_system.screening.universe import UniverseSelector
from swing_trading_system.storage import check_minio_connection
from swing_trading_system.strategies import BreakoutStrategy, PullbackStrategy, StrategyContext


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Swing trading system operational CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("check-connection", help="Check PostgreSQL and MinIO connectivity")
    subparsers.add_parser("check-readiness", help="Check required Quant shared relations")
    subparsers.add_parser("init-db", help="Initialize Swing-owned schemas and tables")
    subparsers.add_parser("backfill-bootstrap", help="Seed Sprint 2 bootstrap data into Swing-owned schemas")

    backfill_signals = subparsers.add_parser("backfill-signals", help="Backfill daily screening/strategy signals over a date range")
    backfill_signals.add_argument("--start-date", required=True, help="Backfill start date YYYY-MM-DD")
    backfill_signals.add_argument("--end-date", required=True, help="Backfill end date YYYY-MM-DD")
    backfill_signals.add_argument("--frequency", choices=("daily", "weekly", "monthly"), default="weekly")
    backfill_signals.add_argument("--max-universe", type=int, default=None)
    backfill_signals.add_argument("--symbols", help="Comma-separated symbols; defaults to top liquid universe")
    backfill_signals.add_argument("--dry-run", action="store_true", help="Compute without writing Swing schema rows")
    backfill_signals.add_argument("--force", action="store_true", help="Recompute dates even when signals already exist")

    run_daily = subparsers.add_parser("run-daily", help="Run Sprint 2 screening and strategy pipeline")
    run_daily.add_argument("--as-of", dest="as_of", help="As-of date in YYYY-MM-DD format; defaults to latest shared trade date")
    run_daily.add_argument("--symbols", help="Comma-separated symbols; defaults to top liquid universe")
    run_daily.add_argument("--max-universe", type=int, default=None, help="Maximum universe size")
    run_daily.add_argument("--dry-run", action="store_true", help="Compute results without writing to Swing schemas")

    run_backtest = subparsers.add_parser("run-backtest", help="Run Sprint 3 signal-based backtest")
    run_backtest.add_argument("--start-date", help="Signal start date YYYY-MM-DD")
    run_backtest.add_argument("--end-date", help="Signal end date YYYY-MM-DD")
    run_backtest.add_argument("--strategy", help="Strategy filter")
    run_backtest.add_argument("--symbols", help="Comma-separated symbols")
    run_backtest.add_argument("--initial-equity", type=float, default=None)
    run_backtest.add_argument("--fee-bps", type=float, default=None)
    run_backtest.add_argument("--slippage-bps", type=float, default=None)
    run_backtest.add_argument("--max-hold-days", type=int, default=None)
    run_backtest.add_argument("--max-positions", type=int, default=None)
    run_backtest.add_argument("--max-gross-exposure-pct", type=float, default=None)
    run_backtest.add_argument("--dry-run", action="store_true", help="Run without saving backtest results")
    return parser


def _json_default(value: Any) -> str:
    return str(value)


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, default=_json_default, sort_keys=True))


def handle_check_connection(settings: Settings | None = None) -> tuple[int, dict[str, Any]]:
    settings = settings or Settings()
    database = check_database_connection(settings)
    try:
        minio_ok = check_minio_connection(settings)
        minio_detail = "connected"
    except Exception as exc:
        minio_ok = False
        minio_detail = f"{type(exc).__name__}: {exc}"
    ok = database.ok and minio_ok
    return (
        0 if ok else 1,
        {
            "ok": ok,
            "database": {"ok": database.ok, "detail": database.detail},
            "minio": {"ok": minio_ok, "detail": minio_detail},
        },
    )


def handle_check_readiness(settings: Settings | None = None) -> tuple[int, dict[str, Any]]:
    readiness = SharedMarketRepository(settings).check_readiness()
    return (0 if readiness.ok else 1, readiness.to_dict())


def handle_init_db(settings: Settings | None = None) -> tuple[int, dict[str, Any]]:
    result = initialize_schema(settings)
    return (0, {"ok": True, **result})


def handle_backfill_bootstrap(settings: Settings | None = None) -> tuple[int, dict[str, Any]]:
    settings = settings or Settings()
    result = backfill_sprint2_bootstrap(
        market_repository=SharedMarketRepository(settings),
        swing_repository=SwingRepository(settings),
    )
    return (0, {"ok": True, **result.to_dict()})


def handle_backfill_signals(args: argparse.Namespace, settings: Settings | None = None) -> tuple[int, dict[str, Any]]:
    settings = settings or Settings()
    market_repository = SharedMarketRepository(settings)
    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date)
    trade_dates = market_repository.fetch_trade_dates(start_date, end_date)
    selected_dates = _select_backfill_dates(trade_dates, args.frequency)
    backtest_repository = BacktestRepository(settings)
    swing_repository = SwingRepository(settings)
    symbols = _parse_symbols(args.symbols)
    runs: list[dict[str, Any]] = []
    total_signals = 0
    total_features = 0
    skipped_existing = 0
    for as_of_date in selected_dates:
        if not args.force and not args.dry_run:
            existing = backtest_repository.fetch_signals(start_date=as_of_date, end_date=as_of_date, symbols=symbols)
            feature_rows = swing_repository.count_feature_rows(as_of_date, symbols=symbols)
            if existing or feature_rows:
                skipped_existing += 1
                runs.append(
                    {
                        "as_of": as_of_date,
                        "skipped": True,
                        "reason": "signals_or_features_already_exist",
                        "signal_count": len(existing),
                        "feature_count": feature_rows,
                    }
                )
                continue
        daily_args = argparse.Namespace(
            as_of=as_of_date.isoformat(),
            symbols=args.symbols,
            max_universe=args.max_universe,
            dry_run=args.dry_run,
        )
        _, payload = handle_run_daily(daily_args, settings)
        runs.append(
            {
                "as_of": as_of_date,
                "signal_count": payload.get("signal_count", 0),
                "feature_count": payload.get("feature_count", 0),
                "candidate_count": payload.get("candidate_count", 0),
                "screening_run_id": payload.get("screening_run_id"),
            }
        )
        total_signals += int(payload.get("signal_count", 0))
        total_features += int(payload.get("feature_count", 0))
    return (
        0,
        {
            "ok": True,
            "dry_run": args.dry_run,
            "frequency": args.frequency,
            "available_trade_dates": len(trade_dates),
            "processed_dates": len(selected_dates),
            "total_features": total_features,
            "total_signals": total_signals,
            "skipped_existing_dates": skipped_existing,
            "runs": runs,
        },
    )


def handle_run_backtest(args: argparse.Namespace, settings: Settings | None = None) -> tuple[int, dict[str, Any]]:
    settings = settings or Settings()
    config = BacktestConfig(
        initial_equity=args.initial_equity or settings.swing_account_equity,
        fee_bps=args.fee_bps if args.fee_bps is not None else settings.swing_fee_bps,
        slippage_bps=args.slippage_bps if args.slippage_bps is not None else settings.swing_slippage_bps,
        max_hold_days=args.max_hold_days or settings.swing_default_max_hold_days,
        max_positions=args.max_positions or settings.swing_max_positions,
        max_gross_exposure_pct=(
            args.max_gross_exposure_pct
            if args.max_gross_exposure_pct is not None
            else settings.swing_max_gross_exposure_pct
        ),
    )
    repository = BacktestRepository(settings)
    start_date = date.fromisoformat(args.start_date) if args.start_date else None
    end_date = date.fromisoformat(args.end_date) if args.end_date else None
    symbols = _parse_symbols(args.symbols)
    signals = repository.fetch_signals(
        start_date=start_date,
        end_date=end_date,
        strategy=args.strategy,
        symbols=symbols,
    )
    prices = repository.fetch_prices_for_signals(signals, end_date=None, max_hold_days=config.max_hold_days)
    result = BacktestEngine().run(signals=signals, prices_by_symbol=prices, config=config)
    saved = {"trades_saved": 0, "equity_points_saved": 0}
    if not args.dry_run:
        saved = repository.save_result(result)
    return (
        0,
        {
            "ok": True,
            "dry_run": args.dry_run,
            "run_id": result.run_id,
            "signal_count": len(signals),
            "signal_start_date": result.signal_start_date,
            "signal_end_date": result.signal_end_date,
            "trade_start_date": min((trade.entry_date for trade in result.trades), default=None),
            "trade_end_date": max((trade.exit_date for trade in result.trades), default=None),
            "trade_count": len(result.trades),
            "rejection_count": len(result.rejections),
            "metrics": result.metrics,
            **saved,
        },
    )


def handle_run_daily(args: argparse.Namespace, settings: Settings | None = None) -> tuple[int, dict[str, Any]]:
    settings = settings or Settings()
    market_repository = SharedMarketRepository(settings)
    as_of_date = _parse_as_of(args.as_of, market_repository)
    max_universe = args.max_universe or settings.swing_max_universe
    symbols = _parse_symbols(args.symbols)
    universe = UniverseSelector(market_repository).select(
        as_of_date=as_of_date,
        symbols=symbols,
        max_universe=max_universe,
        universe_name="manual" if symbols else "top_liquid",
    )
    repository = _DryRunRepository() if args.dry_run else SwingRepository(settings)
    pipeline = ScreeningPipeline(
        input_loader=ScreeningInputLoader(market_repository),
        repository=repository,
        screener=Screener(
            ScreenerConfig(
                min_price=settings.swing_min_price,
                min_average_dollar_volume=settings.swing_min_adv_usd,
                max_candidates=settings.swing_max_positions,
            )
        ),
        strategies=(PullbackStrategy(), BreakoutStrategy()),
    )
    result = pipeline.run_daily(
        symbols=list(universe.symbols),
        as_of_date=as_of_date,
        universe_name=universe.universe_name,
        context=StrategyContext(
            as_of_date=as_of_date,
            risk_per_trade_pct=settings.swing_risk_per_trade_pct,
            account_equity=settings.swing_account_equity,
        ),
    )
    payload = {"ok": True, "dry_run": args.dry_run, **result.to_dict()}
    if args.dry_run:
        payload["would_write"] = repository.summary()
    return (0, payload)


def _select_backfill_dates(trade_dates: list[date], frequency: str) -> list[date]:
    if frequency == "daily":
        return trade_dates
    selected: list[date] = []
    seen: set[tuple[int, int] | tuple[int, int, int]] = set()
    for trade_date in trade_dates:
        if frequency == "weekly":
            iso = trade_date.isocalendar()
            key: tuple[int, int] | tuple[int, int, int] = (iso.year, iso.week)
        elif frequency == "monthly":
            key = (trade_date.year, trade_date.month, 1)
        else:
            raise ValueError(f"unsupported frequency: {frequency}")
        if key in seen:
            continue
        seen.add(key)
        selected.append(trade_date)
    return selected


def _parse_as_of(value: str | None, market_repository: SharedMarketRepository) -> date:
    if value:
        return date.fromisoformat(value)
    latest = market_repository.fetch_latest_trade_date()
    if latest is None:
        raise RuntimeError("No shared trade date available")
    return latest


def _parse_symbols(value: str | None) -> list[str] | None:
    if not value:
        return None
    symbols = [symbol.strip().upper() for symbol in value.split(",") if symbol.strip()]
    return symbols or None


class _DryRunRepository:
    def __init__(self) -> None:
        self.features: list[dict[str, Any]] = []
        self.signals: list[dict[str, Any]] = []
        self.completed: list[dict[str, Any]] = []

    def create_screening_run(self, run_date: date, universe_name: str | None = None, criteria: dict[str, Any] | None = None) -> dict[str, Any]:
        self.run = {"id": 0, "run_date": run_date, "universe_name": universe_name, "criteria": criteria or {}}
        return self.run

    def complete_screening_run(self, screening_run_id: int, result_count: int, status: str = "completed") -> dict[str, Any]:
        self.completed.append({"screening_run_id": screening_run_id, "result_count": result_count, "status": status})
        return self.completed[-1]

    def upsert_feature_store(self, symbol: str, feature_date: date, feature_set: str, features: dict[str, Any]) -> dict[str, Any]:
        self.features.append({"symbol": symbol, "feature_date": feature_date, "feature_set": feature_set, "features": features})
        return self.features[-1]

    def create_signal(self, **kwargs: Any) -> dict[str, Any]:
        self.signals.append(kwargs)
        return kwargs

    def summary(self) -> dict[str, int]:
        return {"feature_rows": len(self.features), "signals": len(self.signals), "completed_runs": len(self.completed)}


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = Settings()

    if args.command == "check-connection":
        code, payload = handle_check_connection(settings)
    elif args.command == "check-readiness":
        code, payload = handle_check_readiness(settings)
    elif args.command == "init-db":
        code, payload = handle_init_db(settings)
    elif args.command == "backfill-bootstrap":
        code, payload = handle_backfill_bootstrap(settings)
    elif args.command == "backfill-signals":
        code, payload = handle_backfill_signals(args, settings)
    elif args.command == "run-daily":
        code, payload = handle_run_daily(args, settings)
    elif args.command == "run-backtest":
        code, payload = handle_run_backtest(args, settings)
    else:  # pragma: no cover - argparse prevents this path.
        parser.error(f"unknown command: {args.command}")

    _print_json(payload)
    return code


def main(argv: Sequence[str] | None = None) -> None:
    raise SystemExit(run(argv))


if __name__ == "__main__":
    main()
