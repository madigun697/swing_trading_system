"""Backtest repository for signals, price bars, and result persistence."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from psycopg.types.json import Jsonb

from swing_trading_system.backtest.models import BacktestResult, BacktestSignal, PriceBar
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
        limit: int = 500,
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
            clauses.append("strategy = %(strategy)s")
            params["strategy"] = strategy
        if symbols:
            clauses.append("symbol = ANY(%(symbols)s)")
            params["symbols"] = symbols
        where = " AND ".join(clauses)
        query = f"""
            SELECT *
            FROM swing_meta.signal
            WHERE {where}
            ORDER BY signal_date ASC, id ASC
            LIMIT %(limit)s
        """
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(query, params)
            signals = [BacktestSignal.from_row(row) for row in cur.fetchall()]
            return [signal for signal in signals if signal is not None]

    def fetch_price_bars(self, symbol: str, start_date: date, end_date: date | None = None, max_hold_days: int = 20) -> list[PriceBar]:
        effective_end = end_date or (start_date + timedelta(days=max_hold_days * 3 + 15))
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
    ) -> dict[str, list[PriceBar]]:
        prices: dict[str, list[PriceBar]] = {}
        for signal in signals:
            current = prices.setdefault(signal.symbol, [])
            if current:
                continue
            current.extend(
                self.fetch_price_bars(
                    symbol=signal.symbol,
                    start_date=signal.signal_date,
                    end_date=end_date,
                    max_hold_days=max_hold_days,
                )
            )
        return prices

    def save_result(self, result: BacktestResult) -> dict[str, int]:
        with postgres_connection(self.settings) as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM swing_mart.backtest_trade_log WHERE run_id = %(run_id)s", {"run_id": result.run_id})
                    cur.execute("DELETE FROM swing_mart.backtest_equity_curve WHERE run_id = %(run_id)s", {"run_id": result.run_id})
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
                                "details": Jsonb({**trade.details, "exit_reason": trade.exit_reason, "strategy": trade.strategy}),
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
                                "details": Jsonb({**point.details, "metrics": result.metrics, "config": result.config.to_dict()}),
                            },
                        )
        return {"trades_saved": len(result.trades), "equity_points_saved": len(result.equity_curve)}

    def list_recent_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT run_id,
                       COUNT(*) AS trade_count,
                       SUM(pnl) AS total_pnl,
                       MIN(entry_date) AS start_date,
                       MAX(exit_date) AS end_date,
                       MAX(created_at) AS created_at
                FROM swing_mart.backtest_trade_log
                GROUP BY run_id
                ORDER BY MAX(created_at) DESC
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
