from __future__ import annotations

from pathlib import Path

from swing_trading_system.storage import postgres_connection


def init_db() -> None:
    sql_path = Path(__file__).resolve().parents[2] / "sql" / "01_swing_schema.sql"
    ddl = sql_path.read_text(encoding="utf-8")
    with postgres_connection() as conn:
        conn.execute(ddl)
        conn.commit()
