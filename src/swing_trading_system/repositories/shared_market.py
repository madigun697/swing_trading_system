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
            settings = self.settings or Settings()
            metadata: dict[str, Any] = {}
            with postgres_connection(self.settings) as conn, conn.cursor() as cur:
                missing = []
                for relation in REQUIRED_RELATIONS:
                    cur.execute(
                        "SELECT to_regclass(%s) IS NOT NULL AS exists", (relation,)
                    )
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

                cur.execute(
                    "SELECT MAX(effective_as_of)::text AS latest FROM stg.stg_daily_prices"
                )
                price_row = cur.fetchone() or {}
                metadata["daily_prices_latest_effective_as_of"] = price_row.get(
                    "latest"
                )

                cur.execute(
                    "SELECT MAX(observation_date)::text AS latest FROM stg.stg_benchmark_series"
                )
                benchmark_row = cur.fetchone() or {}
                metadata["benchmark_latest_observation_date"] = benchmark_row.get(
                    "latest"
                )

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

                cur.execute(
                    """
                    SELECT COUNT(*) AS row_count,
                           MAX(observation_date)::text AS latest
                    FROM stg.stg_benchmark_series
                    WHERE benchmark_name = %(benchmark_name)s
                    """,
                    {"benchmark_name": settings.swing_vix_benchmark_name},
                )
                vix_row = cur.fetchone() or {}
                metadata["vix_benchmark_name"] = settings.swing_vix_benchmark_name
                metadata["vix_rows"] = vix_row.get("row_count", 0)
                metadata["vix_latest_observation_date"] = vix_row.get("latest")
                if settings.swing_require_vix and not vix_row.get("row_count", 0):
                    return ReadinessStatus(
                        ok=False,
                        code="missing_vix_benchmark",
                        detail=(
                            "Missing required VIX benchmark series: "
                            f"{settings.swing_vix_benchmark_name}"
                        ),
                        checked_relations=REQUIRED_RELATIONS,
                        metadata=metadata,
                    )

            return ReadinessStatus(
                ok=True,
                code="ready",
                detail="Required Quant shared relations are readable",
                checked_relations=REQUIRED_RELATIONS,
                metadata=metadata,
            )
        except Exception as exc:
            return self.classify_error(exc)

    def fetch_latest_trade_date(self) -> date | None:
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT MAX(trade_date) AS latest_trade_date FROM stg.stg_daily_prices"
            )
            row = cur.fetchone() or {}
            return row.get("latest_trade_date")

    def fetch_trade_dates(
        self, start_date: date, end_date: date, symbol: str = "SPY"
    ) -> list[date]:
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT trade_date
                FROM stg.stg_daily_prices
                WHERE symbol = %(symbol)s
                  AND trade_date >= %(start_date)s
                  AND trade_date <= %(end_date)s
                ORDER BY trade_date ASC
                """,
                {"symbol": symbol, "start_date": start_date, "end_date": end_date},
            )
            return [row["trade_date"] for row in cur.fetchall()]

    def fetch_top_liquid_symbols(self, as_of_date: date, limit: int = 10) -> list[str]:
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT symbol
                FROM stg.stg_daily_prices
                WHERE trade_date = %(as_of_date)s
                GROUP BY symbol
                ORDER BY MAX(dollar_volume) DESC NULLS LAST, symbol ASC
                LIMIT %(limit)s
                """,
                {"as_of_date": as_of_date, "limit": limit},
            )
            return [row["symbol"] for row in cur.fetchall()]

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

    def fetch_benchmark_series(
        self,
        benchmark_names: list[str],
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 2_000,
    ) -> dict[str, list[dict[str, Any]]]:
        if not benchmark_names:
            return {}
        clauses = ["benchmark_name = ANY(%(benchmark_names)s)"]
        params: dict[str, Any] = {
            "benchmark_names": benchmark_names,
            "limit": limit,
        }
        if start_date is not None:
            clauses.append("observation_date >= %(start_date)s")
            params["start_date"] = start_date
        if end_date is not None:
            clauses.append("observation_date <= %(end_date)s")
            params["end_date"] = end_date
        where = " AND ".join(clauses)
        query = f"""
            SELECT benchmark_name, observation_date, value, source
            FROM stg.stg_benchmark_series
            WHERE {where}
            ORDER BY observation_date ASC, benchmark_name ASC
            LIMIT %(limit)s
        """
        grouped: dict[str, list[dict[str, Any]]] = {
            benchmark_name: [] for benchmark_name in benchmark_names
        }
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(query, params)
            for row in cur.fetchall():
                grouped.setdefault(str(row["benchmark_name"]), []).append(dict(row))
        return grouped

    def fetch_security_metadata(
        self, symbols: list[str], as_of_date: date
    ) -> dict[str, dict[str, Any]]:
        if not symbols:
            return {}
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (symbol)
                       symbol, stable_id_or_cik, exchange, security_type, sector, industry, market_cap,
                       shares_outstanding, as_of_date, effective_as_of
                FROM stg.stg_security_master
                WHERE symbol = ANY(%(symbols)s)
                  AND (as_of_date IS NULL OR as_of_date <= %(as_of_date)s)
                ORDER BY symbol, as_of_date DESC NULLS LAST, effective_as_of DESC NULLS LAST
                """,
                {"symbols": symbols, "as_of_date": as_of_date},
            )
            return {row["symbol"]: dict(row) for row in cur.fetchall()}

    def fetch_sector_by_symbol_and_date(
        self, requests: list[tuple[str, date]]
    ) -> dict[tuple[str, date], str]:
        if not requests:
            return {}
        symbols = list(dict.fromkeys(symbol for symbol, _ in requests))
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT symbol, sector, as_of_date, effective_as_of
                FROM stg.stg_security_master
                WHERE symbol = ANY(%(symbols)s)
                  AND sector IS NOT NULL
                ORDER BY symbol ASC,
                         as_of_date DESC NULLS LAST,
                         effective_as_of DESC NULLS LAST
                """,
                {"symbols": symbols},
            )
            metadata_rows = list(cur.fetchall())
        metadata_by_symbol: dict[str, list[dict[str, Any]]] = {}
        for row in metadata_rows:
            metadata_by_symbol.setdefault(str(row["symbol"]), []).append(dict(row))
        resolved: dict[tuple[str, date], str] = {}
        for symbol, as_of_date in requests:
            rows = metadata_by_symbol.get(symbol, [])
            if not rows:
                continue
            selected_sector = None
            for row in rows:
                row_as_of_date = row.get("as_of_date")
                if row_as_of_date is None or row_as_of_date <= as_of_date:
                    selected_sector = row.get("sector")
                    break
            if not selected_sector:
                selected_sector = rows[0].get("sector")
            if selected_sector:
                resolved[(symbol, as_of_date)] = str(selected_sector)
        return resolved

    def fetch_point_in_time_fundamentals(
        self, symbols: list[str], as_of_date: date
    ) -> dict[str, list[dict[str, Any]]]:
        if not symbols:
            return {}
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(
                """
                WITH security AS (
                    SELECT DISTINCT ON (symbol) symbol, stable_id_or_cik
                    FROM stg.stg_security_master
                    WHERE symbol = ANY(%(symbols)s)
                      AND stable_id_or_cik IS NOT NULL
                      AND (as_of_date IS NULL OR as_of_date <= %(as_of_date)s)
                    ORDER BY symbol, as_of_date DESC NULLS LAST, effective_as_of DESC NULLS LAST
                )
                SELECT security.symbol, fundamentals.*
                FROM security
                JOIN stg.int_point_in_time_fundamentals fundamentals
                  ON fundamentals.stable_id_or_cik = security.stable_id_or_cik
                WHERE fundamentals.available_at::date <= %(as_of_date)s
                ORDER BY security.symbol, fundamentals.period_end ASC, fundamentals.available_at ASC
                """,
                {"symbols": symbols, "as_of_date": as_of_date},
            )
            grouped: dict[str, list[dict[str, Any]]] = {
                symbol: [] for symbol in symbols
            }
            for row in cur.fetchall():
                row_dict = dict(row)
                symbol = str(row_dict.pop("symbol"))
                grouped.setdefault(symbol, []).append(row_dict)
            return grouped

    def fetch_filing_metadata(
        self, symbols: list[str], as_of_date: date, limit_per_symbol: int = 12
    ) -> dict[str, list[dict[str, Any]]]:
        if not symbols:
            return {}
        with postgres_connection(self.settings) as conn, conn.cursor() as cur:
            cur.execute(
                """
                WITH security AS (
                    SELECT DISTINCT ON (symbol) symbol, stable_id_or_cik
                    FROM stg.stg_security_master
                    WHERE symbol = ANY(%(symbols)s)
                      AND stable_id_or_cik IS NOT NULL
                      AND (as_of_date IS NULL OR as_of_date <= %(as_of_date)s)
                    ORDER BY symbol, as_of_date DESC NULLS LAST, effective_as_of DESC NULLS LAST
                ),
                ranked AS (
                    SELECT security.symbol, filings.*,
                           ROW_NUMBER() OVER (
                               PARTITION BY security.symbol
                               ORDER BY filings.filing_date DESC NULLS LAST, filings.available_at DESC NULLS LAST
                           ) AS rn
                    FROM security
                    JOIN stg.stg_filing_metadata filings
                      ON filings.stable_id_or_cik = security.stable_id_or_cik
                    WHERE filings.available_at::date <= %(as_of_date)s
                )
                SELECT *
                FROM ranked
                WHERE rn <= %(limit_per_symbol)s
                ORDER BY symbol, filing_date ASC, available_at ASC
                """,
                {
                    "symbols": symbols,
                    "as_of_date": as_of_date,
                    "limit_per_symbol": limit_per_symbol,
                },
            )
            grouped: dict[str, list[dict[str, Any]]] = {
                symbol: [] for symbol in symbols
            }
            for row in cur.fetchall():
                row_dict = dict(row)
                symbol = str(row_dict.pop("symbol"))
                row_dict.pop("rn", None)
                grouped.setdefault(symbol, []).append(row_dict)
            return grouped
