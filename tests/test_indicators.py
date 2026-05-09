from datetime import date, timedelta
from decimal import Decimal

from swing_trading_system.domain import MarketBar
from swing_trading_system.screening.indicators import atr, average, highest, percent_change, volume_ratio


def _bar(index: int) -> MarketBar:
    day = date(2024, 1, 1) + timedelta(days=index)
    price = Decimal("100") + Decimal(index)
    return MarketBar("AAA", day, price, price + 1, price - 1, price, Decimal("1000") + index, price * 1000)


def test_indicator_helpers() -> None:
    values = [Decimal(i) for i in range(1, 31)]
    bars = [_bar(i) for i in range(30)]
    assert average(values, 5) == Decimal("28")
    assert highest(values, 20, exclude_last=True) == Decimal("29")
    assert percent_change(values, 5) == Decimal("0.2")
    assert volume_ratio([Decimal("10")] * 19 + [Decimal("20")], 20) == Decimal("20") / Decimal("10.5")
    assert atr(bars, 14) == Decimal("2")
