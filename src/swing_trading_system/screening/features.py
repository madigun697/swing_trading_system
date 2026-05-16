"""Screening feature contract and calculation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
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
    sector: str | None = None
    industry: str | None = None
    market_cap: float | None = None
    benchmark_return_20d: float | None = None
    benchmark_above_ma50: bool | None = None
    benchmark_above_ma200: bool | None = None
    market_regime: dict[str, Any] | None = None
    quality_score: float | None = None
    revenue_yoy: float | None = None
    net_income_yoy: float | None = None
    ocf_margin: float | None = None
    recent_filing_form: str | None = None
    recent_filing_age_days: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["as_of_date"] = self.as_of_date.isoformat()
        return payload


def calculate_features(
    symbol: str,
    as_of_date: date,
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    benchmark_rows: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    market_regime: dict[str, Any] | None = None,
    security_metadata: dict[str, Any] | None = None,
    fundamental_rows: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    filing_rows: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
) -> ScreeningFeatures:
    safe_rows = [
        row
        for row in rows
        if row.get("trade_date") is not None and row["trade_date"] <= as_of_date
    ]
    ordered = sorted(safe_rows, key=lambda row: row["trade_date"])
    closes = [as_float(row.get("close")) for row in ordered]
    highs = [as_float(row.get("high")) for row in ordered]
    lows = [as_float(row.get("low")) for row in ordered]
    volumes = [as_float(row.get("volume")) for row in ordered]
    dollar_volumes = [_dollar_volume(row) for row in ordered]

    benchmark_safe_rows = [
        row
        for row in benchmark_rows
        if row.get("trade_date") is not None and row["trade_date"] <= as_of_date
    ]
    benchmark_closes = [
        as_float(row.get("close"))
        for row in sorted(benchmark_safe_rows, key=lambda row: row["trade_date"])
    ]
    benchmark_close = last(benchmark_closes)
    benchmark_ma50 = simple_moving_average(benchmark_closes, 50)
    benchmark_ma200 = simple_moving_average(benchmark_closes, 200)

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

    quality = _quality_features(as_of_date, fundamental_rows)
    filing = _recent_filing(as_of_date, filing_rows)
    security = security_metadata or {}

    return ScreeningFeatures(
        symbol=symbol,
        as_of_date=as_of_date,
        close=close,
        volume=volume,
        dollar_volume=dollar_volume,
        return_20d=return_20d,
        return_60d=return_60d,
        return_120d=rolling_return(closes, 120),
        relative_strength_60d=relative_strength(
            return_60d, rolling_return(benchmark_closes, 60)
        ),
        average_dollar_volume_20d=average(dollar_volumes, 20),
        atr_14=atr_14,
        atr_pct=(atr_14 / close)
        if atr_14 is not None and close not in (None, 0)
        else None,
        volume_ratio_20d=(volume / average_volume_20d)
        if volume is not None and average_volume_20d not in (None, 0)
        else None,
        ma_20=ma_20,
        ma_50=ma_50,
        ma_200=ma_200,
        trend_up=bool(close and ma_50 and ma_200 and close > ma_50 > ma_200),
        recent_high_20=high(highs, 20),
        previous_high_20=high(highs, 20, include_current=False),
        recent_low_20=low(lows, 20),
        history_days=len(ordered),
        sector=_as_optional_str(security.get("sector")),
        industry=_as_optional_str(security.get("industry")),
        market_cap=as_float(security.get("market_cap")),
        benchmark_return_20d=rolling_return(benchmark_closes, 20),
        benchmark_above_ma50=(benchmark_close > benchmark_ma50)
        if benchmark_close is not None and benchmark_ma50 is not None
        else None,
        benchmark_above_ma200=(benchmark_close > benchmark_ma200)
        if benchmark_close is not None and benchmark_ma200 is not None
        else None,
        market_regime=market_regime,
        quality_score=quality["quality_score"],
        revenue_yoy=quality["revenue_yoy"],
        net_income_yoy=quality["net_income_yoy"],
        ocf_margin=quality["ocf_margin"],
        recent_filing_form=filing["recent_filing_form"],
        recent_filing_age_days=filing["recent_filing_age_days"],
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


def _quality_features(
    as_of_date: date, rows: list[dict[str, Any]] | tuple[dict[str, Any], ...]
) -> dict[str, float | None]:
    point_in_time = [
        row
        for row in rows
        if _available_date(row.get("available_at")) is not None
        and _available_date(row.get("available_at")) <= as_of_date
    ]
    ordered = sorted(
        point_in_time,
        key=lambda row: (
            row.get("period_end") or date.min,
            _available_datetime(row.get("available_at")) or datetime.min,
        ),
    )
    latest = ordered[-1] if ordered else None
    previous = (
        _previous_comparable_fundamental(ordered, latest)
        if latest is not None
        else None
    )
    if latest is None:
        return {
            "quality_score": None,
            "revenue_yoy": None,
            "net_income_yoy": None,
            "ocf_margin": None,
        }

    revenue = as_float(latest.get("revenue"))
    net_income = as_float(latest.get("net_income"))
    operating_cash_flow = as_float(latest.get("operating_cash_flow"))
    revenue_yoy = _growth(
        revenue, as_float(previous.get("revenue")) if previous else None
    )
    net_income_yoy = _growth(
        net_income, as_float(previous.get("net_income")) if previous else None
    )
    ocf_margin = (
        (operating_cash_flow / revenue)
        if operating_cash_flow is not None and revenue not in (None, 0)
        else None
    )
    quality_score = _quality_score(revenue_yoy, net_income_yoy, ocf_margin)
    return {
        "quality_score": quality_score,
        "revenue_yoy": revenue_yoy,
        "net_income_yoy": net_income_yoy,
        "ocf_margin": ocf_margin,
    }


def _previous_comparable_fundamental(
    ordered: list[dict[str, Any]], latest: dict[str, Any]
) -> dict[str, Any] | None:
    latest_period = latest.get("period_end")
    if not isinstance(latest_period, date):
        return ordered[-2] if len(ordered) > 1 else None
    comparable = [
        row
        for row in ordered[:-1]
        if isinstance(row.get("period_end"), date)
        and (latest_period - row["period_end"]).days >= 300
    ]
    return comparable[-1] if comparable else (ordered[-2] if len(ordered) > 1 else None)


def _recent_filing(
    as_of_date: date, rows: list[dict[str, Any]] | tuple[dict[str, Any], ...]
) -> dict[str, str | int | None]:
    point_in_time = [
        row
        for row in rows
        if _available_date(row.get("available_at")) is not None
        and _available_date(row.get("available_at")) <= as_of_date
    ]
    ordered = sorted(
        point_in_time,
        key=lambda row: (
            row.get("filing_date") or date.min,
            _available_datetime(row.get("available_at")) or datetime.min,
        ),
    )
    latest = ordered[-1] if ordered else None
    filing_date = latest.get("filing_date") if latest else None
    return {
        "recent_filing_form": _as_optional_str(latest.get("form")) if latest else None,
        "recent_filing_age_days": (as_of_date - filing_date).days
        if isinstance(filing_date, date)
        else None,
    }


def _quality_score(
    revenue_yoy: float | None, net_income_yoy: float | None, ocf_margin: float | None
) -> float | None:
    if revenue_yoy is None and net_income_yoy is None and ocf_margin is None:
        return None
    revenue_component = _bounded_growth(revenue_yoy, -0.10, 0.30) * 0.35
    income_component = _bounded_growth(net_income_yoy, -0.25, 0.50) * 0.35
    cash_component = _bounded_growth(ocf_margin, -0.05, 0.25) * 0.30
    return round(revenue_component + income_component + cash_component, 6)


def _growth(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return (current - previous) / abs(previous)


def _bounded_growth(value: float | None, lower: float, upper: float) -> float:
    if value is None or upper <= lower:
        return 0.0
    return max(0.0, min(1.0, (value - lower) / (upper - lower)))


def _available_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _available_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    return None


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
