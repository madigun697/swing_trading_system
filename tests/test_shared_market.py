import psycopg

from swing_trading_system.repositories.shared_market import REQUIRED_RELATIONS, SharedMarketRepository


def test_required_relations_are_sprint_1_contract() -> None:
    assert REQUIRED_RELATIONS == (
        "stg.stg_daily_prices",
        "stg.stg_security_master",
        "stg.stg_benchmark_series",
    )


def test_classify_operational_error() -> None:
    status = SharedMarketRepository().classify_error(psycopg.OperationalError("down"))

    assert status.ok is False
    assert status.code == "database_unreachable"
    assert status.checked_relations == REQUIRED_RELATIONS
