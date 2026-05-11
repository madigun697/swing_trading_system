"""Screening feature contract and calculation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from swing_trading_system.screening.indicators import (
    as_float,
    average,
    average_true_range,
    high,
    last,
    low,
    relative_strength,
    rolling_return,
    simple_moving_average,
)


@dataclass(frozen=True)
class ScreeningFeatures:
    symbol: str
    as_of_date: date
    close: float | None
    volume: float | None
    dollar_volume: float | None
    return_20d: float | None
    return_60d: float | None
    return_120d: float | None
    relative_strength_60d: float | None
    average_dollar_volume_20d: float | None
    atr_14: float | None
    atr_pct: float | None
    volume_ratio_20d: float | None
    ma_20: float | None
    ma_50: float | None
    ma_200: float | None
    trend_up: bool
    recent_high_20: float | None
    previous_high_20: float | None
    recent_low_20: float | None
    history_days: int

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["as_of_date"] = self.as_of_date.isoformat()
        return payload


def calculate_features(
    symbol: str,
    as_of_date: date,
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    benchmark_rows: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
) -> ScreeningFeatures:
    safe_rows = [row for row in rows if row.get("trade_date") is not None and row["trade_date"] <= as_of_date]
    ordered = sorted(safe_rows, key=lambda row: row["trade_date"])
    closes = [as_float(row.get("close")) for row in ordered]
    highs = [as_float(row.get("high")) for row in ordered]
    lows = [as_float(row.get("low")) for row in ordered]
    volumes = [as_float(row.get("volume")) for row in ordered]
    dollar_volumes = [_dollar_volume(row) for row in ordered]

    benchmark_safe_rows = [row for row in benchmark_rows if row.get("trade_date") is not None and row["trade_date"] <= as_of_date]
    benchmark_closes = [as_float(row.get("close")) for row in sorted(benchmark_safe_rows, key=lambda row: row["trade_date"])]

    close = last(closes)
    volume = last(volumes)
    dollar_volume = last(dollar_volumes)
    return_20d = rolling_return(closes, 20)
    return_60d = rolling_return(closes, 60)
    atr_14 = average_true_range(ordered, 14)
    ma_20 = simple_moving_average(closes, 20)
    ma_50 = simple_moving_average(closes, 50)
    ma_200 = simple_moving_average(closes, 200)
    average_volume_20d = average(volumes, 20)

    return ScreeningFeatures(
        symbol=symbol,
        as_of_date=as_of_date,
        close=close,
        volume=volume,
        dollar_volume=dollar_volume,
        return_20d=return_20d,
        return_60d=return_60d,
        return_120d=rolling_return(closes, 120),
        relative_strength_60d=relative_strength(return_60d, rolling_return(benchmark_closes, 60)),
        average_dollar_volume_20d=average(dollar_volumes, 20),
        atr_14=atr_14,
        atr_pct=(atr_14 / close) if atr_14 is not None and close not in (None, 0) else None,
        volume_ratio_20d=(volume / average_volume_20d) if volume is not None and average_volume_20d not in (None, 0) else None,
        ma_20=ma_20,
        ma_50=ma_50,
        ma_200=ma_200,
        trend_up=bool(close and ma_50 and ma_200 and close > ma_50 > ma_200),
        recent_high_20=high(highs, 20),
        previous_high_20=high(highs, 20, include_current=False),
        recent_low_20=low(lows, 20),
        history_days=len(ordered),
    )


def _dollar_volume(row: dict[str, Any]) -> float | None:
    explicit = as_float(row.get("dollar_volume"))
    if explicit is not None:
        return explicit
    close = as_float(row.get("close"))
    volume = as_float(row.get("volume"))
    if close is None or volume is None:
        return None
    return close * volume
