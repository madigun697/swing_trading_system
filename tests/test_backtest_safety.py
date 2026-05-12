from datetime import date, timedelta

from swing_trading_system.backtest.engine import BacktestEngine
from swing_trading_system.backtest.models import BacktestConfig, BacktestSignal, PriceBar


def signal() -> BacktestSignal:
    return BacktestSignal(1, "AAA", date(2026, 1, 1), "breakout", 100, 95, 110, 5, 10)


def bar(offset: int, open_price=100, high=101, low=99, close=100) -> PriceBar:
    return PriceBar("AAA", date(2026, 1, 1) + timedelta(days=offset), open_price, high, low, close)


def test_signal_day_bar_is_ignored_for_entry() -> None:
    result = BacktestEngine().run(
        [signal()],
        {"AAA": [bar(0, open_price=1, high=999, low=1), bar(1, open_price=100), bar(2, high=111)]},
        BacktestConfig(fee_bps=0, slippage_bps=0),
        run_id="r",
    )

    assert result.trades[0].entry_date == date(2026, 1, 2)
    assert result.trades[0].entry_price == 100


def test_entry_bar_exit_is_forbidden() -> None:
    result = BacktestEngine().run(
        [signal()],
        {"AAA": [bar(1, open_price=100, high=999, low=1), bar(2, high=101, low=99, close=100)]},
        BacktestConfig(fee_bps=0, slippage_bps=0, max_hold_days=10),
        run_id="r",
    )

    assert result.trades[0].exit_date == date(2026, 1, 3)
    assert result.trades[0].exit_reason == "end_of_data"


def test_max_hold_exit_does_not_need_future_beyond_exit_bar() -> None:
    result = BacktestEngine().run(
        [signal()],
        {"AAA": [bar(1, open_price=100), bar(2, close=103), bar(3, close=104)]},
        BacktestConfig(fee_bps=0, slippage_bps=0, max_hold_days=1),
        run_id="r",
    )

    assert result.trades[0].exit_reason == "max_hold"
    assert result.trades[0].exit_date == date(2026, 1, 3)
