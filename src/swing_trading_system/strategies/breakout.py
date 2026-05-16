"""Breakout strategy v1."""

from __future__ import annotations

from swing_trading_system.screening.screener import ScreeningCandidate
from swing_trading_system.strategies.base import (
    StrategyContext,
    StrategySignal,
    calculate_position_size,
    has_positive_momentum,
    has_quality_or_rs_strength,
    market_position_multiplier,
)


class BreakoutStrategy:
    name = "breakout"

    def generate(
        self, candidate: ScreeningCandidate, context: StrategyContext
    ) -> StrategySignal | None:
        feature = candidate.features
        close = feature.close
        atr = feature.atr_14
        previous_high = feature.previous_high_20
        if (
            not candidate.passed
            or not has_positive_momentum(candidate)
            or not feature.trend_up
            or close is None
            or atr is None
            or previous_high in (None, 0)
        ):
            return None
        position_multiplier = market_position_multiplier(
            candidate, context=context, strategy=self.name
        )
        if position_multiplier <= 0:
            return None
        breakout_ratio = (close / previous_high) - 1.0
        if breakout_ratio < -0.005:
            return None
        breakout_strength = "strong" if breakout_ratio > 0.02 else "weak"
        required_volume_ratio = 1.5
        if (feature.volume_ratio_20d or 0.0) < required_volume_ratio:
            return None
        entry = close
        stop = min(previous_high - (0.5 * atr), entry - (1.5 * atr))
        if stop <= 0 or stop >= entry:
            return None
        risk_per_share, position_size = calculate_position_size(entry, stop, context)
        if risk_per_share <= 0 or position_size <= 0:
            return None
        risk_multiple_target = 2.5 if breakout_strength == "strong" else 1.8
        if has_quality_or_rs_strength(candidate):
            risk_multiple_target += 0.5
        target = entry + (risk_multiple_target * risk_per_share)
        return StrategySignal(
            symbol=candidate.symbol,
            signal_date=context.as_of_date,
            strategy=self.name,
            entry_price=round(entry, 4),
            stop_price=round(stop, 4),
            target_price=round(target, 4),
            risk_per_share=round(risk_per_share, 4),
            position_size=round(position_size * position_multiplier, 4),
            score=candidate.score,
            reason="volume_confirmed_breakout",
            details={
                **candidate.to_signal_details(),
                "breakout_ratio": breakout_ratio,
                "breakout_strength": breakout_strength,
                "volume_ratio_20d": feature.volume_ratio_20d,
                "required_volume_ratio_20d": required_volume_ratio,
                "risk_multiple_target": risk_multiple_target,
                "market_position_multiplier": position_multiplier,
                "market_regime": feature.market_regime,
            },
        )
