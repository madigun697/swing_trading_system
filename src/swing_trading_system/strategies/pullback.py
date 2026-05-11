"""Pullback strategy v1."""

from __future__ import annotations

from swing_trading_system.screening.screener import ScreeningCandidate
from swing_trading_system.strategies.base import StrategyContext, StrategySignal, calculate_position_size


class PullbackStrategy:
    name = "pullback"

    def generate(self, candidate: ScreeningCandidate, context: StrategyContext) -> StrategySignal | None:
        feature = candidate.features
        close = feature.close
        atr = feature.atr_14
        recent_high = feature.recent_high_20
        if not candidate.passed or not feature.trend_up or close is None or atr is None or recent_high in (None, 0):
            return None
        pullback_pct = (recent_high - close) / recent_high
        near_ma20 = feature.ma_20 is not None and abs(close - feature.ma_20) / close <= 0.04
        near_ma50 = feature.ma_50 is not None and abs(close - feature.ma_50) / close <= 0.06
        if not (0.02 <= pullback_pct <= 0.12 and (near_ma20 or near_ma50)):
            return None
        entry = close
        ma_stop = (feature.ma_50 - atr) if feature.ma_50 is not None else entry - (2.0 * atr)
        stop = min(entry - (1.5 * atr), ma_stop)
        if stop <= 0 or stop >= entry:
            return None
        risk_per_share, position_size = calculate_position_size(entry, stop, context)
        if risk_per_share <= 0 or position_size <= 0:
            return None
        target = max(entry + (2.0 * risk_per_share), recent_high)
        return StrategySignal(
            symbol=candidate.symbol,
            signal_date=context.as_of_date,
            strategy=self.name,
            entry_price=round(entry, 4),
            stop_price=round(stop, 4),
            target_price=round(target, 4),
            risk_per_share=round(risk_per_share, 4),
            position_size=round(position_size, 4),
            score=candidate.score,
            reason="pullback_in_uptrend",
            details={
                **candidate.to_signal_details(),
                "pullback_pct": pullback_pct,
                "near_ma20": near_ma20,
                "near_ma50": near_ma50,
                "risk_multiple_target": 2.0,
            },
        )
