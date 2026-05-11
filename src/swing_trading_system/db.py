"""Database bootstrap helpers for Swing-owned schemas."""

from __future__ import annotations

from dataclasses import dataclass

from swing_trading_system.config import Settings
from swing_trading_system.storage import postgres_connection

SCHEMA_SQL: tuple[str, ...] = (
    "CREATE SCHEMA IF NOT EXISTS swing_meta",
    "CREATE SCHEMA IF NOT EXISTS swing_mart",
    "CREATE SCHEMA IF NOT EXISTS swing_raw",
    """
    CREATE TABLE IF NOT EXISTS swing_meta.strategy_config (
        id BIGSERIAL PRIMARY KEY,
        strategy_name TEXT NOT NULL,
        version TEXT NOT NULL DEFAULT 'v1',
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        params JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (strategy_name, version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS swing_meta.screening_run (
        id BIGSERIAL PRIMARY KEY,
        run_date DATE NOT NULL,
        status TEXT NOT NULL DEFAULT 'created',
        universe_name TEXT,
        criteria JSONB NOT NULL DEFAULT '{}'::jsonb,
        result_count INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        completed_at TIMESTAMPTZ
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS swing_meta.signal (
        id BIGSERIAL PRIMARY KEY,
        screening_run_id BIGINT REFERENCES swing_meta.screening_run(id),
        symbol TEXT NOT NULL,
        signal_date DATE NOT NULL,
        strategy TEXT NOT NULL,
        entry_price NUMERIC,
        stop_price NUMERIC,
        target_price NUMERIC,
        risk_per_share NUMERIC,
        position_size NUMERIC,
        score NUMERIC,
        reason TEXT,
        details JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS swing_meta.trade_plan (
        id BIGSERIAL PRIMARY KEY,
        signal_id BIGINT REFERENCES swing_meta.signal(id),
        symbol TEXT NOT NULL,
        plan_date DATE NOT NULL,
        status TEXT NOT NULL DEFAULT 'planned',
        entry_price NUMERIC,
        stop_price NUMERIC,
        target_price NUMERIC,
        quantity NUMERIC,
        risk_amount NUMERIC,
        notes TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS swing_meta.position_snapshot (
        id BIGSERIAL PRIMARY KEY,
        symbol TEXT NOT NULL,
        snapshot_date DATE NOT NULL,
        quantity NUMERIC NOT NULL DEFAULT 0,
        average_price NUMERIC,
        market_price NUMERIC,
        unrealized_pnl NUMERIC,
        source TEXT NOT NULL DEFAULT 'manual',
        details JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS swing_meta.alert (
        id BIGSERIAL PRIMARY KEY,
        symbol TEXT,
        alert_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'created',
        severity TEXT NOT NULL DEFAULT 'info',
        message TEXT NOT NULL,
        details JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        sent_at TIMESTAMPTZ
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS swing_meta.execution_order (
        id BIGSERIAL PRIMARY KEY,
        trade_plan_id BIGINT REFERENCES swing_meta.trade_plan(id),
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        order_type TEXT NOT NULL,
        quantity NUMERIC NOT NULL,
        limit_price NUMERIC,
        status TEXT NOT NULL DEFAULT 'dry_run',
        broker_order_id TEXT,
        paper BOOLEAN NOT NULL DEFAULT TRUE,
        details JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS swing_mart.swing_feature_store (
        id BIGSERIAL PRIMARY KEY,
        symbol TEXT NOT NULL,
        feature_date DATE NOT NULL,
        feature_set TEXT NOT NULL,
        features JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (symbol, feature_date, feature_set)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS swing_mart.backtest_trade_log (
        id BIGSERIAL PRIMARY KEY,
        run_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        entry_date DATE,
        exit_date DATE,
        entry_price NUMERIC,
        exit_price NUMERIC,
        quantity NUMERIC,
        pnl NUMERIC,
        details JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS swing_mart.backtest_equity_curve (
        id BIGSERIAL PRIMARY KEY,
        run_id TEXT NOT NULL,
        equity_date DATE NOT NULL,
        equity NUMERIC NOT NULL,
        drawdown NUMERIC,
        details JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (run_id, equity_date)
    )
    """,
)


@dataclass(frozen=True)
class DatabaseCheck:
    ok: bool
    detail: str


def check_database_connection(settings: Settings | None = None) -> DatabaseCheck:
    try:
        with postgres_connection(settings) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            row = cur.fetchone()
            return DatabaseCheck(ok=bool(row and row["ok"] == 1), detail="connected")
    except Exception as exc:
        return DatabaseCheck(ok=False, detail=f"{type(exc).__name__}: {exc}")


def initialize_schema(settings: Settings | None = None) -> dict[str, int]:
    with postgres_connection(settings) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                for statement in SCHEMA_SQL:
                    cur.execute(statement)
    return {"statements_executed": len(SCHEMA_SQL)}
