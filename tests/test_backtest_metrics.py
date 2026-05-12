from datetime import date

from swing_trading_system.backtest.metrics import calculate_metrics
from swing_trading_system.backtest.models import BacktestTrade, EquityCurvePoint


def trade(pnl: float, symbol="AAA") -> BacktestTrade:
    return BacktestTrade("r", 1, symbol, "pullback", date(2026, 1, 1), date(2026, 1, 2), 100, 101, 1, pnl, "target")


def test_metrics_handles_wins_losses_and_contributions() -> None:
    curve = [EquityCurvePoint("r", date(2026, 1, 2), 101_000, 0), EquityCurvePoint("r", date(2026, 1, 3), 100_500, -0.0049505)]
    metrics = calculate_metrics([trade(1000), trade(-500, "BBB")], curve, 100_000)

    assert metrics["trade_count"] == 2
    assert metrics["total_return"] == 0.005
    assert metrics["win_rate"] == 0.5
    assert metrics["profit_factor"] == 2.0
    assert metrics["symbol_contribution"] == {"AAA": 1000, "BBB": -500}


def test_metrics_handles_empty_trades() -> None:
    metrics = calculate_metrics([], [], 100_000)

    assert metrics["trade_count"] == 0
    assert metrics["profit_factor"] == 0.0
    assert metrics["expectancy"] == 0.0
