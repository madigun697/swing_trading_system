from __future__ import annotations

import argparse
import json
from datetime import date
from decimal import Decimal

from swing_trading_system.db import init_db
from swing_trading_system.execution.service import PaperExecutionService
from swing_trading_system.pipeline.orchestrator import SwingOrchestrator
from swing_trading_system.repositories.shared_market import SharedMarketRepository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Swing trading system CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db")
    subparsers.add_parser("healthcheck")

    screen = subparsers.add_parser("screen")
    screen.add_argument("--strategy", choices=["breakout", "pullback"], required=True)
    screen.add_argument("--as-of-date", default=None)
    screen.add_argument("--save", action="store_true")

    backtest = subparsers.add_parser("backtest")
    backtest.add_argument("--strategy", choices=["breakout", "pullback"], required=True)
    backtest.add_argument("--start-date", required=True)
    backtest.add_argument("--end-date", required=True)
    backtest.add_argument("--initial-capital", default="100000")
    backtest.add_argument("--save", action="store_true")

    monitor = subparsers.add_parser("monitor")
    monitor.add_argument("--as-of-date", default=None)
    monitor.add_argument("--send-alerts", action="store_true")

    end_of_day = subparsers.add_parser("end-of-day")
    end_of_day.add_argument("--as-of-date", default=None)
    end_of_day.add_argument("--save", action="store_true")
    end_of_day.add_argument("--send-alerts", action="store_true")

    execute = subparsers.add_parser("execute-paper")
    execute.add_argument("--all-ready", action="store_true")
    execute.add_argument("--submit", action="store_true")
    execute.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    orchestrator = SwingOrchestrator()

    if args.command == "init-db":
        init_db()
        print(json.dumps({"ok": True, "message": "swing schema initialized"}))
        return

    if args.command == "healthcheck":
        readiness = SharedMarketRepository().check_readiness()
        print(json.dumps(readiness.__dict__, default=str))
        return

    as_of_date = date.fromisoformat(args.as_of_date) if getattr(args, "as_of_date", None) else date.today()

    if args.command == "screen":
        result = orchestrator.run_screen(strategy_id=args.strategy, as_of_date=as_of_date, save=args.save)
    elif args.command == "backtest":
        result = orchestrator.run_backtest(
            strategy_id=args.strategy,
            start_date=date.fromisoformat(args.start_date),
            end_date=date.fromisoformat(args.end_date),
            initial_capital=Decimal(args.initial_capital),
            save=args.save,
        )
    elif args.command == "monitor":
        result = {"alert_count": orchestrator.monitoring_service.run_end_of_day_monitor(as_of_date=as_of_date, send=args.send_alerts)}
    elif args.command == "end-of-day":
        result = orchestrator.run_end_of_day(as_of_date=as_of_date, save=args.save, send_alerts=args.send_alerts)
    elif args.command == "execute-paper":
        del args.all_ready
        submit = args.submit and not args.dry_run
        result = PaperExecutionService().execute(submit=submit)
    else:
        raise ValueError(f"Unsupported command: {args.command}")

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
