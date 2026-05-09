from __future__ import annotations

from decimal import Decimal

from swing_trading_system.domain import MarketBar


def average(values: list[Decimal], window: int) -> Decimal | None:
    if len(values) < window or window <= 0:
        return None
    sample = values[-window:]
    return sum(sample, Decimal("0")) / Decimal(window)


def highest(values: list[Decimal], window: int, *, exclude_last: bool = False) -> Decimal | None:
    if exclude_last:
        values = values[:-1]
    if len(values) < window:
        return None
    return max(values[-window:])


def lowest(values: list[Decimal], window: int) -> Decimal | None:
    if len(values) < window:
        return None
    return min(values[-window:])


def percent_change(values: list[Decimal], lookback: int) -> Decimal | None:
    if len(values) <= lookback:
        return None
    prior = values[-lookback - 1]
    if prior == 0:
        return None
    return values[-1] / prior - Decimal("1")


def atr(bars: list[MarketBar], window: int = 14) -> Decimal | None:
    if len(bars) < window + 1:
        return None
    true_ranges: list[Decimal] = []
    for previous, current in zip(bars[:-1], bars[1:]):
        if current.high is None or current.low is None or previous.close is None:
            continue
        true_ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    if len(true_ranges) < window:
        return None
    return sum(true_ranges[-window:], Decimal("0")) / Decimal(window)


def volume_ratio(volumes: list[Decimal], window: int = 20) -> Decimal | None:
    if len(volumes) < window:
        return None
    avg_volume = sum(volumes[-window:], Decimal("0")) / Decimal(window)
    if avg_volume == 0:
        return None
    return volumes[-1] / avg_volume
