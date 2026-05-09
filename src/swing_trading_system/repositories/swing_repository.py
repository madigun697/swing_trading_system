from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Iterable

from psycopg.types.json import Jsonb

from swing_trading_system.domain import AlertEvent, BacktestResult, ScreenCandidate, ScreenRunRecord, TradePlan
from swing_trading_system.storage import postgres_connection, upload_json
from swing_trading_system.config import get_settings


class SwingRepository:
    def __init__(self) -> None:
        self.settings = get_settings()

    def create_screen_run(self, strategy_id: str, signal_date, params: dict) -> int:
        with postgres_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into swing_meta.screen_runs(strategy_id, signal_date, status, params, completed_at)
                values (%s, %s, 'running', %s, null)
                returning screen_run_id
                """,
                (strategy_id, signal_date, Jsonb(params)),
            )
            screen_run_id = int(cur.fetchone()["screen_run_id"])
            conn.commit()
            return screen_run_id

    def save_screen_candidates(self, screen_run_id: int, strategy_id: str, signal_date, candidates: Iterable[ScreenCandidate]) -> ScreenRunRecord:
        candidate_rows = list(candidates)
        payload = [
            {
                "symbol": candidate.symbol,
                "score": str(candidate.score),
                "stop_price": str(candidate.stop_price),
                "target_price": str(candidate.target_price),
                "reasons": candidate.reasons,
                "metadata": candidate.metadata,
            }
            for candidate in candidate_rows
        ]
        artifact_key = f"screens/{strategy_id}/{signal_date.isoformat()}/{screen_run_id}.json"
        upload_json(self.settings.swing_watchlist_bucket, artifact_key, payload, self.settings)
        with postgres_connection() as conn, conn.cursor() as cur:
            for candidate in candidate_rows:
                cur.execute(
                    """
                    insert into swing_mart.screen_candidates(
                        screen_run_id, strategy_id, signal_date, symbol, sector, industry,
                        close_price, adv20, atr14, relative_strength_20d, relative_strength_60d,
                        volume_ratio_20d, breakout_level, pullback_distance_pct, score,
                        risk_per_share, stop_price, target_price, metadata
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (screen_run_id, symbol) do update set
                        score = excluded.score,
                        metadata = excluded.metadata,
                        stop_price = excluded.stop_price,
                        target_price = excluded.target_price
                    """,
                    (
                        screen_run_id,
                        strategy_id,
                        signal_date,
                        candidate.symbol,
                        candidate.sector,
                        candidate.industry,
                        candidate.close_price,
                        candidate.adv20,
                        candidate.atr14,
                        candidate.relative_strength_20d,
                        candidate.relative_strength_60d,
                        candidate.volume_ratio20,
                        candidate.breakout_level,
                        candidate.pullback_distance_pct,
                        candidate.score,
                        candidate.risk_per_share,
                        candidate.stop_price,
                        candidate.target_price,
                        Jsonb({"reasons": candidate.reasons, **candidate.metadata}),
                    ),
                )
            cur.execute(
                """
                update swing_meta.screen_runs
                set status = 'completed',
                    candidate_count = %s,
                    artifact_bucket = %s,
                    artifact_key = %s,
                    completed_at = now()
                where screen_run_id = %s
                """,
                (len(candidate_rows), self.settings.swing_watchlist_bucket, artifact_key, screen_run_id),
            )
            conn.commit()
        return ScreenRunRecord(screen_run_id, strategy_id, signal_date, len(candidate_rows))

    def list_latest_candidates(self, strategy_id: str | None = None, limit: int = 25) -> list[dict]:
        with postgres_connection(read_only=True) as conn, conn.cursor() as cur:
            cur.execute(
                """
                with latest_run as (
                    select screen_run_id
                    from swing_meta.screen_runs
                    where (%s is null or strategy_id = %s)
                    order by signal_date desc, screen_run_id desc
                    limit 1
                )
                select c.*, r.signal_date
                from swing_mart.screen_candidates c
                join latest_run lr on c.screen_run_id = lr.screen_run_id
                join swing_meta.screen_runs r on r.screen_run_id = c.screen_run_id
                order by c.score desc, c.symbol
                limit %s
                """,
                (strategy_id, strategy_id, limit),
            )
            return [dict(row) for row in cur.fetchall()]

    def save_trade_plans(self, trade_plans: Iterable[TradePlan]) -> int:
        count = 0
        with postgres_connection() as conn, conn.cursor() as cur:
            for plan in trade_plans:
                cur.execute(
                    """
                    insert into swing_meta.trade_plans(
                        strategy_id, signal_date, entry_date, symbol, side, quantity,
                        entry_price, stop_price, target_price, risk_per_share,
                        score, sector, status, notes, metadata
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ready', %s, %s)
                    """,
                    (
                        plan.strategy_id,
                        plan.signal_date,
                        plan.signal_date,
                        plan.symbol,
                        plan.side,
                        plan.quantity,
                        plan.entry_price,
                        plan.stop_price,
                        plan.target_price,
                        plan.risk_per_share,
                        plan.score,
                        plan.sector,
                        plan.notes,
                        Jsonb(plan.metadata),
                    ),
                )
                count += 1
            conn.commit()
        return count

    def list_ready_trade_plans(self, limit: int = 20) -> list[dict]:
        with postgres_connection(read_only=True) as conn, conn.cursor() as cur:
            cur.execute(
                """
                select *
                from swing_meta.trade_plans
                where status in ('ready', 'planned')
                  and broker_order_id is null
                order by signal_date desc, score desc nulls last, trade_plan_id desc
                limit %s
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]

    def mark_trade_plan_submitting(self, trade_plan_id: int) -> None:
        with postgres_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                update swing_meta.trade_plans
                set status = 'submitting', updated_at = now()
                where trade_plan_id = %s
                  and status in ('ready', 'planned')
                """,
                (trade_plan_id,),
            )
            conn.commit()

    def mark_trade_plan_execution_result(self, trade_plan_id: int, broker_order_id: str | None, broker_status: str, *, submitted: bool) -> None:
        with postgres_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                update swing_meta.trade_plans
                set status = %s,
                    broker_order_id = coalesce(%s, broker_order_id),
                    broker_status = %s,
                    updated_at = now()
                where trade_plan_id = %s
                """,
                ("submitted" if submitted else "failed", broker_order_id, broker_status, trade_plan_id),
            )
            conn.commit()

    def list_open_positions(self) -> list[dict]:
        with postgres_connection(read_only=True) as conn, conn.cursor() as cur:
            cur.execute(
                """
                select position_id, strategy_id, symbol, quantity, entry_price, stop_price, target_price, opened_at, notes, metadata
                from swing_meta.positions
                where status = 'open'
                order by opened_at desc
                """
            )
            return [dict(row) for row in cur.fetchall()]

    def save_alerts(self, alerts: Iterable[AlertEvent]) -> int:
        alert_rows = list(alerts)
        if not alert_rows:
            return 0
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        artifact_key = f"alerts/{timestamp}.json"
        upload_json(self.settings.swing_alert_bucket, artifact_key, [alert.payload | {"message": alert.message} for alert in alert_rows], self.settings)
        with postgres_connection() as conn, conn.cursor() as cur:
            for alert in alert_rows:
                cur.execute(
                    """
                    insert into swing_meta.alert_events(alert_type, symbol, severity, message, status, payload, artifact_bucket, artifact_key)
                    values (%s, %s, %s, %s, 'pending', %s, %s, %s)
                    """,
                    (
                        alert.alert_type,
                        alert.symbol,
                        alert.severity,
                        alert.message,
                        Jsonb(alert.payload),
                        self.settings.swing_alert_bucket,
                        artifact_key,
                    ),
                )
            conn.commit()
        return len(alert_rows)

    def save_backtest_result(self, result: BacktestResult) -> int:
        artifact_key = f"backtests/{result.strategy_id}/{result.start_date.isoformat()}_{result.end_date.isoformat()}.json"
        upload_json(
            self.settings.swing_backtest_bucket,
            artifact_key,
            {
                "strategy_id": result.strategy_id,
                "summary": {
                    "initial_capital": str(result.initial_capital),
                    "final_equity": str(result.final_equity),
                    "total_return": str(result.total_return),
                    "cagr": str(result.cagr),
                    "max_drawdown": str(result.max_drawdown),
                    "sharpe_ratio": str(result.sharpe_ratio),
                    "win_rate": str(result.win_rate),
                },
                "trades": [trade.__dict__ for trade in result.trades],
                "equity_curve": [point.__dict__ for point in result.equity_curve],
                "params": result.params,
            },
            self.settings,
        )
        with postgres_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                insert into swing_mart.backtest_runs(
                    strategy_id, start_date, end_date, initial_capital, final_equity,
                    total_return, cagr, max_drawdown, sharpe_ratio, win_rate,
                    trade_count, params, artifact_bucket, artifact_key
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                returning backtest_run_id
                """,
                (
                    result.strategy_id,
                    result.start_date,
                    result.end_date,
                    result.initial_capital,
                    result.final_equity,
                    result.total_return,
                    result.cagr,
                    result.max_drawdown,
                    result.sharpe_ratio,
                    result.win_rate,
                    len(result.trades),
                    Jsonb(result.params),
                    self.settings.swing_backtest_bucket,
                    artifact_key,
                ),
            )
            backtest_run_id = int(cur.fetchone()["backtest_run_id"])
            for trade in result.trades:
                cur.execute(
                    """
                    insert into swing_mart.backtest_trades(
                        backtest_run_id, trade_id, strategy_id, symbol, entry_date, exit_date,
                        quantity, entry_price, exit_price, pnl, return_pct, exit_reason, hold_days
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        backtest_run_id,
                        trade.trade_id,
                        trade.strategy_id,
                        trade.symbol,
                        trade.entry_date,
                        trade.exit_date,
                        trade.quantity,
                        trade.entry_price,
                        trade.exit_price,
                        trade.pnl,
                        trade.return_pct,
                        trade.exit_reason,
                        trade.hold_days,
                    ),
                )
            for point in result.equity_curve:
                cur.execute(
                    """
                    insert into swing_mart.backtest_equity_curve(
                        backtest_run_id, trade_date, cash, market_value, total_equity, drawdown
                    ) values (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        backtest_run_id,
                        point.trade_date,
                        point.cash,
                        point.market_value,
                        point.total_equity,
                        point.drawdown,
                    ),
                )
            conn.commit()
        return backtest_run_id

    def list_latest_backtests(self, limit: int = 10) -> list[dict]:
        with postgres_connection(read_only=True) as conn, conn.cursor() as cur:
            cur.execute(
                """
                select *
                from swing_mart.backtest_runs
                order by created_at desc
                limit %s
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]

    def list_recent_alerts(self, limit: int = 20) -> list[dict]:
        with postgres_connection(read_only=True) as conn, conn.cursor() as cur:
            cur.execute(
                """
                select *
                from swing_meta.alert_events
                order by created_at desc
                limit %s
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]
