"""Common strategy contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Protocol

from swing_trading_system.screening.screener import ScreeningCandidate


@dataclass(frozen=True)
class StrategyContext:
    as_of_date: date
    account_equity: float = 100_000.0
    risk_per_trade_pct: float = 0.01
    max_position_pct: float = 0.125

    @property
    def risk_amount(self) -> float:
        return self.account_equity * self.risk_per_trade_pct


@dataclass(frozen=True)
class StrategySignal:
    symbol: str
    signal_date: date
    strategy: str
    entry_price: float
    stop_price: float
    target_price: float
    risk_per_share: float
    position_size: float
    score: float
    reason: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_repository_kwargs(self, screening_run_id: int) -> dict[str, Any]:
        return {
            "screening_run_id": screening_run_id,
            "symbol": self.symbol,
            "signal_date": self.signal_date,
            "strategy": self.strategy,
            "entry_price": self.entry_price,
            "stop_price": self.stop_price,
            "target_price": self.target_price,
            "risk_per_share": self.risk_per_share,
            "position_size": self.position_size,
            "score": self.score,
            "reason": self.reason,
            "details": self.details,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["signal_date"] = self.signal_date.isoformat()
        return payload


class Strategy(Protocol):
    name: str

    def generate(self, candidate: ScreeningCandidate, context: StrategyContext) -> StrategySignal | None:
        ...


def calculate_position_size(entry_price: float, stop_price: float, context: StrategyContext) -> tuple[float, float]:
    risk_per_share = entry_price - stop_price
    if risk_per_share <= 0:
        return 0.0, 0.0
    risk_limited_size = context.risk_amount / risk_per_share
    max_position_value = context.account_equity * context.max_position_pct
    value_limited_size = max_position_value / entry_price if entry_price > 0 else 0.0
    return risk_per_share, max(0.0, min(risk_limited_size, value_limited_size))
