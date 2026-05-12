"""Backtest domain models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class BacktestConfig:
    initial_equity: float = 100_000.0
    fee_bps: float = 2.0
    slippage_bps: float = 10.0
    max_hold_days: int = 20
    max_positions: int = 5
    max_gross_exposure_pct: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BacktestSignal:
    id: int
    symbol: str
    signal_date: date
    strategy: str
    entry_price: float
    stop_price: float
    target_price: float
    risk_per_share: float
    position_size: float
    score: float | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "BacktestSignal | None":
        required = ["id", "symbol", "signal_date", "strategy", "entry_price", "stop_price", "target_price", "risk_per_share", "position_size"]
        if any(row.get(key) is None for key in required):
            return None
        return cls(
            id=int(row["id"]),
            symbol=str(row["symbol"]),
            signal_date=row["signal_date"],
            strategy=str(row["strategy"]),
            entry_price=float(row["entry_price"]),
            stop_price=float(row["stop_price"]),
            target_price=float(row["target_price"]),
            risk_per_share=float(row["risk_per_share"]),
            position_size=float(row["position_size"]),
            score=as_float(row.get("score")),
            details=row.get("details") or {},
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["signal_date"] = self.signal_date.isoformat()
        return payload


@dataclass(frozen=True)
class PriceBar:
    symbol: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "PriceBar | None":
        open_price = as_float(row.get("open"))
        high = as_float(row.get("high"))
        low = as_float(row.get("low"))
        close = as_float(row.get("close"))
        if row.get("trade_date") is None or open_price is None or high is None or low is None or close is None:
            return None
        return cls(
            symbol=str(row.get("symbol")),
            trade_date=row["trade_date"],
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=as_float(row.get("volume")),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["trade_date"] = self.trade_date.isoformat()
        return payload


@dataclass(frozen=True)
class BacktestTrade:
    run_id: str
    signal_id: int
    symbol: str
    strategy: str
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    exit_reason: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["entry_date"] = self.entry_date.isoformat()
        payload["exit_date"] = self.exit_date.isoformat()
        return payload


@dataclass(frozen=True)
class EquityCurvePoint:
    run_id: str
    equity_date: date
    equity: float
    drawdown: float
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["equity_date"] = self.equity_date.isoformat()
        return payload


@dataclass(frozen=True)
class BacktestRejection:
    signal_id: int
    symbol: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BacktestResult:
    run_id: str
    config: BacktestConfig
    trades: tuple[BacktestTrade, ...]
    equity_curve: tuple[EquityCurvePoint, ...]
    rejections: tuple[BacktestRejection, ...]
    metrics: dict[str, Any]
    signal_count: int = 0
    signal_start_date: date | None = None
    signal_end_date: date | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "config": self.config.to_dict(),
            "trades": [trade.to_dict() for trade in self.trades],
            "equity_curve": [point.to_dict() for point in self.equity_curve],
            "rejections": [rejection.to_dict() for rejection in self.rejections],
            "metrics": self.metrics,
            "signal_count": self.signal_count,
            "signal_start_date": self.signal_start_date.isoformat() if self.signal_start_date else None,
            "signal_end_date": self.signal_end_date.isoformat() if self.signal_end_date else None,
        }
