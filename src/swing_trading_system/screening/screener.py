"""Screener v1 candidate scoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from swing_trading_system.screening.features import ScreeningFeatures


@dataclass(frozen=True)
class ScreenerConfig:
    min_price: float = 10.0
    min_average_dollar_volume: float = 10_000_000.0
    min_history_days: int = 200
    max_atr_pct: float = 0.18
    min_relative_strength_60d: float = -0.05
    max_candidates: int = 50


@dataclass(frozen=True)
class ScreeningCandidate:
    symbol: str
    score: float
    passed: bool
    reason: str
    features: ScreeningFeatures
    details: dict[str, Any] = field(default_factory=dict)

    def to_signal_details(self) -> dict[str, Any]:
        return {"screener": self.details, "features": self.features.to_dict()}


class Screener:
    def __init__(self, config: ScreenerConfig | None = None) -> None:
        self.config = config or ScreenerConfig()

    def screen(self, features: list[ScreeningFeatures]) -> list[ScreeningCandidate]:
        candidates = [self.evaluate(feature) for feature in features]
        passed = [candidate for candidate in candidates if candidate.passed]
        return sorted(passed, key=lambda candidate: candidate.score, reverse=True)[: self.config.max_candidates]

    def evaluate(self, feature: ScreeningFeatures) -> ScreeningCandidate:
        rejects = self._reject_reasons(feature)
        score_components = self._score_components(feature)
        score = round(sum(score_components.values()), 6)
        return ScreeningCandidate(
            symbol=feature.symbol,
            score=score,
            passed=not rejects,
            reason="passed" if not rejects else "; ".join(rejects),
            features=feature,
            details={"reject_reasons": rejects, "score_components": score_components},
        )

    def _reject_reasons(self, feature: ScreeningFeatures) -> list[str]:
        reasons: list[str] = []
        if feature.history_days < self.config.min_history_days:
            reasons.append("insufficient_history")
        if feature.close is None or feature.close < self.config.min_price:
            reasons.append("below_min_price")
        if (
            feature.average_dollar_volume_20d is None
            or feature.average_dollar_volume_20d < self.config.min_average_dollar_volume
        ):
            reasons.append("below_min_adv")
        if not feature.trend_up:
            reasons.append("trend_not_up")
        if feature.atr_pct is None or feature.atr_pct <= 0 or feature.atr_pct > self.config.max_atr_pct:
            reasons.append("atr_out_of_range")
        if feature.relative_strength_60d is None or feature.relative_strength_60d < self.config.min_relative_strength_60d:
            reasons.append("weak_relative_strength")
        return reasons

    def _score_components(self, feature: ScreeningFeatures) -> dict[str, float]:
        rs_score = _bounded(feature.relative_strength_60d, lower=-0.10, upper=0.25)
        momentum_score = _bounded(feature.return_60d, lower=-0.10, upper=0.30)
        volume_score = _bounded((feature.volume_ratio_20d or 1.0) - 1.0, lower=-0.5, upper=2.0)
        atr_score = 1.0 - _bounded(feature.atr_pct, lower=0.0, upper=self.config.max_atr_pct)
        trend_score = 1.0 if feature.trend_up else 0.0
        return {
            "relative_strength": rs_score * 0.35,
            "momentum": momentum_score * 0.20,
            "volume": volume_score * 0.15,
            "volatility": atr_score * 0.15,
            "trend": trend_score * 0.15,
        }


def _bounded(value: float | None, lower: float, upper: float) -> float:
    if value is None or upper <= lower:
        return 0.0
    return max(0.0, min(1.0, (value - lower) / (upper - lower)))
