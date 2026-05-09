from __future__ import annotations

from decimal import Decimal

from swing_trading_system.domain import FeatureSnapshot, ScreenCandidate
from swing_trading_system.strategies.base import BaseSwingStrategy


class PullbackStrategy(BaseSwingStrategy):
    strategy_id = "pullback"
    display_name = "Trend Pullback"

    def evaluate(self, snapshot: FeatureSnapshot) -> ScreenCandidate | None:
        if not (
            snapshot.close_price > snapshot.sma50 > snapshot.sma200
            and snapshot.close_price >= snapshot.sma20 * Decimal("0.97")
            and Decimal("-0.10") <= snapshot.return_5d <= Decimal("-0.01")
            and snapshot.relative_strength_60d > Decimal("0")
            and snapshot.atr14 > Decimal("0")
        ):
            return None
        stop_price = min(snapshot.low_20d, snapshot.close_price - snapshot.atr14 * Decimal("1.5"))
        risk_per_share = snapshot.close_price - stop_price
        if risk_per_share <= Decimal("0"):
            return None
        target_price = snapshot.close_price + risk_per_share * Decimal("2.5")
        pullback_distance_pct = (snapshot.close_price / snapshot.sma20) - Decimal("1")
        score = (
            snapshot.relative_strength_60d * Decimal("100")
            + (Decimal("0.12") - abs(snapshot.return_5d)) * Decimal("100")
            + snapshot.volume_ratio20 * Decimal("10")
        )
        return ScreenCandidate(
            strategy_id=self.strategy_id,
            signal_date=snapshot.trade_date,
            symbol=snapshot.symbol,
            sector=snapshot.sector,
            industry=snapshot.industry,
            close_price=snapshot.close_price,
            adv20=snapshot.adv20,
            atr14=snapshot.atr14,
            relative_strength_20d=snapshot.relative_strength_20d,
            relative_strength_60d=snapshot.relative_strength_60d,
            volume_ratio20=snapshot.volume_ratio20,
            breakout_level=snapshot.breakout_20d,
            pullback_distance_pct=pullback_distance_pct,
            score=score,
            risk_per_share=risk_per_share,
            stop_price=stop_price,
            target_price=target_price,
            reasons=["trend_up", "controlled_pullback", "relative_strength_positive"],
            metadata={"sma20": str(snapshot.sma20), "sma50": str(snapshot.sma50), "sma200": str(snapshot.sma200)},
        )
