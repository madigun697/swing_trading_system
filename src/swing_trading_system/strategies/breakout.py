from __future__ import annotations

from decimal import Decimal

from swing_trading_system.domain import FeatureSnapshot, ScreenCandidate
from swing_trading_system.strategies.base import BaseSwingStrategy


class BreakoutStrategy(BaseSwingStrategy):
    strategy_id = "breakout"
    display_name = "Volume Breakout"

    def evaluate(self, snapshot: FeatureSnapshot) -> ScreenCandidate | None:
        if not (
            snapshot.close_price > snapshot.breakout_20d
            and snapshot.close_price > snapshot.sma50 > snapshot.sma200
            and snapshot.volume_ratio20 >= Decimal("1.3")
            and snapshot.relative_strength_20d > Decimal("0")
            and snapshot.atr14 > Decimal("0")
        ):
            return None
        stop_price = max(snapshot.breakout_20d - snapshot.atr14, snapshot.close_price * Decimal("0.92"))
        risk_per_share = snapshot.close_price - stop_price
        if risk_per_share <= Decimal("0"):
            return None
        target_price = snapshot.close_price + risk_per_share * Decimal("3")
        score = (
            snapshot.relative_strength_20d * Decimal("120")
            + snapshot.volume_ratio20 * Decimal("15")
            + (snapshot.close_price / snapshot.sma50 - Decimal("1")) * Decimal("100")
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
            pullback_distance_pct=snapshot.close_price / snapshot.sma20 - Decimal("1"),
            score=score,
            risk_per_share=risk_per_share,
            stop_price=stop_price,
            target_price=target_price,
            reasons=["breakout_20d", "volume_expansion", "relative_strength_positive"],
            metadata={"sma50": str(snapshot.sma50), "sma200": str(snapshot.sma200)},
        )
