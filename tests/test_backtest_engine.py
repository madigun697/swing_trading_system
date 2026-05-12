from datetime import date, timedelta

from swing_trading_system.backtest.engine import BacktestEngine
from swing_trading_system.backtest.models import BacktestConfig, BacktestSignal, PriceBar


def signal() -> BacktestSignal:
    return BacktestSignal(
        id=1,
        symbol="AAA",
        signal_date=date(2026, 1, 1),
        strategy="pullback",
        entry_price=100,
        stop_price=95,
        target_price=110,
        risk_per_share=5,
        position_size=10,
    )


def bar(day: int, open_price=100, high=105, low=99, close=102) -> PriceBar:
    return PriceBar("AAA", date(2026, 1, 1) + timedelta(days=day), open_price, high, low, close, 1000)


def test_engine_enters_on_next_open_and_targets_after_entry_bar() -> None:
    result = BacktestEngine().run(
        signals=[signal()],
        prices_by_symbol={"AAA": [bar(0, open_price=1, high=999, low=1), bar(1, open_price=101), bar(2, high=111, low=100)]},
        config=BacktestConfig(fee_bps=0, slippage_bps=0, max_hold_days=5),
        run_id="test-run",
    )

    trade = result.trades[0]
    assert trade.entry_date == date(2026, 1, 2)
    assert trade.entry_price == 101
    assert trade.exit_date == date(2026, 1, 3)
    assert trade.exit_reason == "target"
    assert trade.pnl == 90


def test_engine_rejects_missing_next_bar() -> None:
    result = BacktestEngine().run([signal()], {"AAA": []}, BacktestConfig(), run_id="r")

    assert result.trades == ()
    assert result.rejections[0].reason == "missing_next_bar"


def test_engine_uses_stop_first_when_stop_and_target_same_bar() -> None:
    result = BacktestEngine().run(
        [signal()],
        {"AAA": [bar(1, open_price=100), bar(2, high=120, low=90)]},
        BacktestConfig(fee_bps=0, slippage_bps=0),
        run_id="r",
    )

    assert result.trades[0].exit_reason == "stop_loss_same_bar_conservative"
    assert result.trades[0].exit_price == 95
