"""Read-only access to Quant shared market relations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import psycopg

from swing_trading_system.config import Settings
from swing_trading_system.storage import postgres_connection

REQUIRED_RELATIONS: tuple[str, ...] = (
    "stg.stg_daily_prices",
    "stg.stg_security_master",
    "stg.stg_benchmark_series",
)


@dataclass(frozen=True)
class ReadinessStatus:
    ok: bool
    code: str
    detail: str
    checked_relations: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "code": self.code,
            "detail": self.detail,
            "checked_relations": list(self.checked_relations),
            "metadata": self.metadata,
        }


class SharedMarketRepository:
    """Repository for read-only Quant shared relation access."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings

    def classify_error(self, exc: Exception) -> ReadinessStatus:
        if isinstance(exc, psycopg.OperationalError):
            code = "database_unreachable"
        elif isinstance(exc, psycopg.errors.InvalidSchemaName):
            code = "missing_schema"
        elif isinstance(exc, psycopg.errors.UndefinedTable):
            code = "missing_relation"
        else:
            code = "database_error"
        return ReadinessStatus(
            ok=False,
            code=code,
            detail=f"{type(exc).__name__}: {exc}",
            checked_relations=REQUIRED_RELATIONS,
        )

    def check_readiness(self) -> ReadinessStatus:
        try:
            metadata: dict[str, Any] = {}
            with postgres_connection(self.settings) as conn, conn.cursor() as cur:
                missing = []
                for relation in REQUIRED_RELATIONS:
                    cur.execute("SELECT to_regclass(%s) IS NOT NULL AS exists", (relation,))
                    row = cur.fetchone()
                    if not row or not row["exists"]:
                        missing.append(relation)
                if missing:
                    return ReadinessStatus(
                        ok=False,
                        code="missing_relation",
                        detail=f"Missing required shared relation(s): {', '.join(missing)}",
                        checked_relations=REQUIRED_RELATIONS,
                    )

                cur.execute("SELECT MAX(effective_as_of)::text AS latest FROM stg.stg_daily_prices")
                price_row = cur.fetchone() or {}
                metadata["daily_prices_latest_effective_as_of"] = price_row.get("latest")

                cur.execute("SELECT MAX(observation_date)::text AS latest FROM stg.stg_benchmark_series")
                benchmark_row = cur.fetchone() or {}
                metadata["benchmark_latest_observation_date"] = benchmark_row.get("latest")

                cur.execute(
                    """
                    SELECT COUNT(*) AS row_count
                    FROM stg.stg_daily_prices
                    WHERE symbol = ANY(%s)
                    """,
                    (["SPY"],),
                )
                support_row = cur.fetchone() or {}
                metadata["support_symbol_rows"] = support_row.get("row_count", 0)

            return ReadinessStatus(
                ok=True,
                code="ready",
                detail="Required Quant shared relations are readable",
                checked_relations=REQUIRED_RELATIONS,
                metadata=metadata,
            )
        except Exception as exc:
            return self.classify_error(exc)

    def fetch_daily_prices(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        clauses = ["symbol = %(symbol)s"]
        params: dict[str, Any] = {"symbol": symbol, "limit": limit}
        if start_date is not None:
            clauses.append("trade_date >= %(start_date)s")
            params["start_date"] = start_date
        if end_date is not None:
            clauses.append("trade_date <= %(end_date)s")
            params["end_date"] = end_date
        where = " AND ".join(clauses)
        query = f"""
            SELECT *
            FROM stg.stg_daily_prices
            WHERE {where}
            ORDER BY trade_date DESC
            LIMIT %(limit)s
        """
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(query, params)
            return list(cur.fetchall())
