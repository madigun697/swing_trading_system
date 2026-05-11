from swing_trading_system.screening.indicators import average_true_range, rolling_return, simple_moving_average


def test_simple_moving_average_and_rolling_return() -> None:
    values = [1.0, 2.0, 3.0, 4.0]

    assert simple_moving_average(values, 3) == 3.0
    assert rolling_return(values, 2) == 1.0
    assert simple_moving_average(values, 5) is None


def test_average_true_range_uses_only_ordered_rows() -> None:
    rows = [
        {"high": 10, "low": 8, "close": 9},
        {"high": 12, "low": 9, "close": 11},
        {"high": 13, "low": 10, "close": 12},
    ]

    assert average_true_range(rows, 2) == 3.0
