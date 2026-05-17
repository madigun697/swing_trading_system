"""Backtest repository for signals, price bars, and result persistence."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from psycopg.types.json import Jsonb

from swing_trading_system.backtest.models import (
    BacktestResult,
    BacktestSignal,
    PriceBar,
)
from swing_trading_system.config import Settings
from swing_trading_system.storage import postgres_connection


class BacktestRepository:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings

    def fetch_signals(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        strategy: str | None = None,
        symbols: list[str] | None = None,
        limit: int | None = 500,
        require_market_regime: bool = False,
    ) -> list[BacktestSignal]:
        clauses = [
            "entry_price IS NOT NULL",
            "stop_price IS NOT NULL",
            "target_price IS NOT NULL",
            "risk_per_share IS NOT NULL",
            "position_size IS NOT NULL",
        ]
        params: dict[str, Any] = {"limit": limit}
        if start_date is not None:
            clauses.append("signal_date >= %(start_date)s")
            params["start_date"] = start_date
        if end_date is not None:
            clauses.append("signal_date <= %(end_date)s")
            params["end_date"] = end_date
        if strategy:
            if "+" in strategy:
                strategies = [s.strip() for s in strategy.split("+")]
                clauses.append("strategy = ANY(%(strategies)s)")
                params["strategies"] = strategies
            else:
                clauses.append("strategy = %(strategy)s")
                params["strategy"] = strategy
        if symbols:
            clauses.append("symbol = ANY(%(symbols)s)")
            params["symbols"] = symbols
        if require_market_regime:
            clauses.append(
                """
                COALESCE(
                    details->'market_regime'->>'regime_id',
                    details->'features'->'market_regime'->>'regime_id'
                ) IS NOT NULL
                """
            )
        where = " AND ".join(clauses)
        limit_sql = "LIMIT %(limit)s" if limit is not None else ""
        query = f"""
            SELECT *
            FROM swing_meta.signal
            WHERE {where}
            ORDER BY signal_date ASC, id ASC
            {limit_sql}
        """
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(query, params)
            signals = [BacktestSignal.from_row(row) for row in cur.fetchall()]
            return [signal for signal in signals if signal is not None]

    def fetch_price_bars(
        self,
        symbol: str,
        start_date: date,
        end_date: date | None = None,
        max_hold_days: int = 20,
    ) -> list[PriceBar]:
        effective_end = end_date or (
            start_date + timedelta(days=max_hold_days * 3 + 15)
        )
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT symbol, trade_date, open, high, low, close, volume
                FROM stg.stg_daily_prices
                WHERE symbol = %(symbol)s
                  AND trade_date >= %(start_date)s
                  AND trade_date <= %(end_date)s
                ORDER BY trade_date ASC
                """,
                {"symbol": symbol, "start_date": start_date, "end_date": effective_end},
            )
            bars = [PriceBar.from_row(row) for row in cur.fetchall()]
            return [bar for bar in bars if bar is not None]

    def fetch_prices_for_signals(
        self,
        signals: list[BacktestSignal],
        end_date: date | None = None,
        max_hold_days: int = 20,
        benchmark_symbol: str | None = None,
    ) -> dict[str, list[PriceBar]]:
        prices: dict[str, list[PriceBar]] = {}
        signal_dates_by_symbol: dict[str, list[date]] = {}
        for signal in signals:
            signal_dates_by_symbol.setdefault(signal.symbol, []).append(
                signal.signal_date
            )
        for symbol, signal_dates in signal_dates_by_symbol.items():
            start_date = min(signal_dates)
            effective_end = end_date or (
                max(signal_dates) + timedelta(days=max_hold_days * 3 + 15)
            )
            prices[symbol] = self.fetch_price_bars(
                symbol=symbol,
                start_date=start_date,
                end_date=effective_end,
                max_hold_days=max_hold_days,
            )
        if benchmark_symbol and signal_dates_by_symbol:
            all_signal_dates = [
                signal_date
                for signal_dates in signal_dates_by_symbol.values()
                for signal_date in signal_dates
            ]
            start_date = min(all_signal_dates)
            effective_end = end_date or (
                max(all_signal_dates) + timedelta(days=max_hold_days * 3 + 15)
            )
            prices[benchmark_symbol] = self.fetch_price_bars(
                symbol=benchmark_symbol,
                start_date=start_date,
                end_date=effective_end,
                max_hold_days=max_hold_days,
            )
        return prices

    def save_result(self, result: BacktestResult) -> dict[str, int]:
        with postgres_connection(self.settings) as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM swing_mart.backtest_trade_log WHERE run_id = %(run_id)s",
                        {"run_id": result.run_id},
                    )
                    cur.execute(
                        "DELETE FROM swing_mart.backtest_equity_curve WHERE run_id = %(run_id)s",
                        {"run_id": result.run_id},
                    )
                    cur.execute(
                        "DELETE FROM swing_mart.backtest_run_summary WHERE run_id = %(run_id)s",
                        {"run_id": result.run_id},
                    )
                    for trade in result.trades:
                        cur.execute(
                            """
                            INSERT INTO swing_mart.backtest_trade_log (
                                run_id, symbol, entry_date, exit_date, entry_price, exit_price, quantity, pnl, details
                            ) VALUES (
                                %(run_id)s, %(symbol)s, %(entry_date)s, %(exit_date)s, %(entry_price)s, %(exit_price)s,
                                %(quantity)s, %(pnl)s, %(details)s::jsonb
                            )
                            """,
                            {
                                "run_id": trade.run_id,
                                "symbol": trade.symbol,
                                "entry_date": trade.entry_date,
                                "exit_date": trade.exit_date,
                                "entry_price": trade.entry_price,
                                "exit_price": trade.exit_price,
                                "quantity": trade.quantity,
                                "pnl": trade.pnl,
                                "details": Jsonb(
                                    {
                                        **trade.details,
                                        "exit_reason": trade.exit_reason,
                                        "strategy": trade.strategy,
                                    }
                                ),
                            },
                        )
                    for point in result.equity_curve:
                        cur.execute(
                            """
                            INSERT INTO swing_mart.backtest_equity_curve (run_id, equity_date, equity, drawdown, details)
                            VALUES (%(run_id)s, %(equity_date)s, %(equity)s, %(drawdown)s, %(details)s::jsonb)
                            ON CONFLICT (run_id, equity_date)
                            DO UPDATE SET equity = EXCLUDED.equity, drawdown = EXCLUDED.drawdown, details = EXCLUDED.details
                            """,
                            {
                                "run_id": point.run_id,
                                "equity_date": point.equity_date,
                                "equity": point.equity,
                                "drawdown": point.drawdown,
                                "details": Jsonb(
                                    {
                                        **point.details,
                                        "metrics": result.metrics,
                                        "config": result.config.to_dict(),
                                    }
                                ),
                            },
                        )
                    cur.execute(
                        """
                        INSERT INTO swing_mart.backtest_run_summary (
                            run_id, start_date, end_date, signal_start_date, signal_end_date, initial_equity, final_equity,
                            total_pnl, total_return, max_drawdown, win_rate, profit_factor, trade_count, rejection_count,
                            metrics, config, rejections
                        ) VALUES (
                            %(run_id)s, %(start_date)s, %(end_date)s, %(signal_start_date)s, %(signal_end_date)s,
                            %(initial_equity)s, %(final_equity)s, %(total_pnl)s, %(total_return)s, %(max_drawdown)s,
                            %(win_rate)s, %(profit_factor)s, %(trade_count)s, %(rejection_count)s,
                            %(metrics)s::jsonb, %(config)s::jsonb, %(rejections)s::jsonb
                        )
                        """,
                        _summary_params(result),
                    )
        return {
            "trades_saved": len(result.trades),
            "equity_points_saved": len(result.equity_curve),
            "summary_saved": 1,
        }

    def list_recent_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(
                """
                WITH trade_runs AS (
                    SELECT run_id,
                           COUNT(*) AS trade_count,
                           SUM(pnl) AS total_pnl,
                           MIN(entry_date) AS start_date,
                           MAX(exit_date) AS end_date,
                           MAX(created_at) AS created_at
                    FROM swing_mart.backtest_trade_log
                    GROUP BY run_id
                )
                SELECT COALESCE(summary.run_id, trade_runs.run_id) AS run_id,
                       COALESCE(summary.trade_count, trade_runs.trade_count, 0) AS trade_count,
                       COALESCE(summary.total_pnl, trade_runs.total_pnl, 0) AS total_pnl,
                       COALESCE(summary.start_date, trade_runs.start_date) AS start_date,
                       COALESCE(summary.end_date, trade_runs.end_date) AS end_date,
                       COALESCE(summary.created_at, trade_runs.created_at) AS created_at
                FROM trade_runs
                FULL OUTER JOIN swing_mart.backtest_run_summary summary USING (run_id)
                ORDER BY COALESCE(summary.created_at, trade_runs.created_at) DESC
                LIMIT %(limit)s
                """,
                {"limit": limit},
            )
            return list(cur.fetchall())

    def fetch_run_trades(self, run_id: str) -> list[dict[str, Any]]:
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM swing_mart.backtest_trade_log
                WHERE run_id = %(run_id)s
                ORDER BY entry_date ASC, id ASC
                """,
                {"run_id": run_id},
            )
            return list(cur.fetchall())

    def fetch_run_summary(self, run_id: str) -> dict[str, Any]:
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM swing_mart.backtest_run_summary WHERE run_id = %(run_id)s",
                {"run_id": run_id},
            )
            row = cur.fetchone()
            if row:
                return dict(row)
            trades = self.fetch_run_trades(run_id)
            equity = self.fetch_run_equity_curve(run_id)
            metrics = (
                (equity[-1].get("details") or {}).get("metrics", {}) if equity else {}
            )
            config = (
                (equity[-1].get("details") or {}).get("config", {}) if equity else {}
            )
            return {
                "run_id": run_id,
                "start_date": min(
                    (trade.get("entry_date") for trade in trades), default=None
                ),
                "end_date": max(
                    (trade.get("exit_date") for trade in trades), default=None
                ),
                "signal_start_date": metrics.get("signal_start_date"),
                "signal_end_date": metrics.get("signal_end_date"),
                "initial_equity": config.get("initial_equity"),
                "final_equity": equity[-1].get("equity") if equity else None,
                "total_pnl": metrics.get(
                    "total_pnl", sum(_safe_float(trade.get("pnl")) for trade in trades)
                ),
                "total_return": metrics.get("total_return"),
                "max_drawdown": metrics.get("max_drawdown"),
                "win_rate": metrics.get("win_rate"),
                "profit_factor": metrics.get("profit_factor"),
                "trade_count": len(trades),
                "rejection_count": metrics.get("rejection_count", 0),
                "metrics": metrics,
                "config": config,
                "rejections": [],
            }

    def fetch_run_equity_curve(self, run_id: str) -> list[dict[str, Any]]:
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM swing_mart.backtest_equity_curve
                WHERE run_id = %(run_id)s
                ORDER BY equity_date ASC, id ASC
                """,
                {"run_id": run_id},
            )
            return list(cur.fetchall())

    def count_signals(self) -> int:
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM swing_meta.signal")
            row = cur.fetchone() or {}
            return int(row.get("n", 0))


def _summary_params(result: BacktestResult) -> dict[str, Any]:
    start_date = min((trade.entry_date for trade in result.trades), default=None)
    end_date = max((trade.exit_date for trade in result.trades), default=None)
    final_equity = (
        result.equity_curve[-1].equity
        if result.equity_curve
        else result.config.initial_equity
    )
    return {
        "run_id": result.run_id,
        "start_date": start_date,
        "end_date": end_date,
        "signal_start_date": result.signal_start_date,
        "signal_end_date": result.signal_end_date,
        "initial_equity": result.config.initial_equity,
        "final_equity": final_equity,
        "total_pnl": result.metrics.get("total_pnl", 0.0),
        "total_return": result.metrics.get("total_return", 0.0),
        "max_drawdown": result.metrics.get("max_drawdown", 0.0),
        "win_rate": result.metrics.get("win_rate", 0.0),
        "profit_factor": result.metrics.get("profit_factor"),
        "trade_count": len(result.trades),
        "rejection_count": len(result.rejections),
        "metrics": Jsonb(result.metrics),
        "config": Jsonb(result.config.to_dict()),
        "rejections": Jsonb([rejection.to_dict() for rejection in result.rejections]),
    }


def _safe_float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
