from swing_trading_system.db import SCHEMA_SQL


def test_schema_sql_uses_swing_namespaces_only_for_writes() -> None:
    combined = "\n".join(SCHEMA_SQL)

    assert "CREATE SCHEMA IF NOT EXISTS swing_meta" in combined
    assert "CREATE SCHEMA IF NOT EXISTS swing_mart" in combined
    assert "swing_meta.signal" in combined
    assert "CREATE TABLE IF NOT EXISTS raw." not in combined
    assert "CREATE TABLE IF NOT EXISTS stg." not in combined
    assert "CREATE TABLE IF NOT EXISTS mart." not in combined
