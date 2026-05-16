"""Quality momentum continuation strategy."""

from __future__ import annotations

from swing_trading_system.screening.screener import ScreeningCandidate
from swing_trading_system.strategies.base import (
    StrategyContext,
    StrategySignal,
    calculate_position_size,
    has_positive_momentum,
    market_position_multiplier,
)


class QualityMomentumStrategy:
    name = "quality_momentum"

    def generate(
        self, candidate: ScreeningCandidate, context: StrategyContext
    ) -> StrategySignal | None:
        feature = candidate.features
        close = feature.close
        atr = feature.atr_14
        if (
            not candidate.passed
            or not has_positive_momentum(candidate)
            or close is None
            or atr is None
        ):
            return None
        if not _has_ordered_trend(feature.ma_20, feature.ma_50, feature.ma_200, close):
            return None
        if (
            feature.relative_strength_60d is None
            or feature.relative_strength_60d < 0.15
        ):
            return None
        if feature.return_20d is None or feature.return_20d <= 0:
            return None
        if feature.quality_score is None or feature.quality_score < 0.60:
            return None
        if feature.revenue_yoy is None or feature.revenue_yoy <= 0:
            return None
        if (feature.net_income_yoy is None or feature.net_income_yoy <= 0) and (
            feature.ocf_margin is None or feature.ocf_margin <= 0
        ):
            return None
        position_multiplier = market_position_multiplier(
            candidate, context=context, strategy=self.name
        )
        if position_multiplier <= 0:
            return None

        entry = close
        ma20_stop = (
            (feature.ma_20 - (0.5 * atr))
            if feature.ma_20 is not None
            else entry - (2.0 * atr)
        )
        stop = min(entry - (1.75 * atr), ma20_stop)
        if stop <= 0 or stop >= entry:
            return None
        risk_per_share, position_size = calculate_position_size(entry, stop, context)
        if risk_per_share <= 0 or position_size <= 0:
            return None
        target = entry + (3.0 * risk_per_share)
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
            reason="quality_momentum_continuation",
            details={
                **candidate.to_signal_details(),
                "risk_multiple_target": 3.0,
                "market_position_multiplier": position_multiplier,
                "market_regime": feature.market_regime,
                "quality_score": feature.quality_score,
                "revenue_yoy": feature.revenue_yoy,
                "net_income_yoy": feature.net_income_yoy,
                "ocf_margin": feature.ocf_margin,
            },
        )


def _has_ordered_trend(
    ma_20: float | None, ma_50: float | None, ma_200: float | None, close: float
) -> bool:
    return (
        ma_20 is not None
        and ma_50 is not None
        and ma_200 is not None
        and close > ma_20 > ma_50 > ma_200
    )
