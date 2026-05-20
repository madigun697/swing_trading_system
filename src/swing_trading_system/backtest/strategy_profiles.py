"""Backtest strategy selection profiles."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from swing_trading_system.backtest.models import BacktestConfig
from swing_trading_system.market_regime import MarketRegimeId


@dataclass(frozen=True)
class StrategyProfile:
    key: str
    label: str
    signal_strategy_filter: str | None = None
    aliases: tuple[str, ...] = ()
    require_market_regime: bool = False
    apply_regime_policy: bool = False
    config_overrides: Mapping[str, Any] = field(default_factory=dict)

    def matches(self, value: str | None) -> bool:
        normalized = normalize_strategy_key(value)
        return normalized == self.key or normalized in self.aliases


STABLE_ALPHA_HYBRID_MULTIPLIERS: dict[str, dict[str, float]] = {
    MarketRegimeId.R1_STRONG_BULL.value: {
        "breakout": 1.15,
        "quality_momentum": 1.15,
        "pullback": 0.50,
    },
    MarketRegimeId.R2_VOLATILE_BULL.value: {
        "breakout": 0.75,
        "quality_momentum": 0.80,
        "pullback": 0.40,
    },
    MarketRegimeId.R3_SIDEWAYS.value: {
        "breakout": 0.35,
        "quality_momentum": 0.50,
        "pullback": 0.25,
    },
    MarketRegimeId.R4_EARLY_BEAR.value: {
        "breakout": 0.0,
        "quality_momentum": 0.0,
        "pullback": 0.0,
    },
    MarketRegimeId.R5_DEEP_BEAR.value: {
        "breakout": 0.0,
        "quality_momentum": 0.0,
        "pullback": 0.0,
    },
}


STRATEGY_PROFILES: tuple[StrategyProfile, ...] = (
    StrategyProfile(
        key="market_regime",
        label="Market Regime Switching",
        aliases=("__market_regime__", "market-regime"),
        require_market_regime=True,
        apply_regime_policy=True,
    ),
    StrategyProfile(key="all_signals", label="전체 저장 signal", aliases=("", "all")),
    StrategyProfile(
        key="breakout", label="Breakout", signal_strategy_filter="breakout"
    ),
    StrategyProfile(
        key="pullback", label="Pullback", signal_strategy_filter="pullback"
    ),
    StrategyProfile(
        key="quality_momentum",
        label="Quality Momentum",
        signal_strategy_filter="quality_momentum",
        aliases=("quality-momentum",),
    ),
    StrategyProfile(
        key="breakout+pullback",
        label="Breakout + Pullback",
        signal_strategy_filter="breakout+pullback",
    ),
    StrategyProfile(
        key="breakout+quality_momentum",
        label="Breakout + Quality Momentum",
        signal_strategy_filter="breakout+quality_momentum",
        aliases=("breakout+quality-momentum",),
    ),
    StrategyProfile(
        key="pullback+quality_momentum",
        label="Pullback + Quality Momentum",
        signal_strategy_filter="pullback+quality_momentum",
        aliases=("pullback+quality-momentum",),
    ),
    StrategyProfile(
        key="stable_alpha_hybrid",
        label="Stable Alpha Hybrid",
        signal_strategy_filter="breakout+pullback+quality_momentum",
        aliases=("stable-alpha-hybrid",),
        apply_regime_policy=True,
        config_overrides={
            "max_positions": 15,
            "max_gross_exposure_pct": 1.2,
            "max_portfolio_risk_pct": 0.07,
            "target_scale_out_pct": 0.5,
            "trailing_ma_days": 10,
            "regime_strategy_multipliers": STABLE_ALPHA_HYBRID_MULTIPLIERS,
            "stop_loss_cooldown_lookback_days": 20,
            "stop_loss_cooldown_threshold": 6,
        },
    ),
)


def normalize_strategy_key(value: str | None) -> str:
    return (value or "").strip().lower().replace("-", "_")


def strategy_profiles_for_ui() -> list[dict[str, str]]:
    return [
        {"value": profile.key, "label": profile.label} for profile in STRATEGY_PROFILES
    ]


def resolve_strategy_profile(value: str | None) -> StrategyProfile:
    normalized = normalize_strategy_key(value)
    for profile in STRATEGY_PROFILES:
        if profile.matches(normalized):
            return profile
    return StrategyProfile(
        key=normalized,
        label="Custom",
        signal_strategy_filter=(value or "").strip() or None,
    )


def apply_strategy_profile_config(
    config: BacktestConfig,
    profile: StrategyProfile,
    *,
    skip_fields: set[str] | None = None,
) -> BacktestConfig:
    if not profile.config_overrides:
        return config
    skip_fields = skip_fields or set()
    payload = config.to_dict()
    for key, value in profile.config_overrides.items():
        if key not in skip_fields:
            payload[key] = value
    return BacktestConfig(**payload)
