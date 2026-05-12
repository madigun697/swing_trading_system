from pathlib import Path


def test_backtest_repository_uses_swing_mart_for_writes_and_stg_for_reads() -> None:
    source = Path("src/swing_trading_system/backtest/repository.py").read_text()

    assert "FROM swing_meta.signal" in source
    assert "FROM stg.stg_daily_prices" in source
    assert "INSERT INTO swing_mart.backtest_trade_log" in source
    assert "INSERT INTO swing_mart.backtest_equity_curve" in source
    assert "INSERT INTO stg." not in source
    assert "UPDATE stg." not in source
    assert "INSERT INTO raw." not in source
