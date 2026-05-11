from datetime import date

import pytest

from swing_trading_system.screening.universe import UniverseSelector


class FakeMarketRepository:
    def fetch_top_liquid_symbols(self, as_of_date, limit=10):
        return ["A", "B", "C"][:limit]


def test_universe_selector_uses_manual_symbols_and_dedupes() -> None:
    selected = UniverseSelector(FakeMarketRepository()).select(
        as_of_date=date(2026, 1, 1),
        symbols=["A", "A", "B"],
        max_universe=2,
    )

    assert selected.symbols == ("A", "B")


def test_universe_selector_fetches_top_liquid_symbols() -> None:
    selected = UniverseSelector(FakeMarketRepository()).select(as_of_date=date(2026, 1, 1), max_universe=2)

    assert selected.symbols == ("A", "B")


def test_universe_selector_rejects_non_positive_cap() -> None:
    with pytest.raises(ValueError):
        UniverseSelector(FakeMarketRepository()).select(as_of_date=date(2026, 1, 1), max_universe=0)
