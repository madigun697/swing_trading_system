from datetime import date

from swing_trading_system.screening.features import ScreeningFeatures
from swing_trading_system.screening.screener import Screener, ScreenerConfig


def feature(**overrides):
    values = dict(
        symbol="AAA",
        as_of_date=date(2026, 1, 1),
        close=100.0,
        volume=2_000_000.0,
        dollar_volume=200_000_000.0,
        return_20d=0.05,
        return_60d=0.10,
        return_120d=0.20,
        relative_strength_60d=0.03,
        average_dollar_volume_20d=100_000_000.0,
        atr_14=3.0,
        atr_pct=0.03,
        volume_ratio_20d=1.5,
        ma_20=98.0,
        ma_50=95.0,
        ma_200=80.0,
        trend_up=True,
        recent_high_20=110.0,
        previous_high_20=109.0,
        recent_low_20=90.0,
        history_days=220,
    )
    values.update(overrides)
    return ScreeningFeatures(**values)


def test_screener_returns_passed_candidates_sorted() -> None:
    screener = Screener(ScreenerConfig(max_candidates=1))

    candidates = screener.screen([feature(symbol="AAA", relative_strength_60d=0.01), feature(symbol="BBB", relative_strength_60d=0.10)])

    assert [candidate.symbol for candidate in candidates] == ["BBB"]
    assert candidates[0].passed is True


def test_screener_rejects_low_liquidity() -> None:
    candidate = Screener().evaluate(feature(average_dollar_volume_20d=1000.0))

    assert candidate.passed is False
    assert "below_min_adv" in candidate.reason
