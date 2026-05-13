"""Event-driven daily backtest engine."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Mapping, Sequence

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
        equity_curve = self._build_equity_curve(
            run_id,
            sorted(trades, key=lambda trade: trade.exit_date),
            prices_by_symbol,
            config.initial_equity,
            config.benchmark_symbol,
        )
        metrics = calculate_metrics(trades, equity_curve, config.initial_equity)
        metrics.update(self._benchmark_metrics(equity_curve, metrics["total_return"]))
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
        quantity = self._sized_quantity(signal, entry_price, config)
        if quantity <= 0:
            return None, BacktestRejection(signal.id, signal.symbol, "invalid_position_size")

        exit_legs: list[dict[str, Any]] = []
        remaining_quantity = quantity
        target_scaled = False
        for days_held, bar in enumerate(prices[1:], start=1):
            if not target_scaled:
                stop_hit = bar.low <= signal.stop_price
                target_hit = bar.high >= signal.target_price
                if stop_hit:
                    reason = "stop_loss_same_bar_conservative" if target_hit else "stop_loss"
                    exit_legs.append(self._exit_leg(bar, remaining_quantity, signal.stop_price, slippage, fee_rate, reason))
                    remaining_quantity = 0.0
                    break
                if target_hit:
                    scale_out_pct = min(max(config.target_scale_out_pct, 0.0), 1.0)
                    has_future_bar = days_held < len(prices) - 1
                    scale_quantity = remaining_quantity
                    if config.enable_trailing_stop and has_future_bar and 0.0 < scale_out_pct < 1.0:
                        scale_quantity = remaining_quantity * scale_out_pct
                    exit_legs.append(self._exit_leg(bar, scale_quantity, signal.target_price, slippage, fee_rate, "target"))
                    remaining_quantity = max(0.0, remaining_quantity - scale_quantity)
                    target_scaled = remaining_quantity > 0
                    if not target_scaled:
                        break
                    continue
            else:
                trailing_stop = self._trailing_stop(prices, days_held, config.trailing_ma_days)
                if trailing_stop is not None and bar.low <= trailing_stop:
                    exit_legs.append(self._exit_leg(bar, remaining_quantity, trailing_stop, slippage, fee_rate, "trailing_stop"))
                    remaining_quantity = 0.0
                    break
            if days_held >= config.max_hold_days:
                reason = "target_then_max_hold" if target_scaled else "max_hold"
                exit_legs.append(self._exit_leg(bar, remaining_quantity, bar.close, slippage, fee_rate, reason))
                remaining_quantity = 0.0
                break
        if remaining_quantity > 0:
            reason = "target_then_end_of_data" if target_scaled else "end_of_data"
            exit_legs.append(self._exit_leg(prices[-1], remaining_quantity, prices[-1].close, slippage, fee_rate, reason))

        entry_notional = entry_price * quantity
        entry_fee = entry_notional * fee_rate
        exit_notional = sum(leg["price"] * leg["quantity"] for leg in exit_legs)
        exit_fees = sum(leg["fee"] for leg in exit_legs)
        fees = entry_fee + exit_fees
        pnl = sum((leg["price"] - entry_price) * leg["quantity"] for leg in exit_legs) - fees
        exit_price = exit_notional / quantity if quantity else 0.0
        exit_bar = prices[-1]
        if exit_legs:
            exit_bar = next((bar for bar in prices if bar.trade_date.isoformat() == exit_legs[-1]["date"]), prices[-1])
        exit_reason = self._combined_exit_reason(exit_legs)
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
                    "exit_legs": [
                        {
                            **leg,
                            "quantity": round(leg["quantity"], 6),
                            "price": round(leg["price"], 6),
                            "fee": round(leg["fee"], 6),
                        }
                        for leg in exit_legs
                    ],
                    "fee_bps": config.fee_bps,
                    "slippage_bps": config.slippage_bps,
                    "entry_notional": round(entry_notional, 6),
                    "entry_fee": round(entry_fee, 6),
                    "fees": round(fees, 6),
                    "raw_signal_position_size": signal.position_size,
                    "max_position_pct": config.max_position_pct,
                    "pullback_size_multiplier": config.pullback_size_multiplier,
                    "target_scale_out_pct": config.target_scale_out_pct,
                    "trailing_ma_days": config.trailing_ma_days,
                    "trailing_stop_enabled": config.enable_trailing_stop,
                    "same_bar_exit_forbidden": True,
                },
            ),
            None,
        )

    def _sized_quantity(self, signal: BacktestSignal, entry_price: float, config: BacktestConfig) -> float:
        quantity = max(0.0, signal.position_size)
        if signal.strategy == "pullback":
            quantity *= max(0.0, config.pullback_size_multiplier)
        if config.max_position_pct > 0 and entry_price > 0:
            max_quantity = (config.initial_equity * config.max_position_pct) / entry_price
            quantity = min(quantity, max_quantity)
        return quantity

    def _exit_leg(self, bar: PriceBar, quantity: float, raw_price: float, slippage: float, fee_rate: float, reason: str) -> dict[str, Any]:
        exit_price = raw_price * (1.0 - slippage)
        return {
            "date": bar.trade_date.isoformat(),
            "quantity": max(0.0, quantity),
            "price": exit_price,
            "reason": reason,
            "fee": max(0.0, quantity) * exit_price * fee_rate,
        }

    def _trailing_stop(self, prices: Sequence[PriceBar], current_index: int, trailing_ma_days: int) -> float | None:
        if trailing_ma_days <= 0:
            return None
        start = max(0, current_index - trailing_ma_days)
        closes = [bar.close for bar in prices[start:current_index] if bar.close is not None]
        if not closes:
            return None
        return sum(closes) / len(closes)

    def _combined_exit_reason(self, exit_legs: Sequence[dict[str, Any]]) -> str:
        if not exit_legs:
            return "unknown"
        reasons = [str(leg["reason"]) for leg in exit_legs]
        if len(set(reasons)) == 1:
            return reasons[0]
        if reasons[0] == "target":
            return f"target_then_{reasons[-1].removeprefix('target_then_')}"
        return "multi_exit"

    def _build_equity_curve(
        self,
        run_id: str,
        trades: Sequence[BacktestTrade],
        prices_by_symbol: Mapping[str, Sequence[PriceBar]],
        initial_equity: float,
        benchmark_symbol: str,
    ) -> list[EquityCurvePoint]:
        peak = initial_equity
        curve: list[EquityCurvePoint] = []
        if not trades:
            return curve
        min_date = min(trade.entry_date for trade in trades)
        max_date = max(trade.exit_date for trade in trades)
        trade_symbols = {trade.symbol for trade in trades}
        curve_dates = sorted(
            {
                bar.trade_date
                for symbol in trade_symbols
                for bar in prices_by_symbol.get(symbol, ())
                if min_date <= bar.trade_date <= max_date
            }
            | {trade.exit_date for trade in trades}
            | {trade.entry_date for trade in trades}
        )
        trades_by_exit_date: dict[date, list[BacktestTrade]] = {}
        for trade in trades:
            trades_by_exit_date.setdefault(trade.exit_date, []).append(trade)
        previous_equity = initial_equity
        benchmark_state = self._benchmark_state(prices_by_symbol.get(benchmark_symbol, ()), curve_dates, initial_equity)
        for equity_date in curve_dates:
            equity = initial_equity + sum(
                self._trade_mark_to_market(trade, equity_date, prices_by_symbol.get(trade.symbol, ()))
                for trade in trades
            )
            peak = max(peak, equity)
            drawdown = (equity / peak) - 1.0 if peak else 0.0
            date_trades = trades_by_exit_date.get(equity_date, [])
            benchmark_details = benchmark_state.get(equity_date, {})
            curve.append(
                EquityCurvePoint(
                    run_id=run_id,
                    equity_date=equity_date,
                    equity=round(equity, 6),
                    drawdown=round(drawdown, 8),
                    details={
                        "daily_pnl": round(equity - previous_equity, 6),
                        "trade_count": len(date_trades),
                        "open_trade_count": sum(1 for trade in trades if trade.entry_date <= equity_date <= trade.exit_date),
                        "symbols": [trade.symbol for trade in date_trades],
                        "exit_reasons": [trade.exit_reason for trade in date_trades],
                        **benchmark_details,
                    },
                )
            )
            previous_equity = equity
        return curve

    def _trade_mark_to_market(self, trade: BacktestTrade, as_of_date: date, price_rows: Sequence[PriceBar]) -> float:
        if as_of_date < trade.entry_date:
            return 0.0
        if as_of_date >= trade.exit_date:
            return trade.pnl
        entry_fee = _safe_float((trade.details or {}).get("entry_fee"))
        realized_pnl = 0.0
        exited_quantity = 0.0
        for leg in self._exit_legs_until(trade, as_of_date):
            quantity = _safe_float(leg.get("quantity"))
            price = _safe_float(leg.get("price"))
            fee = _safe_float(leg.get("fee"))
            exited_quantity += quantity
            realized_pnl += (price - trade.entry_price) * quantity - fee
        remaining_quantity = max(0.0, trade.quantity - exited_quantity)
        mark_price = self._latest_close(price_rows, as_of_date) or trade.entry_price
        unrealized_pnl = (mark_price - trade.entry_price) * remaining_quantity
        return realized_pnl + unrealized_pnl - entry_fee

    def _exit_legs_until(self, trade: BacktestTrade, as_of_date: date) -> list[dict[str, Any]]:
        legs = (trade.details or {}).get("exit_legs")
        if not isinstance(legs, list):
            return []
        eligible = []
        for leg in legs:
            if not isinstance(leg, dict):
                continue
            leg_date = _parse_date(leg.get("date"))
            if leg_date is not None and leg_date <= as_of_date:
                eligible.append(leg)
        return eligible

    def _latest_close(self, price_rows: Sequence[PriceBar], as_of_date: date) -> float | None:
        latest: PriceBar | None = None
        for bar in price_rows:
            if bar.trade_date <= as_of_date and (latest is None or latest.trade_date < bar.trade_date):
                latest = bar
        return latest.close if latest is not None else None

    def _benchmark_state(
        self,
        benchmark_prices: Sequence[PriceBar],
        curve_dates: Sequence[date],
        initial_equity: float,
    ) -> dict[date, dict[str, float | str]]:
        if not benchmark_prices or not curve_dates:
            return {}
        ordered = sorted(benchmark_prices, key=lambda item: item.trade_date)
        start_close = self._latest_close(ordered, curve_dates[0]) or next((bar.close for bar in ordered if bar.trade_date >= curve_dates[0]), None)
        if not start_close:
            return {}
        peak = initial_equity
        state: dict[date, dict[str, float | str]] = {}
        for curve_date in curve_dates:
            close = self._latest_close(ordered, curve_date)
            if close is None:
                continue
            benchmark_equity = initial_equity * (close / start_close)
            peak = max(peak, benchmark_equity)
            benchmark_drawdown = (benchmark_equity / peak) - 1.0 if peak else 0.0
            state[curve_date] = {
                "benchmark_symbol": ordered[0].symbol,
                "benchmark_equity": round(benchmark_equity, 6),
                "benchmark_drawdown": round(benchmark_drawdown, 8),
            }
        return state

    def _benchmark_metrics(self, equity_curve: Sequence[EquityCurvePoint], strategy_return: float) -> dict[str, float | None]:
        points = [
            point
            for point in equity_curve
            if isinstance(point.details.get("benchmark_equity"), (int, float))
        ]
        if not points:
            return {
                "benchmark_return": None,
                "benchmark_mdd": None,
                "benchmark_cagr": None,
                "excess_return": None,
            }
        initial_benchmark = float(points[0].details["benchmark_equity"])
        final_benchmark = float(points[-1].details["benchmark_equity"])
        benchmark_return = (final_benchmark / initial_benchmark) - 1.0 if initial_benchmark else 0.0
        benchmark_mdd = min(float(point.details.get("benchmark_drawdown", 0.0)) for point in points)
        elapsed_days = max(1, (points[-1].equity_date - points[0].equity_date).days)
        benchmark_cagr = (final_benchmark / initial_benchmark) ** (365.0 / elapsed_days) - 1.0 if initial_benchmark and final_benchmark > 0 else 0.0
        return {
            "benchmark_return": round(benchmark_return, 8),
            "benchmark_mdd": round(benchmark_mdd, 8),
            "benchmark_cagr": round(benchmark_cagr, 8),
            "excess_return": round(strategy_return - benchmark_return, 8),
        }


def _parse_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _safe_float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
