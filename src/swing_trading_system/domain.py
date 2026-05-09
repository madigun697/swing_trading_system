from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class ReadinessStatus:
    ok: bool
    code: str
    detail: str
    checked_relations: tuple[str, ...] = ()


@dataclass(frozen=True)
class MarketBar:
    symbol: str
    trade_date: date
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    volume: Decimal | None
    dollar_volume: Decimal | None
    sector: str | None = None
    industry: str | None = None


@dataclass(frozen=True)
class FeatureSnapshot:
    symbol: str
    trade_date: date
    sector: str | None
    industry: str | None
    close_price: Decimal
    adv20: Decimal
    atr14: Decimal
    sma20: Decimal
    sma50: Decimal
    sma200: Decimal
    volume_ratio20: Decimal
    breakout_20d: Decimal
    low_20d: Decimal
    return_5d: Decimal
    return_20d: Decimal
    return_60d: Decimal
    relative_strength_20d: Decimal
    relative_strength_60d: Decimal


@dataclass(frozen=True)
class ScreenCandidate:
    strategy_id: str
    signal_date: date
    symbol: str
    sector: str | None
    industry: str | None
    close_price: Decimal
    adv20: Decimal
    atr14: Decimal
    relative_strength_20d: Decimal
    relative_strength_60d: Decimal
    volume_ratio20: Decimal
    breakout_level: Decimal
    pullback_distance_pct: Decimal
    score: Decimal
    risk_per_share: Decimal
    stop_price: Decimal
    target_price: Decimal
    reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TradePlan:
    strategy_id: str
    signal_date: date
    symbol: str
    side: str
    quantity: Decimal
    entry_price: Decimal
    stop_price: Decimal
    target_price: Decimal
    risk_per_share: Decimal
    score: Decimal
    sector: str | None
    notes: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AlertEvent:
    alert_type: str
    symbol: str | None
    severity: str
    message: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class BacktestTrade:
    trade_id: int
    strategy_id: str
    symbol: str
    entry_date: date
    exit_date: date
    quantity: Decimal
    entry_price: Decimal
    exit_price: Decimal
    pnl: Decimal
    return_pct: Decimal
    exit_reason: str
    hold_days: int


@dataclass(frozen=True)
class EquityPoint:
    trade_date: date
    cash: Decimal
    market_value: Decimal
    total_equity: Decimal
    drawdown: Decimal


@dataclass(frozen=True)
class BacktestResult:
    strategy_id: str
    start_date: date
    end_date: date
    initial_capital: Decimal
    final_equity: Decimal
    total_return: Decimal
    cagr: Decimal
    max_drawdown: Decimal
    sharpe_ratio: Decimal
    win_rate: Decimal
    trades: list[BacktestTrade]
    equity_curve: list[EquityPoint]
    params: dict[str, Any]


@dataclass(frozen=True)
class ScreenRunRecord:
    screen_run_id: int
    strategy_id: str
    signal_date: date
    candidate_count: int
