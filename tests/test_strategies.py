from datetime import date

from swing_trading_system.screening.features import ScreeningFeatures
from swing_trading_system.screening.screener import ScreeningCandidate
from swing_trading_system.strategies import BreakoutStrategy, PullbackStrategy, StrategyContext


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
        ma_20=99.0,
        ma_50=96.0,
        ma_200=80.0,
        trend_up=True,
        recent_high_20=106.0,
        previous_high_20=99.5,
        recent_low_20=90.0,
        history_days=220,
    )
    values.update(overrides)
    return ScreeningFeatures(**values)


def candidate(features=None):
    return ScreeningCandidate(symbol="AAA", score=0.8, passed=True, reason="passed", features=features or feature())


def test_pullback_strategy_generates_signal_with_risk_fields() -> None:
    signal = PullbackStrategy().generate(candidate(), StrategyContext(as_of_date=date(2026, 1, 1)))

    assert signal is not None
    assert signal.strategy == "pullback"
    assert signal.stop_price < signal.entry_price < signal.target_price
    assert signal.risk_per_share > 0
    assert signal.position_size > 0


def test_breakout_strategy_generates_signal_with_risk_fields() -> None:
    signal = BreakoutStrategy().generate(candidate(feature(previous_high_20=99.0, volume_ratio_20d=1.6)), StrategyContext(as_of_date=date(2026, 1, 1)))

    assert signal is not None
    assert signal.strategy == "breakout"
    assert signal.stop_price < signal.entry_price < signal.target_price


def test_strategies_reject_failed_candidate() -> None:
    failed = ScreeningCandidate(symbol="AAA", score=0.1, passed=False, reason="bad", features=feature())

    assert PullbackStrategy().generate(failed, StrategyContext(as_of_date=date(2026, 1, 1))) is None
    assert BreakoutStrategy().generate(failed, StrategyContext(as_of_date=date(2026, 1, 1))) is None
