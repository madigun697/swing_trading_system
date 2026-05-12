"""Event-driven daily backtest engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping, Sequence

from swing_trading_system.backtest.metrics import calculate_metrics
from swing_trading_system.backtest.models import (
    BacktestConfig,
    BacktestRejection,
    BacktestResult,
    BacktestSignal,
    BacktestTrade,
    EquityCurvePoint,
    PriceBar,
)


class BacktestEngine:
    def run(
        self,
        signals: Sequence[BacktestSignal],
        prices_by_symbol: Mapping[str, Sequence[PriceBar]],
        config: BacktestConfig,
        run_id: str | None = None,
    ) -> BacktestResult:
        run_id = run_id or self.generate_run_id()
        trades: list[BacktestTrade] = []
        rejections: list[BacktestRejection] = []
        for signal in signals:
            trade, rejection = self._simulate_signal(signal, prices_by_symbol.get(signal.symbol, ()), config, run_id)
            if trade is not None:
                trades.append(trade)
            if rejection is not None:
                rejections.append(rejection)
        equity_curve = self._build_equity_curve(run_id, sorted(trades, key=lambda trade: trade.exit_date), config.initial_equity)
        metrics = calculate_metrics(trades, equity_curve, config.initial_equity)
        return BacktestResult(
            run_id=run_id,
            config=config,
            trades=tuple(trades),
            equity_curve=tuple(equity_curve),
            rejections=tuple(rejections),
            metrics=metrics,
        )

    @staticmethod
    def generate_run_id() -> str:
        return f"bt-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"

    def _simulate_signal(
        self,
        signal: BacktestSignal,
        price_rows: Sequence[PriceBar],
        config: BacktestConfig,
        run_id: str,
    ) -> tuple[BacktestTrade | None, BacktestRejection | None]:
        prices = sorted((bar for bar in price_rows if bar.trade_date > signal.signal_date), key=lambda bar: bar.trade_date)
        if not prices:
            return None, BacktestRejection(signal.id, signal.symbol, "missing_next_bar")
        if len(prices) < 2:
            return None, BacktestRejection(signal.id, signal.symbol, "insufficient_future_bars")

        entry_bar = prices[0]
        slippage = config.slippage_bps / 10_000.0
        fee_rate = config.fee_bps / 10_000.0
        entry_price = entry_bar.open * (1.0 + slippage)
        quantity = max(0.0, signal.position_size)
        if quantity <= 0:
            return None, BacktestRejection(signal.id, signal.symbol, "invalid_position_size")

        exit_price = prices[-1].close * (1.0 - slippage)
        exit_bar = prices[-1]
        exit_reason = "end_of_data"
        for days_held, bar in enumerate(prices[1:], start=1):
            stop_hit = bar.low <= signal.stop_price
            target_hit = bar.high >= signal.target_price
            if stop_hit:
                exit_price = signal.stop_price * (1.0 - slippage)
                exit_bar = bar
                exit_reason = "stop_loss" if not target_hit else "stop_loss_same_bar_conservative"
                break
            if target_hit:
                exit_price = signal.target_price * (1.0 - slippage)
                exit_bar = bar
                exit_reason = "target"
                break
            if days_held >= config.max_hold_days:
                exit_price = bar.close * (1.0 - slippage)
                exit_bar = bar
                exit_reason = "max_hold"
                break

        entry_notional = entry_price * quantity
        exit_notional = exit_price * quantity
        fees = (entry_notional + exit_notional) * fee_rate
        pnl = (exit_price - entry_price) * quantity - fees
        return (
            BacktestTrade(
                run_id=run_id,
                signal_id=signal.id,
                symbol=signal.symbol,
                strategy=signal.strategy,
                entry_date=entry_bar.trade_date,
                exit_date=exit_bar.trade_date,
                entry_price=round(entry_price, 6),
                exit_price=round(exit_price, 6),
                quantity=round(quantity, 6),
                pnl=round(pnl, 6),
                exit_reason=exit_reason,
                details={
                    "signal": signal.to_dict(),
                    "entry_bar": entry_bar.to_dict(),
                    "exit_bar": exit_bar.to_dict(),
                    "fee_bps": config.fee_bps,
                    "slippage_bps": config.slippage_bps,
                    "same_bar_exit_forbidden": True,
                },
            ),
            None,
        )

    def _build_equity_curve(self, run_id: str, trades: Sequence[BacktestTrade], initial_equity: float) -> list[EquityCurvePoint]:
        equity = initial_equity
        peak = initial_equity
        curve: list[EquityCurvePoint] = []
        if not trades:
            return curve
        for trade in trades:
            equity += trade.pnl
            peak = max(peak, equity)
            drawdown = (equity / peak) - 1.0 if peak else 0.0
            curve.append(
                EquityCurvePoint(
                    run_id=run_id,
                    equity_date=trade.exit_date,
                    equity=round(equity, 6),
                    drawdown=round(drawdown, 8),
                    details={"signal_id": trade.signal_id, "symbol": trade.symbol, "exit_reason": trade.exit_reason},
                )
            )
        return curve
