from datetime import date
from decimal import Decimal

from swing_trading_system.domain import FeatureSnapshot
from swing_trading_system.strategies.breakout import BreakoutStrategy
from swing_trading_system.strategies.pullback import PullbackStrategy


def test_breakout_strategy_selects_valid_snapshot() -> None:
    snapshot = FeatureSnapshot(
        symbol="AAA",
        trade_date=date(2024, 5, 1),
        sector="Tech",
        industry="Software",
        close_price=Decimal("120"),
        adv20=Decimal("20000000"),
        atr14=Decimal("3"),
        sma20=Decimal("110"),
        sma50=Decimal("100"),
        sma200=Decimal("90"),
        volume_ratio20=Decimal("1.6"),
        breakout_20d=Decimal("118"),
        low_20d=Decimal("100"),
        return_5d=Decimal("0.04"),
        return_20d=Decimal("0.12"),
        return_60d=Decimal("0.25"),
        relative_strength_20d=Decimal("0.05"),
        relative_strength_60d=Decimal("0.08"),
    )
    candidate = BreakoutStrategy().evaluate(snapshot)
    assert candidate is not None
    assert candidate.symbol == "AAA"


def test_pullback_strategy_selects_valid_snapshot() -> None:
    snapshot = FeatureSnapshot(
        symbol="BBB",
        trade_date=date(2024, 5, 1),
        sector="Healthcare",
        industry="Biotech",
        close_price=Decimal("118"),
        adv20=Decimal("30000000"),
        atr14=Decimal("2"),
        sma20=Decimal("120"),
        sma50=Decimal("110"),
        sma200=Decimal("95"),
        volume_ratio20=Decimal("1.1"),
        breakout_20d=Decimal("125"),
        low_20d=Decimal("112"),
        return_5d=Decimal("-0.03"),
        return_20d=Decimal("0.10"),
        return_60d=Decimal("0.22"),
        relative_strength_20d=Decimal("0.02"),
        relative_strength_60d=Decimal("0.05"),
    )
    candidate = PullbackStrategy().evaluate(snapshot)
    assert candidate is not None
    assert candidate.stop_price < candidate.close_price
