from datetime import date, timedelta

from swing_trading_system.backtest.engine import BacktestEngine
from swing_trading_system.backtest.models import (
    BacktestConfig,
    BacktestSignal,
    PriceBar,
)
from swing_trading_system.market_regime import MarketRegimeId, default_regime_policy


def signal() -> BacktestSignal:
    return BacktestSignal(
        id=1,
        symbol="AAA",
        signal_date=date(2026, 1, 1),
        strategy="pullback",
        entry_price=100,
        stop_price=95,
        target_price=110,
        risk_per_share=5,
        position_size=10,
    )


def regime_signal(
    regime_id: MarketRegimeId, signal_id: int = 1, symbol: str = "AAA"
) -> BacktestSignal:
    return BacktestSignal(
        id=signal_id,
        symbol=symbol,
        signal_date=date(2026, 1, 1),
        strategy="pullback",
        entry_price=100,
        stop_price=95,
        target_price=110,
        risk_per_share=5,
        position_size=10,
        details={"market_regime": {"regime_id": regime_id.value}},
    )


def bar(day: int, open_price=100, high=105, low=99, close=102) -> PriceBar:
    return PriceBar(
        "AAA",
        date(2026, 1, 1) + timedelta(days=day),
        open_price,
        high,
        low,
        close,
        1000,
    )


def test_engine_enters_on_next_open_and_targets_after_entry_bar() -> None:
    result = BacktestEngine().run(
        signals=[signal()],
        prices_by_symbol={
            "AAA": [
                bar(0, open_price=1, high=999, low=1),
                bar(1, open_price=101),
                bar(2, high=111, low=100),
            ]
        },
        config=BacktestConfig(fee_bps=0, slippage_bps=0, max_hold_days=5),
        run_id="test-run",
    )

    trade = result.trades[0]
    assert trade.entry_date == date(2026, 1, 2)
    assert trade.entry_price == 101
    assert trade.exit_date == date(2026, 1, 3)
    assert trade.exit_reason == "target"
    assert trade.pnl == 90


def test_engine_rejects_duplicate_signals() -> None:
    duplicate = signal()
    result = BacktestEngine().run(
        signals=[signal(), duplicate],
        prices_by_symbol={"AAA": [bar(1, open_price=101), bar(2, high=111, low=100)]},
        config=BacktestConfig(fee_bps=0, slippage_bps=0),
        run_id="test-run",
    )

    assert len(result.trades) == 1
    assert any(
        rejection.reason == "duplicate_signal" for rejection in result.rejections
    )


def test_engine_enforces_max_positions() -> None:
    second = BacktestSignal(2, "BBB", date(2026, 1, 1), "pullback", 100, 95, 110, 5, 10)
    result = BacktestEngine().run(
        signals=[signal(), second],
        prices_by_symbol={
            "AAA": [
                PriceBar("AAA", date(2026, 1, 2), 100, 101, 99, 100),
                PriceBar("AAA", date(2026, 1, 3), 100, 101, 99, 100),
            ],
            "BBB": [
                PriceBar("BBB", date(2026, 1, 2), 100, 101, 99, 100),
                PriceBar("BBB", date(2026, 1, 3), 100, 101, 99, 100),
            ],
        },
        config=BacktestConfig(fee_bps=0, slippage_bps=0, max_positions=1),
        run_id="test-run",
    )

    assert len(result.trades) == 1
    assert any(
        rejection.reason == "max_positions_exceeded" for rejection in result.rejections
    )


def test_engine_enforces_gross_exposure_limit() -> None:
    result = BacktestEngine().run(
        signals=[signal()],
        prices_by_symbol={"AAA": [bar(1, open_price=1000), bar(2, close=1001)]},
        config=BacktestConfig(
            initial_equity=1000,
            fee_bps=0,
            slippage_bps=0,
            max_gross_exposure_pct=0.5,
            max_position_pct=0,
        ),
        run_id="test-run",
    )

    assert result.trades == ()
    assert any(
        rejection.reason == "gross_exposure_exceeded" for rejection in result.rejections
    )


def test_equity_curve_aggregates_same_day_exits() -> None:
    second = BacktestSignal(2, "BBB", date(2026, 1, 1), "pullback", 100, 95, 110, 5, 10)
    result = BacktestEngine().run(
        signals=[signal(), second],
        prices_by_symbol={
            "AAA": [
                PriceBar("AAA", date(2026, 1, 2), 100, 101, 99, 100),
                PriceBar("AAA", date(2026, 1, 3), 100, 111, 99, 100),
            ],
            "BBB": [
                PriceBar("BBB", date(2026, 1, 2), 100, 101, 99, 100),
                PriceBar("BBB", date(2026, 1, 3), 100, 111, 99, 100),
            ],
        },
        config=BacktestConfig(fee_bps=0, slippage_bps=0, max_positions=10),
        run_id="test-run",
    )

    assert len(result.trades) == 2
    assert len(result.equity_curve) == 2
    assert result.equity_curve[-1].details["trade_count"] == 2


def test_engine_caps_position_size_by_max_position_pct() -> None:
    large = BacktestSignal(1, "AAA", date(2026, 1, 1), "breakout", 100, 95, 110, 5, 100)
    result = BacktestEngine().run(
        [large],
        {"AAA": [bar(1, open_price=100), bar(2, close=101)]},
        BacktestConfig(
            initial_equity=1000, fee_bps=0, slippage_bps=0, max_position_pct=0.1
        ),
        run_id="r",
    )

    assert result.trades[0].quantity == 1


def test_engine_partially_takes_target_then_trails_remainder() -> None:
    result = BacktestEngine().run(
        [signal()],
        {
            "AAA": [
                bar(1, open_price=100, high=101, low=99, close=100),
                bar(2, high=111, low=100, close=111),
                bar(3, high=106, low=104, close=104),
            ]
        },
        BacktestConfig(
            fee_bps=0, slippage_bps=0, trailing_ma_days=2, target_scale_out_pct=0.5
        ),
        run_id="r",
    )

    trade = result.trades[0]
    assert trade.exit_reason == "target_then_trailing_stop"
    assert trade.details["exit_legs"][0]["reason"] == "target"
    assert trade.details["exit_legs"][1]["reason"] == "trailing_stop"
    assert trade.pnl == 77.5


def test_engine_adds_spy_benchmark_metrics() -> None:
    result = BacktestEngine().run(
        [signal()],
        {
            "AAA": [
                bar(1, open_price=100, close=100),
                bar(2, high=111, low=100, close=110),
            ],
            "SPY": [
                PriceBar("SPY", date(2026, 1, 2), 100, 100, 100, 100),
                PriceBar("SPY", date(2026, 1, 3), 110, 110, 110, 110),
            ],
        },
        BacktestConfig(fee_bps=0, slippage_bps=0, benchmark_symbol="SPY"),
        run_id="r",
    )

    assert result.metrics["benchmark_return"] == 0.1
    assert result.metrics["benchmark_mdd"] == 0.0
    assert result.metrics["excess_return"] is not None


def test_engine_rejects_missing_next_bar() -> None:
    result = BacktestEngine().run([signal()], {"AAA": []}, BacktestConfig(), run_id="r")

    assert result.trades == ()
    assert result.rejections[0].reason == "missing_next_bar"


def test_engine_uses_stop_first_when_stop_and_target_same_bar() -> None:
    result = BacktestEngine().run(
        [signal()],
        {"AAA": [bar(1, open_price=100), bar(2, high=120, low=90)]},
        BacktestConfig(fee_bps=0, slippage_bps=0),
        run_id="r",
    )

    assert result.trades[0].exit_reason == "stop_loss_same_bar_conservative"
    assert result.trades[0].exit_price == 95


def test_engine_risk_off_exits_next_open_after_bear_regime() -> None:
    result = BacktestEngine().run(
        [regime_signal(MarketRegimeId.R2_VOLATILE_BULL)],
        {
            "AAA": [
                bar(1, open_price=100, high=101, low=99, close=100),
                bar(2, open_price=90, high=92, low=88, close=91),
            ]
        },
        BacktestConfig(fee_bps=0, slippage_bps=0),
        run_id="r",
        regime_by_date={date(2026, 1, 2): MarketRegimeId.R4_EARLY_BEAR.value},
        regime_policy=default_regime_policy(require_vix=True),
    )

    assert result.trades[0].exit_reason == "risk_off_exit"
    assert result.trades[0].exit_price == 90


def test_engine_rejects_when_regime_portfolio_heat_is_exceeded() -> None:
    second = regime_signal(MarketRegimeId.R1_STRONG_BULL, signal_id=2, symbol="BBB")
    result = BacktestEngine().run(
        [regime_signal(MarketRegimeId.R1_STRONG_BULL), second],
        {
            "AAA": [
                PriceBar("AAA", date(2026, 1, 2), 100, 101, 99, 100),
                PriceBar("AAA", date(2026, 1, 3), 100, 101, 99, 100),
            ],
            "BBB": [
                PriceBar("BBB", date(2026, 1, 2), 100, 101, 99, 100),
                PriceBar("BBB", date(2026, 1, 3), 100, 101, 99, 100),
            ],
        },
        BacktestConfig(
            initial_equity=1000,
            fee_bps=0,
            slippage_bps=0,
            max_gross_exposure_pct=10,
            max_position_pct=0,
        ),
        run_id="r",
        regime_policy=default_regime_policy(require_vix=True),
    )

    assert len(result.trades) == 1
    assert any(
        rejection.reason == "portfolio_heat_exceeded" for rejection in result.rejections
    )


def test_engine_moves_stop_to_breakeven_after_one_r() -> None:
    result = BacktestEngine().run(
        [signal()],
        {
            "AAA": [
                bar(1, open_price=100, high=101, low=99, close=100),
                bar(2, high=106, low=99, close=104),
                bar(3, high=104, low=99, close=100),
            ]
        },
        BacktestConfig(fee_bps=0, slippage_bps=0),
        run_id="r",
    )

    assert result.trades[0].exit_reason == "breakeven_stop"
    assert result.trades[0].pnl == 0


def test_engine_exits_failed_trade_without_widening_stop() -> None:
    result = BacktestEngine().run(
        [signal()],
        {
            "AAA": [
                bar(1, open_price=100, high=101, low=99, close=100),
                bar(2, high=101, low=98, close=99),
                bar(3, high=101, low=98, close=99),
            ]
        },
        BacktestConfig(
            fee_bps=0,
            slippage_bps=0,
            failed_trade_exit_days=2,
            failed_trade_min_r_multiple=0.5,
        ),
        run_id="r",
    )

    assert result.trades[0].exit_reason == "failed_trade_exit"
    assert result.trades[0].exit_price == 99


def test_engine_applies_regime_strategy_multiplier_to_quantity() -> None:
    breakout = BacktestSignal(
        id=1,
        symbol="AAA",
        signal_date=date(2026, 1, 1),
        strategy="breakout",
        entry_price=100,
        stop_price=95,
        target_price=110,
        risk_per_share=5,
        position_size=10,
        details={"market_regime": {"regime_id": MarketRegimeId.R1_STRONG_BULL.value}},
    )

    result = BacktestEngine().run(
        [breakout],
        {"AAA": [bar(1, open_price=100), bar(2, high=101, low=99, close=100)]},
        BacktestConfig(
            fee_bps=0,
            slippage_bps=0,
            max_position_pct=0,
            regime_strategy_multipliers={
                MarketRegimeId.R1_STRONG_BULL.value: {"breakout": 2.0}
            },
        ),
        run_id="r",
    )

    assert result.trades[0].quantity == 20


def test_engine_rejects_new_trades_during_stop_loss_cooldown() -> None:
    signals = [
        BacktestSignal(
            id=signal_id,
            symbol=f"A{signal_id}",
            signal_date=date(2026, 1, signal_id),
            strategy="breakout",
            entry_price=100,
            stop_price=95,
            target_price=110,
            risk_per_share=5,
            position_size=10,
        )
        for signal_id in range(1, 5)
    ]
    prices = {
        signal.symbol: [
            PriceBar(
                signal.symbol, signal.signal_date + timedelta(days=1), 100, 101, 99, 100
            ),
            PriceBar(
                signal.symbol, signal.signal_date + timedelta(days=2), 100, 101, 94, 94
            ),
        ]
        for signal in signals
    }

    result = BacktestEngine().run(
        signals,
        prices,
        BacktestConfig(
            fee_bps=0,
            slippage_bps=0,
            stop_loss_cooldown_lookback_days=20,
            stop_loss_cooldown_threshold=1,
        ),
        run_id="r",
    )

    assert len(result.trades) == 2
    assert any(
        rejection.reason == "stop_loss_cooldown" for rejection in result.rejections
    )
