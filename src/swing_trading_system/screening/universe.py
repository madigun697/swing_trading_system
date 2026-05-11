"""Universe selection helpers for Sprint 2 screening."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol


class UniverseReader(Protocol):
    def fetch_top_liquid_symbols(self, as_of_date: date, limit: int = 10) -> list[str]:
        ...


@dataclass(frozen=True)
class UniverseSelection:
    symbols: tuple[str, ...]
    as_of_date: date
    universe_name: str
    details: dict[str, object] = field(default_factory=dict)


class UniverseSelector:
    def __init__(self, market_repository: UniverseReader) -> None:
        self.market_repository = market_repository

    def select(
        self,
        as_of_date: date,
        symbols: list[str] | None = None,
        max_universe: int = 50,
        universe_name: str = "top_liquid",
    ) -> UniverseSelection:
        if max_universe <= 0:
            raise ValueError("max_universe must be positive")
        selected = symbols if symbols else self.market_repository.fetch_top_liquid_symbols(as_of_date, max_universe)
        deduped = tuple(dict.fromkeys(selected))[:max_universe]
        return UniverseSelection(
            symbols=deduped,
            as_of_date=as_of_date,
            universe_name=universe_name,
            details={"requested_symbols": symbols or [], "max_universe": max_universe},
        )
