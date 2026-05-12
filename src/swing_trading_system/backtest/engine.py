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
        input_signals = tuple(signals)
        trades: list[BacktestTrade] = []
        rejections: list[BacktestRejection] = []
        unique_signals, duplicate_rejections = self._dedupe_signals(input_signals)
        rejections.extend(duplicate_rejections)
        for signal in unique_signals:
            trade, rejection = self._simulate_signal(signal, prices_by_symbol.get(signal.symbol, ()), config, run_id)
            if trade is not None:
                portfolio_rejection = self._portfolio_rejection(signal, trade, trades, config)
                if portfolio_rejection is not None:
                    rejections.append(portfolio_rejection)
                else:
                    trades.append(trade)
            if rejection is not None:
                rejections.append(rejection)
        equity_curve = self._build_equity_curve(run_id, sorted(trades, key=lambda trade: trade.exit_date), config.initial_equity)
        metrics = calculate_metrics(trades, equity_curve, config.initial_equity)
        metrics["rejection_count"] = len(rejections)
        metrics["duplicate_signal_rejections"] = sum(1 for rejection in rejections if rejection.reason == "duplicate_signal")
        return BacktestResult(
            run_id=run_id,
            config=config,
            trades=tuple(trades),
            equity_curve=tuple(equity_curve),
            rejections=tuple(rejections),
            metrics=metrics,
            signal_count=len(input_signals),
            signal_start_date=min((signal.signal_date for signal in input_signals), default=None),
            signal_end_date=max((signal.signal_date for signal in input_signals), default=None),
        )

    @staticmethod
    def generate_run_id() -> str:
        return f"bt-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"

    def _dedupe_signals(self, signals: Sequence[BacktestSignal]) -> tuple[list[BacktestSignal], list[BacktestRejection]]:
        seen: set[tuple[object, ...]] = set()
        unique: list[BacktestSignal] = []
        rejections: list[BacktestRejection] = []
        for signal in sorted(signals, key=lambda item: (item.signal_date, -(item.score or 0.0), item.symbol, item.strategy, item.id)):
            key = (
                signal.symbol,
                signal.strategy,
                signal.signal_date,
                round(signal.entry_price, 6),
                round(signal.stop_price, 6),
                round(signal.target_price, 6),
            )
            if key in seen:
                rejections.append(BacktestRejection(signal.id, signal.symbol, "duplicate_signal"))
                continue
            seen.add(key)
            unique.append(signal)
        return unique, rejections

    def _portfolio_rejection(
        self,
        signal: BacktestSignal,
        trade: BacktestTrade,
        accepted_trades: Sequence[BacktestTrade],
        config: BacktestConfig,
    ) -> BacktestRejection | None:
        open_trades = [
            accepted
            for accepted in accepted_trades
            if accepted.entry_date <= trade.entry_date <= accepted.exit_date
        ]
        if config.max_positions > 0 and len(open_trades) >= config.max_positions:
            return BacktestRejection(signal.id, signal.symbol, "max_positions_exceeded")
        max_exposure = config.initial_equity * config.max_gross_exposure_pct
        existing_exposure = sum(accepted.entry_price * accepted.quantity for accepted in open_trades)
        trade_exposure = trade.entry_price * trade.quantity
        if max_exposure > 0 and existing_exposure + trade_exposure > max_exposure:
            return BacktestRejection(signal.id, signal.symbol, "gross_exposure_exceeded")
        return None

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
                    "entry_notional": round(entry_notional, 6),
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
        trades_by_date: dict[object, list[BacktestTrade]] = {}
        for trade in trades:
            trades_by_date.setdefault(trade.exit_date, []).append(trade)
        for exit_date, date_trades in sorted(trades_by_date.items()):
            daily_pnl = sum(trade.pnl for trade in date_trades)
            equity += daily_pnl
            peak = max(peak, equity)
            drawdown = (equity / peak) - 1.0 if peak else 0.0
            curve.append(
                EquityCurvePoint(
                    run_id=run_id,
                    equity_date=exit_date,
                    equity=round(equity, 6),
                    drawdown=round(drawdown, 8),
                    details={
                        "daily_pnl": round(daily_pnl, 6),
                        "trade_count": len(date_trades),
                        "symbols": [trade.symbol for trade in date_trades],
                        "exit_reasons": [trade.exit_reason for trade in date_trades],
                    },
                )
            )
        return curve
