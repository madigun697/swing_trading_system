from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from swing_trading_system.domain import FeatureSnapshot, ScreenCandidate


class BaseSwingStrategy(ABC):
    strategy_id: str
    display_name: str

    @abstractmethod
    def evaluate(self, snapshot: FeatureSnapshot) -> ScreenCandidate | None:
        raise NotImplementedError

    def _clamp_decimal(self, value: Decimal, floor: str) -> Decimal:
        return value if value > Decimal(floor) else Decimal(floor)
