"""Market regime classification and policy rules."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from enum import StrEnum
from typing import Any, Mapping, Sequence

class MarketRegimeId(StrEnum):
    R1_STRONG_BULL = "R1_STRONG_BULL"
    R2_VOLATILE_BULL = "R2_VOLATILE_BULL"
    R3_SIDEWAYS = "R3_SIDEWAYS"
    R4_EARLY_BEAR = "R4_EARLY_BEAR"
    R5_DEEP_BEAR = "R5_DEEP_BEAR"


@dataclass(frozen=True)
class RegimeRule:
    strategy_weights: Mapping[str, float]
    max_gross_exposure_pct: float
    new_entries_allowed: bool
    max_positions: int | None = None
    max_portfolio_risk_pct: float | None = None
    risk_off_exit: bool = False


@dataclass(frozen=True)
class RegimePolicy:
    profile: str
    require_vix: bool
    rules: Mapping[MarketRegimeId, RegimeRule]

    def rule_for(self, regime_id: str | MarketRegimeId | None) -> RegimeRule | None:
        if regime_id is None:
            return None
        try:
            return self.rules[MarketRegimeId(str(regime_id))]
        except (KeyError, ValueError):
            return None

    def position_multiplier(
        self, regime_id: str | MarketRegimeId | None, strategy: str
    ) -> float | None:
        rule = self.rule_for(regime_id)
        if rule is None:
            return None
        if not rule.new_entries_allowed:
            return 0.0
        weight = max(0.0, float(rule.strategy_weights.get(strategy, 0.0)))
        return round(max(0.0, rule.max_gross_exposure_pct) * weight, 6)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "require_vix": self.require_vix,
            "rules": {
                regime_id.value: {
                    "strategy_weights": dict(rule.strategy_weights),
                    "max_gross_exposure_pct": rule.max_gross_exposure_pct,
                    "new_entries_allowed": rule.new_entries_allowed,
                    "max_positions": rule.max_positions,
                    "max_portfolio_risk_pct": rule.max_portfolio_risk_pct,
                    "risk_off_exit": rule.risk_off_exit,
                }
                for regime_id, rule in self.rules.items()
            },
        }


@dataclass(frozen=True)
class MarketRegimeSnapshot:
    regime_id: MarketRegimeId
    as_of_date: date
    benchmark_close: float | None
    benchmark_ma50: float | None
    benchmark_ma200: float | None
    benchmark_return_20d: float | None
    benchmark_return_60d: float | None
    vix_value: float | None
    vix_observation_date: date | None
    vix_required: bool
    confidence: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["regime_id"] = self.regime_id.value
        payload["as_of_date"] = self.as_of_date.isoformat()
        payload["vix_observation_date"] = (
            self.vix_observation_date.isoformat()
            if self.vix_observation_date is not None
            else None
        )
        return payload


def default_regime_policy(
    require_vix: bool = True, profile: str = "aggressive"
) -> RegimePolicy:
    return RegimePolicy(
        profile=profile,
        require_vix=require_vix,
        rules={
            MarketRegimeId.R1_STRONG_BULL: RegimeRule(
                strategy_weights={
                    "breakout": 0.55,
                    "quality_momentum": 0.45,
                    "pullback": 0.10,
                },
                max_gross_exposure_pct=1.10,
                new_entries_allowed=True,
                max_positions=15,
                max_portfolio_risk_pct=0.06,
            ),
            MarketRegimeId.R2_VOLATILE_BULL: RegimeRule(
                strategy_weights={
                    "pullback": 0.65,
                    "breakout": 0.20,
                    "quality_momentum": 0.15,
                },
                max_gross_exposure_pct=0.80,
                new_entries_allowed=True,
                max_positions=10,
                max_portfolio_risk_pct=0.035,
            ),
            MarketRegimeId.R3_SIDEWAYS: RegimeRule(
                strategy_weights={
                    "pullback": 1.00,
                },
                max_gross_exposure_pct=0.25,
                new_entries_allowed=True,
                max_positions=5,
                max_portfolio_risk_pct=0.015,
            ),
            MarketRegimeId.R4_EARLY_BEAR: RegimeRule(
                strategy_weights={},
                max_gross_exposure_pct=0.0,
                new_entries_allowed=False,
                max_positions=0,
                max_portfolio_risk_pct=0.0,
                risk_off_exit=True,
            ),
            MarketRegimeId.R5_DEEP_BEAR: RegimeRule(
                strategy_weights={},
                max_gross_exposure_pct=0.0,
                new_entries_allowed=False,
                max_positions=0,
                max_portfolio_risk_pct=0.0,
                risk_off_exit=True,
            ),
        },
    )


def regime_policy_from_json(
    policy_json: str | None,
    require_vix: bool = True,
    profile: str = "aggressive",
) -> RegimePolicy:
    if not policy_json:
        return default_regime_policy(require_vix=require_vix, profile=profile)
    raw = json.loads(policy_json)
    if not isinstance(raw, dict):
        raise ValueError("regime policy JSON must be an object")
    base = default_regime_policy(require_vix=require_vix, profile=profile)
    policy_profile = str(raw.get("profile") or base.profile)
    rules_payload = raw.get("rules", raw)
    if not isinstance(rules_payload, dict):
        raise ValueError("regime policy rules must be an object")
    rules = dict(base.rules)
    for key, value in rules_payload.items():
        if key in {"profile", "require_vix"}:
            continue
        regime_id = MarketRegimeId(str(key))
        if not isinstance(value, dict):
            raise ValueError(f"regime rule for {key} must be an object")
        current = rules[regime_id]
        strategy_weights = value.get("strategy_weights", current.strategy_weights)
        if not isinstance(strategy_weights, dict):
            raise ValueError(f"strategy_weights for {key} must be an object")
        rules[regime_id] = RegimeRule(
            strategy_weights={
                str(strategy): float(weight)
                for strategy, weight in strategy_weights.items()
            },
            max_gross_exposure_pct=float(
                value.get("max_gross_exposure_pct", current.max_gross_exposure_pct)
            ),
            new_entries_allowed=bool(
                value.get("new_entries_allowed", current.new_entries_allowed)
            ),
            max_positions=(
                int(value["max_positions"])
                if value.get("max_positions") is not None
                else current.max_positions
            ),
            max_portfolio_risk_pct=(
                float(value["max_portfolio_risk_pct"])
                if value.get("max_portfolio_risk_pct") is not None
                else current.max_portfolio_risk_pct
            ),
            risk_off_exit=bool(value.get("risk_off_exit", current.risk_off_exit)),
        )
    return RegimePolicy(profile=policy_profile, require_vix=require_vix, rules=rules)


def classify_market_regime(
    benchmark_rows: Sequence[Mapping[str, Any]],
    vix_rows: Sequence[Mapping[str, Any]],
    as_of_date: date,
    require_vix: bool = True,
) -> MarketRegimeSnapshot:
    closes = [
        _row_value(row, "close", "value")
        for row in _point_in_time_rows(benchmark_rows, as_of_date)
    ]
    benchmark_close = last(closes)
    ma50 = simple_moving_average(closes, 50)
    ma200 = simple_moving_average(closes, 200)
    return_20d = rolling_return(closes, 20)
    return_60d = rolling_return(closes, 60)
    vix_row = _latest_vix_row(vix_rows, as_of_date)
    vix_value = _row_value(vix_row, "value") if vix_row is not None else None
    vix_date = _row_date(vix_row) if vix_row is not None else None
    confidence = "high" if vix_value is not None else "low"

    below_ma200 = (
        benchmark_close is not None and ma200 is not None and benchmark_close < ma200
    )
    above_ma200 = (
        benchmark_close is not None and ma200 is not None and benchmark_close > ma200
    )
    strong_uptrend = (
        benchmark_close is not None
        and ma50 is not None
        and ma200 is not None
        and benchmark_close > ma50 > ma200
    )
    below_ma50 = (
        benchmark_close is not None and ma50 is not None and benchmark_close < ma50
    )

    if (below_ma200 and (return_60d or 0.0) <= -0.15) or (
        vix_value is not None and vix_value >= 40
    ):
        regime_id = MarketRegimeId.R5_DEEP_BEAR
        reason = "deep_bear_spy_trend_or_vix"
    elif below_ma200 or (return_20d or 0.0) <= -0.08 or (
        vix_value is not None and vix_value >= 30
    ):
        regime_id = MarketRegimeId.R4_EARLY_BEAR
        reason = "early_bear_spy_trend_or_vix"
    elif strong_uptrend and (return_20d or 0.0) >= 0 and (
        vix_value is not None and vix_value <= 18
    ):
        regime_id = MarketRegimeId.R1_STRONG_BULL
        reason = "strong_bull_low_vix_uptrend"
    elif above_ma200 and (
        below_ma50
        or (return_20d is not None and return_20d <= -0.03)
        or (vix_value is not None and vix_value >= 25)
    ):
        regime_id = MarketRegimeId.R3_SIDEWAYS
        reason = "sideways_risk_control_weak_bull"
    elif above_ma200 and (vix_value is None or vix_value < 30):
        regime_id = MarketRegimeId.R2_VOLATILE_BULL
        reason = "volatile_bull_above_ma200"
    else:
        regime_id = MarketRegimeId.R3_SIDEWAYS
        reason = "sideways_default"

    return MarketRegimeSnapshot(
        regime_id=regime_id,
        as_of_date=as_of_date,
        benchmark_close=benchmark_close,
        benchmark_ma50=ma50,
        benchmark_ma200=ma200,
        benchmark_return_20d=return_20d,
        benchmark_return_60d=return_60d,
        vix_value=vix_value,
        vix_observation_date=vix_date,
        vix_required=require_vix,
        confidence=confidence,
        reason=reason,
    )


def _point_in_time_rows(
    rows: Sequence[Mapping[str, Any]], as_of_date: date
) -> list[Mapping[str, Any]]:
    return sorted(
        [
            row
            for row in rows
            if _row_date(row) is not None and _row_date(row) <= as_of_date
        ],
        key=lambda row: _row_date(row) or date.min,
    )


def _latest_vix_row(
    rows: Sequence[Mapping[str, Any]], as_of_date: date
) -> Mapping[str, Any] | None:
    point_in_time = _point_in_time_rows(rows, as_of_date)
    return point_in_time[-1] if point_in_time else None


def _row_value(row: Mapping[str, Any] | None, *keys: str) -> float | None:
    if row is None:
        return None
    for key in keys:
        value = _as_float(row.get(key))
        if value is not None:
            return value
    return None


def _row_date(row: Mapping[str, Any] | None) -> date | None:
    if row is None:
        return None
    value = row.get("trade_date") or row.get("observation_date")
    return value if isinstance(value, date) else None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def last(values: Sequence[float | None]) -> float | None:
    return values[-1] if values else None


def simple_moving_average(
    values: Sequence[float | None], window: int
) -> float | None:
    if window <= 0 or len(values) < window:
        return None
    window_values = [value for value in values[-window:] if value is not None]
    if len(window_values) < window:
        return None
    return sum(window_values) / window


def rolling_return(values: Sequence[float | None], window: int) -> float | None:
    if window <= 0 or len(values) <= window:
        return None
    start = values[-window - 1]
    end = values[-1]
    if start in (None, 0) or end is None:
        return None
    return (end / start) - 1.0
