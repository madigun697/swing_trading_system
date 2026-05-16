from datetime import date, timedelta

from swing_trading_system.market_regime import (
    MarketRegimeId,
    classify_market_regime,
    default_regime_policy,
    regime_policy_from_json,
)


def benchmark_rows(days=221, start_close=100.0, step=1.0):
    start = date(2025, 1, 1)
    return [
        {
            "benchmark_name": "SPY",
            "observation_date": start + timedelta(days=idx),
            "value": start_close + (idx * step),
        }
        for idx in range(days)
    ]


def vix_row(value: float, day: date = date(2025, 8, 9)):
    return [{"benchmark_name": "VIXCLS", "observation_date": day, "value": value}]


def test_classifies_strong_bull_when_spy_uptrend_and_low_vix() -> None:
    regime = classify_market_regime(
        benchmark_rows=benchmark_rows(),
        vix_rows=vix_row(16),
        as_of_date=date(2025, 8, 9),
        require_vix=True,
    )

    assert regime.regime_id == MarketRegimeId.R1_STRONG_BULL
    assert regime.vix_value == 16


def test_vix_spike_takes_deep_bear_precedence() -> None:
    regime = classify_market_regime(
        benchmark_rows=benchmark_rows(),
        vix_rows=vix_row(42),
        as_of_date=date(2025, 8, 9),
        require_vix=True,
    )

    assert regime.regime_id == MarketRegimeId.R5_DEEP_BEAR
    assert regime.reason == "deep_bear_spy_trend_or_vix"


def test_default_aggressive_policy_blocks_new_bear_entries() -> None:
    policy = default_regime_policy(require_vix=True)

    assert policy.position_multiplier(MarketRegimeId.R1_STRONG_BULL, "breakout") == 0.605
    assert policy.position_multiplier(MarketRegimeId.R4_EARLY_BEAR, "pullback") == 0.0


def test_policy_json_overrides_default_weights() -> None:
    policy = regime_policy_from_json(
        '{"R3_SIDEWAYS": {"strategy_weights": {"pullback": 1.0}, "max_gross_exposure_pct": 0.25}}',
        require_vix=True,
        profile="aggressive",
    )

    assert policy.position_multiplier(MarketRegimeId.R3_SIDEWAYS, "pullback") == 0.25
    assert policy.position_multiplier(MarketRegimeId.R3_SIDEWAYS, "breakout") == 0.0
