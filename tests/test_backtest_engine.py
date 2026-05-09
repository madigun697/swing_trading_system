from datetime import date, timedelta
from decimal import Decimal

from swing_trading_system.backtest.engine import BacktestEngine
from swing_trading_system.domain import MarketBar


class FakeScreeningService:
    def run(self, *, strategy_id: str, as_of_date, market_bars, limit: int = 25):
        from swing_trading_system.domain import ScreenCandidate
        if as_of_date < date(2024, 1, 5):
            return []
        return [
            ScreenCandidate(
                strategy_id=strategy_id,
                signal_date=as_of_date,
                symbol="AAA",
                sector="Tech",
                industry="Software",
                close_price=Decimal("105"),
                adv20=Decimal("10000000"),
                atr14=Decimal("2"),
                relative_strength_20d=Decimal("0.03"),
                relative_strength_60d=Decimal("0.05"),
                volume_ratio20=Decimal("1.5"),
                breakout_level=Decimal("104"),
                pullback_distance_pct=Decimal("0.01"),
                score=Decimal("88"),
                risk_per_share=Decimal("5"),
                stop_price=Decimal("100"),
                target_price=Decimal("115"),
                reasons=["test"],
                metadata={},
            )
        ]


def _bars(symbol: str, start: date, closes: list[int]) -> list[MarketBar]:
    result = []
    for index, close in enumerate(closes):
        trade_date = start + timedelta(days=index)
        close_decimal = Decimal(close)
        result.append(MarketBar(symbol, trade_date, close_decimal, close_decimal + 1, close_decimal - 1, close_decimal, Decimal("1000000"), close_decimal * Decimal("1000000")))
    return result


def test_backtest_engine_generates_trades() -> None:
    engine = BacktestEngine(screening_service=FakeScreeningService())
    start = date(2024, 1, 1)
    market_bars = {
        "SPY": _bars("SPY", start, [100, 101, 102, 103, 104, 105, 106, 107, 108, 109]),
        "AAA": _bars("AAA", start, [100, 101, 102, 103, 104, 106, 108, 110, 112, 116]),
    }
    result = engine.run(
        strategy_id="breakout",
        market_bars=market_bars,
        start_date=start,
        end_date=start + timedelta(days=9),
        initial_capital=Decimal("100000"),
        max_positions=1,
        max_sector_positions=1,
        max_hold_days=5,
    )
    assert result.final_equity > Decimal("100000")
    assert result.trades


def test_backtest_engine_prefers_stop_when_daily_range_hits_stop_and_target() -> None:
    engine = BacktestEngine(screening_service=FakeScreeningService())
    start = date(2024, 1, 1)
    spy = _bars("SPY", start, [100, 101, 102, 103, 104, 105, 106, 107, 108, 109])
    aaa = _bars("AAA", start, [100, 101, 102, 103, 104, 106, 108, 110, 112, 116])
    aaa[5] = MarketBar("AAA", aaa[5].trade_date, Decimal("106"), Decimal("120"), Decimal("95"), Decimal("106"), Decimal("1000000"), Decimal("106000000"))
    result = engine.run(
        strategy_id="breakout",
        market_bars={"SPY": spy, "AAA": aaa},
        start_date=start,
        end_date=start + timedelta(days=9),
        initial_capital=Decimal("100000"),
        max_positions=1,
        max_sector_positions=1,
        max_hold_days=5,
    )
    assert result.trades
    assert result.trades[0].exit_reason in {"stop_loss", "stop_gap"}
