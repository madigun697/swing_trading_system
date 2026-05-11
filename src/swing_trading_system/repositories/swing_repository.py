"""Persistence skeleton for Swing-owned schemas."""

from __future__ import annotations

from datetime import date
from typing import Any

from psycopg.types.json import Jsonb

from swing_trading_system.config import Settings
from swing_trading_system.storage import postgres_connection


class SwingRepository:
    """Repository for Swing-owned domain persistence."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings

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
