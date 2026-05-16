from datetime import date

from swing_trading_system.screening.features import ScreeningFeatures
from swing_trading_system.screening.screener import ScreeningCandidate
from swing_trading_system.market_regime import MarketRegimeId, default_regime_policy
from swing_trading_system.strategies import (
    BreakoutStrategy,
    PullbackStrategy,
    QualityMomentumStrategy,
    StrategyContext,
)


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
    return ScreeningCandidate(
        symbol="AAA",
        score=0.8,
        passed=True,
        reason="passed",
        features=features or feature(),
    )


def test_pullback_strategy_generates_signal_with_risk_fields() -> None:
    signal = PullbackStrategy().generate(
        candidate(), StrategyContext(as_of_date=date(2026, 1, 1))
    )

    assert signal is not None
    assert signal.strategy == "pullback"
    assert signal.stop_price < signal.entry_price < signal.target_price
    assert signal.risk_per_share > 0
    assert signal.position_size > 0


def test_breakout_strategy_generates_signal_with_risk_fields() -> None:
    signal = BreakoutStrategy().generate(
        candidate(feature(previous_high_20=99.0, volume_ratio_20d=1.6)),
        StrategyContext(as_of_date=date(2026, 1, 1)),
    )

    assert signal is not None
    assert signal.strategy == "breakout"
    assert signal.stop_price < signal.entry_price < signal.target_price
    assert signal.details["risk_multiple_target"] == 1.8


def test_breakout_strategy_uses_strong_breakout_target_and_volume_threshold() -> None:
    weak_volume = BreakoutStrategy().generate(
        candidate(feature(previous_high_20=97.0, volume_ratio_20d=1.4)),
        StrategyContext(as_of_date=date(2026, 1, 1)),
    )
    strong_volume = BreakoutStrategy().generate(
        candidate(feature(previous_high_20=97.0, volume_ratio_20d=1.6)),
        StrategyContext(as_of_date=date(2026, 1, 1)),
    )

    assert weak_volume is None
    assert strong_volume is not None
    assert strong_volume.details["breakout_strength"] == "strong"
    assert strong_volume.details["required_volume_ratio_20d"] == 1.5
    assert strong_volume.details["risk_multiple_target"] == 2.5


def test_strategies_reject_failed_candidate() -> None:
    failed = ScreeningCandidate(
        symbol="AAA", score=0.1, passed=False, reason="bad", features=feature()
    )

    assert (
        PullbackStrategy().generate(
            failed, StrategyContext(as_of_date=date(2026, 1, 1))
        )
        is None
    )
    assert (
        BreakoutStrategy().generate(
            failed, StrategyContext(as_of_date=date(2026, 1, 1))
        )
        is None
    )


def test_strategies_reject_negative_relative_strength() -> None:
    weak = candidate(feature(relative_strength_60d=-0.01))

    assert (
        PullbackStrategy().generate(weak, StrategyContext(as_of_date=date(2026, 1, 1)))
        is None
    )
    assert (
        BreakoutStrategy().generate(weak, StrategyContext(as_of_date=date(2026, 1, 1)))
        is None
    )


def test_market_regime_halves_position_size_below_ma50() -> None:
    normal = PullbackStrategy().generate(
        candidate(), StrategyContext(as_of_date=date(2026, 1, 1))
    )
    defensive = PullbackStrategy().generate(
        candidate(feature(benchmark_above_ma50=False, benchmark_return_20d=-0.02)),
        StrategyContext(as_of_date=date(2026, 1, 1)),
    )

    assert normal is not None
    assert defensive is not None
    assert defensive.position_size == round(normal.position_size * 0.5, 4)
    assert defensive.details["market_position_multiplier"] == 0.5


def test_regime_policy_scales_strategy_position_size() -> None:
    normal = BreakoutStrategy().generate(
        candidate(feature(previous_high_20=99.0, volume_ratio_20d=1.6)),
        StrategyContext(as_of_date=date(2026, 1, 1)),
    )
    regime_scaled = BreakoutStrategy().generate(
        candidate(
            feature(
                previous_high_20=99.0,
                volume_ratio_20d=1.6,
                market_regime={"regime_id": MarketRegimeId.R1_STRONG_BULL.value},
            )
        ),
        StrategyContext(
            as_of_date=date(2026, 1, 1),
            regime_policy=default_regime_policy(require_vix=True),
        ),
    )

    assert normal is not None
    assert regime_scaled is not None
    assert regime_scaled.position_size == round(normal.position_size * 0.605, 4)
    assert regime_scaled.details["market_position_multiplier"] == 0.605


def test_bear_regime_blocks_new_strategy_signal() -> None:
    signal = PullbackStrategy().generate(
        candidate(
            feature(market_regime={"regime_id": MarketRegimeId.R4_EARLY_BEAR.value})
        ),
        StrategyContext(
            as_of_date=date(2026, 1, 1),
            regime_policy=default_regime_policy(require_vix=True),
        ),
    )

    assert signal is None


def test_quality_momentum_strategy_generates_three_r_signal() -> None:
    signal = QualityMomentumStrategy().generate(
        candidate(
            feature(
                relative_strength_60d=0.20,
                return_20d=0.08,
                quality_score=0.75,
                revenue_yoy=0.20,
                net_income_yoy=0.15,
                ocf_margin=0.12,
            )
        ),
        StrategyContext(as_of_date=date(2026, 1, 1)),
    )

    assert signal is not None
    assert signal.strategy == "quality_momentum"
    assert signal.details["risk_multiple_target"] == 3.0
