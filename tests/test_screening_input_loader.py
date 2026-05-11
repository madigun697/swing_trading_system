from datetime import date

import pytest

from swing_trading_system.screening.input_loader import ScreeningInputLoader


class FakeMarketRepository:
    def __init__(self) -> None:
        self.calls = []

    def fetch_daily_prices(self, symbol, start_date=None, end_date=None, limit=500):
        self.calls.append({"symbol": symbol, "start_date": start_date, "end_date": end_date, "limit": limit})
        return [
            {"symbol": symbol, "trade_date": date(2026, 1, 3), "close": 103},
            {"symbol": symbol, "trade_date": date(2026, 1, 1), "close": 101},
            {"symbol": symbol, "trade_date": date(2026, 1, 4), "close": 104},
            {"symbol": symbol, "trade_date": date(2026, 1, 2), "close": 102},
        ]


def test_loader_filters_future_rows_and_orders_ascending() -> None:
    repo = FakeMarketRepository()
    loader = ScreeningInputLoader(repo)

    loaded = loader.load_symbol("SPY", as_of_date=date(2026, 1, 2), lookback_days=10)

    assert [row["trade_date"] for row in loaded.rows] == [date(2026, 1, 1), date(2026, 1, 2)]
    assert loaded.latest_row["close"] == 102
    assert repo.calls[0]["end_date"] == date(2026, 1, 2)


def test_loader_rejects_non_positive_lookback() -> None:
    loader = ScreeningInputLoader(FakeMarketRepository())

    with pytest.raises(ValueError, match="lookback_days"):
        loader.load_symbol("SPY", as_of_date=date(2026, 1, 2), lookback_days=0)
