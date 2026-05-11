"""Deterministic technical indicator helpers for EOD screening."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def last(values: Sequence[float | None]) -> float | None:
    return values[-1] if values else None


def simple_moving_average(values: Sequence[float | None], window: int) -> float | None:
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


def average(values: Sequence[float | None], window: int) -> float | None:
    return simple_moving_average(values, window)


def high(values: Sequence[float | None], window: int, include_current: bool = True) -> float | None:
    series = values if include_current else values[:-1]
    if window <= 0 or len(series) < window:
        return None
    window_values = [value for value in series[-window:] if value is not None]
    if len(window_values) < window:
        return None
    return max(window_values)


def low(values: Sequence[float | None], window: int, include_current: bool = True) -> float | None:
    series = values if include_current else values[:-1]
    if window <= 0 or len(series) < window:
        return None
    window_values = [value for value in series[-window:] if value is not None]
    if len(window_values) < window:
        return None
    return min(window_values)


def average_true_range(rows: Sequence[dict[str, Any]], window: int = 14) -> float | None:
    if window <= 0 or len(rows) < window + 1:
        return None
    true_ranges: list[float] = []
    for idx in range(1, len(rows)):
        high_value = as_float(rows[idx].get("high"))
        low_value = as_float(rows[idx].get("low"))
        previous_close = as_float(rows[idx - 1].get("close"))
        if high_value is None or low_value is None or previous_close is None:
            continue
        true_ranges.append(
            max(
                high_value - low_value,
                abs(high_value - previous_close),
                abs(low_value - previous_close),
            )
        )
    if len(true_ranges) < window:
        return None
    return sum(true_ranges[-window:]) / window


def relative_strength(symbol_return: float | None, benchmark_return: float | None) -> float | None:
    if symbol_return is None or benchmark_return is None:
        return None
    return symbol_return - benchmark_return
