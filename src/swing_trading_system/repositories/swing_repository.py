"""Persistence skeleton for Swing-owned schemas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from psycopg.types.json import Jsonb

from swing_trading_system.config import Settings
from swing_trading_system.storage import postgres_connection


class SwingRepository:
    """Repository for Swing-owned domain persistence."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings

    def get_bootstrap_counts(self) -> dict[str, int]:
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM swing_meta.strategy_config) AS strategy_configs,
                    (SELECT COUNT(*) FROM swing_meta.screening_run) AS screening_runs,
                    (SELECT COUNT(*) FROM swing_meta.signal) AS signals,
                    (SELECT COUNT(*) FROM swing_mart.swing_feature_store) AS feature_rows
                """
            )
            row = cur.fetchone() or {}
            return {
                "strategy_configs": int(row.get("strategy_configs", 0)),
                "screening_runs": int(row.get("screening_runs", 0)),
                "signals": int(row.get("signals", 0)),
                "feature_rows": int(row.get("feature_rows", 0)),
            }

    def count_feature_rows(self, feature_date: date, symbols: list[str] | None = None, feature_set: str = "swing_features_v1") -> int:
        params: dict[str, Any] = {"feature_date": feature_date, "feature_set": feature_set}
        symbol_filter = ""
        if symbols:
            symbol_filter = "AND symbol = ANY(%(symbols)s)"
            params["symbols"] = symbols
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COUNT(*) AS n
                FROM swing_mart.swing_feature_store
                WHERE feature_date = %(feature_date)s
                  AND feature_set = %(feature_set)s
                  {symbol_filter}
                """,
                params,
            )
            row = cur.fetchone() or {}
            return int(row.get("n", 0))

    def create_strategy_config(
        self,
        strategy_name: str,
        version: str = "v1",
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO swing_meta.strategy_config (strategy_name, version, params)
                VALUES (%(strategy_name)s, %(version)s, %(params)s::jsonb)
                ON CONFLICT (strategy_name, version)
                DO UPDATE SET params = EXCLUDED.params, updated_at = NOW()
                RETURNING *
                """,
                {
                    "strategy_name": strategy_name,
                    "version": version,
                    "params": Jsonb(params or {}),
                },
            )
            row = cur.fetchone()
            conn.commit()
            return dict(row or {})

    def create_screening_run(
        self,
        run_date: date,
        universe_name: str | None = None,
        criteria: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO swing_meta.screening_run (run_date, universe_name, criteria)
                VALUES (%(run_date)s, %(universe_name)s, %(criteria)s::jsonb)
                RETURNING *
                """,
                {
                    "run_date": run_date,
                    "universe_name": universe_name,
                    "criteria": Jsonb(criteria or {}),
                },
            )
            row = cur.fetchone()
            conn.commit()
            return dict(row or {})

    def complete_screening_run(self, screening_run_id: int, result_count: int, status: str = "completed") -> dict[str, Any]:
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE swing_meta.screening_run
                SET status = %(status)s,
                    result_count = %(result_count)s,
                    completed_at = NOW()
                WHERE id = %(screening_run_id)s
                RETURNING *
                """,
                {
                    "screening_run_id": screening_run_id,
                    "result_count": result_count,
                    "status": status,
                },
            )
            row = cur.fetchone()
            conn.commit()
            return dict(row or {})

    def upsert_feature_store(
        self,
        symbol: str,
        feature_date: date,
        feature_set: str,
        features: dict[str, Any],
    ) -> dict[str, Any]:
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO swing_mart.swing_feature_store (symbol, feature_date, feature_set, features)
                VALUES (%(symbol)s, %(feature_date)s, %(feature_set)s, %(features)s::jsonb)
                ON CONFLICT (symbol, feature_date, feature_set)
                DO UPDATE SET features = EXCLUDED.features, created_at = NOW()
                RETURNING *
                """,
                {
                    "symbol": symbol,
                    "feature_date": feature_date,
                    "feature_set": feature_set,
                    "features": Jsonb(features),
                },
            )
            row = cur.fetchone()
            conn.commit()
            return dict(row or {})

    def create_signal(
        self,
        screening_run_id: int,
        symbol: str,
        signal_date: date,
        strategy: str,
        entry_price: Decimal | float | None = None,
        stop_price: Decimal | float | None = None,
        target_price: Decimal | float | None = None,
        risk_per_share: Decimal | float | None = None,
        position_size: Decimal | float | None = None,
        score: Decimal | float | None = None,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO swing_meta.signal (
                    screening_run_id,
                    symbol,
                    signal_date,
                    strategy,
                    entry_price,
                    stop_price,
                    target_price,
                    risk_per_share,
                    position_size,
                    score,
                    reason,
                    details
                )
                VALUES (
                    %(screening_run_id)s,
                    %(symbol)s,
                    %(signal_date)s,
                    %(strategy)s,
                    %(entry_price)s,
                    %(stop_price)s,
                    %(target_price)s,
                    %(risk_per_share)s,
                    %(position_size)s,
                    %(score)s,
                    %(reason)s,
                    %(details)s::jsonb
                )
                RETURNING *
                """,
                {
                    "screening_run_id": screening_run_id,
                    "symbol": symbol,
                    "signal_date": signal_date,
                    "strategy": strategy,
                    "entry_price": entry_price,
                    "stop_price": stop_price,
                    "target_price": target_price,
                    "risk_per_share": risk_per_share,
                    "position_size": position_size,
                    "score": score,
                    "reason": reason,
                    "details": Jsonb(details or {}),
                },
            )
            row = cur.fetchone()
            conn.commit()
            return dict(row or {})

    def list_recent_signals(self, limit: int = 50) -> list[dict[str, Any]]:
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM swing_meta.signal
                ORDER BY signal_date DESC, id DESC
                LIMIT %(limit)s
                """,
                {"limit": limit},
            )
            return list(cur.fetchall())
