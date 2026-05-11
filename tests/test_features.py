from datetime import date, timedelta

from swing_trading_system.screening.features import calculate_features


def make_rows(days: int = 221, close_start: float = 100.0, volume: float = 1_000_000.0):
    start = date(2025, 1, 1)
    rows = []
    for idx in range(days):
        close = close_start + idx
        rows.append(
            {
                "symbol": "AAA",
                "trade_date": start + timedelta(days=idx),
                "open": close - 0.5,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": volume,
                "dollar_volume": close * volume,
            }
        )
    return rows


def test_calculate_features_is_json_serializable_and_pit_safe() -> None:
    rows = make_rows()
    as_of = rows[-2]["trade_date"]
    future = {**rows[-1], "close": 9999.0, "trade_date": as_of + timedelta(days=1)}

    features = calculate_features("AAA", as_of, rows[:-1] + [future], benchmark_rows=rows[:-1])
    payload = features.to_dict()

    assert features.close == rows[-2]["close"]
    assert features.history_days == 220
    assert features.trend_up is True
    assert payload["as_of_date"] == as_of.isoformat()
    assert payload["close"] != 9999.0
