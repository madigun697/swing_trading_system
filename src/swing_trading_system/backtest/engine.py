from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from math import sqrt

from swing_trading_system.config import get_settings
from swing_trading_system.domain import BacktestResult, BacktestTrade, EquityPoint, MarketBar, ScreenCandidate, TradePlan
from swing_trading_system.screening.service import ScreeningService


@dataclass
class Position:
    strategy_id: str
    symbol: str
    sector: str | None
    entry_date: date
    quantity: Decimal
    entry_price: Decimal
    stop_price: Decimal
    target_price: Decimal
    highest_close: Decimal


@dataclass(frozen=True)
class PendingEntry:
    entry_date: date
    plan: TradePlan


@dataclass(frozen=True)
class PendingExit:
    exit_date: date
    symbol: str
    reason: str


class BacktestEngine:
    def __init__(self, screening_service: ScreeningService | None = None) -> None:
        self.screening_service = screening_service or ScreeningService()
        self.settings = get_settings()

    def run(
        self,
        *,
        strategy_id: str,
        market_bars: dict[str, list[MarketBar]],
        start_date: date,
        end_date: date,
        initial_capital: Decimal,
        max_positions: int | None = None,
        max_sector_positions: int | None = None,
        risk_per_trade_pct: Decimal | None = None,
        max_hold_days: int | None = None,
        fee_bps: Decimal | None = None,
        slippage_bps: Decimal | None = None,
    ) -> BacktestResult:
        max_positions = max_positions or self.settings.swing_max_positions
        max_sector_positions = max_sector_positions or self.settings.swing_max_sector_positions
        risk_per_trade_pct = risk_per_trade_pct or Decimal(str(self.settings.swing_risk_per_trade_pct))
        max_hold_days = max_hold_days or self.settings.swing_default_max_hold_days
        fee_bps = fee_bps or Decimal(str(self.settings.swing_fee_bps))
        slippage_bps = slippage_bps or Decimal(str(self.settings.swing_slippage_bps))

        bars_by_symbol = {symbol: {bar.trade_date: bar for bar in rows} for symbol, rows in market_bars.items()}
        calendar = sorted({bar.trade_date for bar in market_bars.get("SPY", []) if start_date <= bar.trade_date <= end_date})
        if len(calendar) < 2:
            raise ValueError("Not enough benchmark dates to run backtest")
        next_date = {calendar[index]: calendar[index + 1] for index in range(len(calendar) - 1)}
        positions: dict[str, Position] = {}
        pending_entries: list[PendingEntry] = []
        pending_exits: list[PendingExit] = []
        trades: list[BacktestTrade] = []
        equity_curve: list[EquityPoint] = []
        cash = initial_capital
        peak_equity = initial_capital
        sector_counts: Counter[str] = Counter()
        trade_id = 1

        for current_date in calendar:
            todays_entries = [entry for entry in pending_entries if entry.entry_date == current_date]
            pending_entries = [entry for entry in pending_entries if entry.entry_date != current_date]
            todays_exits = [exit_order for exit_order in pending_exits if exit_order.exit_date == current_date]
            pending_exits = [exit_order for exit_order in pending_exits if exit_order.exit_date != current_date]

            for exit_order in todays_exits:
                position = positions.get(exit_order.symbol)
                if position is None:
                    continue
                bar = bars_by_symbol.get(exit_order.symbol, {}).get(current_date)
                if bar is None or bar.open is None:
                    continue
                exit_price = self._apply_slippage(bar.open, sell=True, slippage_bps=slippage_bps)
                fees = self._fees(exit_price * position.quantity, fee_bps)
                proceeds = exit_price * position.quantity - fees
                cash += proceeds
                pnl = (exit_price - position.entry_price) * position.quantity - fees
                trades.append(
                    BacktestTrade(
                        trade_id=trade_id,
                        strategy_id=position.strategy_id,
                        symbol=position.symbol,
                        entry_date=position.entry_date,
                        exit_date=current_date,
                        quantity=position.quantity,
                        entry_price=position.entry_price,
                        exit_price=exit_price,
                        pnl=pnl,
                        return_pct=(exit_price / position.entry_price) - Decimal("1"),
                        exit_reason=exit_order.reason,
                        hold_days=max((current_date - position.entry_date).days, 1),
                    )
                )
                trade_id += 1
                if position.sector:
                    sector_counts[position.sector] -= 1
                positions.pop(exit_order.symbol, None)

            for entry in todays_entries:
                plan = entry.plan
                if plan.symbol in positions:
                    continue
                bar = bars_by_symbol.get(plan.symbol, {}).get(current_date)
                if bar is None or bar.open is None:
                    continue
                fill_price = self._apply_slippage(bar.open, sell=False, slippage_bps=slippage_bps)
                if fill_price <= plan.stop_price:
                    continue
                cost = fill_price * plan.quantity
                fees = self._fees(cost, fee_bps)
                if cost + fees > cash:
                    continue
                cash -= cost + fees
                positions[plan.symbol] = Position(
                    strategy_id=plan.strategy_id,
                    symbol=plan.symbol,
                    sector=plan.sector,
                    entry_date=current_date,
                    quantity=plan.quantity,
                    entry_price=fill_price,
                    stop_price=plan.stop_price,
                    target_price=plan.target_price,
                    highest_close=fill_price,
                )
                if plan.sector:
                    sector_counts[plan.sector] += 1

            for symbol, position in list(positions.items()):
                bar = bars_by_symbol.get(symbol, {}).get(current_date)
                if bar is None or bar.low is None or bar.high is None or bar.close is None:
                    continue
                position.highest_close = max(position.highest_close, bar.close)
                exit_reason: str | None = None
                exit_price: Decimal | None = None
                # Conservative intraday rule:
                # 1) gap below stop => exit at open
                # 2) gap above target => exit at target
                # 3) if both stop and target are inside the same day's range, stop wins
                if bar.open is not None and bar.open <= position.stop_price:
                    exit_reason = "stop_gap"
                    exit_price = self._apply_slippage(bar.open, sell=True, slippage_bps=slippage_bps)
                elif bar.open is not None and bar.open >= position.target_price:
                    exit_reason = "target_gap"
                    exit_price = position.target_price
                elif bar.low <= position.stop_price:
                    exit_reason = "stop_loss"
                    exit_price = position.stop_price
                elif bar.high >= position.target_price:
                    exit_reason = "target_hit"
                    exit_price = position.target_price

                if exit_reason is not None and exit_price is not None:
                    fees = self._fees(exit_price * position.quantity, fee_bps)
                    cash += exit_price * position.quantity - fees
                    pnl = (exit_price - position.entry_price) * position.quantity - fees
                    trades.append(
                        BacktestTrade(
                            trade_id=trade_id,
                            strategy_id=position.strategy_id,
                            symbol=position.symbol,
                            entry_date=position.entry_date,
                            exit_date=current_date,
                            quantity=position.quantity,
                            entry_price=position.entry_price,
                            exit_price=exit_price,
                            pnl=pnl,
                            return_pct=(exit_price / position.entry_price) - Decimal("1"),
                            exit_reason=exit_reason,
                            hold_days=max((current_date - position.entry_date).days, 1),
                        )
                    )
                    trade_id += 1
                    if position.sector:
                        sector_counts[position.sector] -= 1
                    positions.pop(symbol, None)
                    continue
                if (current_date - position.entry_date).days >= max_hold_days and current_date in next_date:
                    pending_exits.append(PendingExit(next_date[current_date], symbol, "max_hold"))
                elif bar.close > position.entry_price + (position.target_price - position.entry_price) * Decimal("0.5"):
                    position.stop_price = max(position.stop_price, position.highest_close - (position.target_price - position.entry_price) * Decimal("0.35"))

            if current_date in next_date:
                available_slots = max_positions - len(positions) - sum(1 for entry in pending_entries if entry.entry_date == next_date[current_date])
                if available_slots > 0:
                    candidates = self.screening_service.run(strategy_id=strategy_id, as_of_date=current_date, market_bars=market_bars, limit=max_positions * 4)
                    equity = cash + self._market_value(positions, bars_by_symbol, current_date)
                    for candidate in candidates:
                        if available_slots <= 0:
                            break
                        if candidate.symbol in positions:
                            continue
                        if any(entry.plan.symbol == candidate.symbol for entry in pending_entries):
                            continue
                        if candidate.sector and sector_counts[candidate.sector] >= max_sector_positions:
                            continue
                        plan = self._build_plan(candidate, equity=equity, risk_per_trade_pct=risk_per_trade_pct)
                        if plan is None:
                            continue
                        pending_entries.append(PendingEntry(next_date[current_date], plan))
                        available_slots -= 1

            market_value = self._market_value(positions, bars_by_symbol, current_date)
            total_equity = cash + market_value
            peak_equity = max(peak_equity, total_equity)
            drawdown = Decimal("0") if peak_equity == 0 else (total_equity / peak_equity) - Decimal("1")
            equity_curve.append(EquityPoint(current_date, cash, market_value, total_equity, drawdown))

        final_equity = equity_curve[-1].total_equity if equity_curve else initial_capital
        total_return = Decimal("0") if initial_capital == 0 else (final_equity / initial_capital) - Decimal("1")
        year_fraction = max((end_date - start_date).days / 365.25, 1 / 365.25)
        cagr = Decimal(str((float(final_equity / initial_capital) ** (1 / year_fraction)) - 1)) if initial_capital > 0 else Decimal("0")
        max_drawdown = min((point.drawdown for point in equity_curve), default=Decimal("0"))
        win_rate = Decimal(str(sum(1 for trade in trades if trade.pnl > 0) / len(trades))) if trades else Decimal("0")
        daily_returns = []
        for prev, current in zip(equity_curve[:-1], equity_curve[1:]):
            if prev.total_equity > 0:
                daily_returns.append(float(current.total_equity / prev.total_equity - Decimal("1")))
        sharpe_ratio = Decimal("0")
        if len(daily_returns) > 1:
            avg_return = sum(daily_returns) / len(daily_returns)
            variance = sum((value - avg_return) ** 2 for value in daily_returns) / len(daily_returns)
            stddev = variance ** 0.5
            if stddev > 0:
                sharpe_ratio = Decimal(str((avg_return / stddev) * sqrt(252)))
        return BacktestResult(
            strategy_id=strategy_id,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            final_equity=final_equity,
            total_return=total_return,
            cagr=cagr,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            win_rate=win_rate,
            trades=trades,
            equity_curve=equity_curve,
            params={
                "max_positions": max_positions,
                "max_sector_positions": max_sector_positions,
                "risk_per_trade_pct": str(risk_per_trade_pct),
                "max_hold_days": max_hold_days,
                "fee_bps": str(fee_bps),
                "slippage_bps": str(slippage_bps),
            },
        )

    def _build_plan(self, candidate: ScreenCandidate, *, equity: Decimal, risk_per_trade_pct: Decimal) -> TradePlan | None:
        risk_amount = equity * risk_per_trade_pct
        if candidate.risk_per_share <= 0:
            return None
        quantity = (risk_amount / candidate.risk_per_share).quantize(Decimal("1"))
        if quantity <= 0:
            return None
        return TradePlan(
            strategy_id=candidate.strategy_id,
            signal_date=candidate.signal_date,
            symbol=candidate.symbol,
            side="buy",
            quantity=quantity,
            entry_price=candidate.close_price,
            stop_price=candidate.stop_price,
            target_price=candidate.target_price,
            risk_per_share=candidate.risk_per_share,
            score=candidate.score,
            sector=candidate.sector,
            notes=", ".join(candidate.reasons),
            metadata=candidate.metadata,
        )

    def _fees(self, notional: Decimal, fee_bps: Decimal) -> Decimal:
        return notional * fee_bps / Decimal("10000")

    def _apply_slippage(self, price: Decimal, *, sell: bool, slippage_bps: Decimal) -> Decimal:
        adjustment = price * slippage_bps / Decimal("10000")
        return price - adjustment if sell else price + adjustment

    def _market_value(self, positions: dict[str, Position], bars_by_symbol: dict[str, dict[date, MarketBar]], current_date: date) -> Decimal:
        total = Decimal("0")
        for position in positions.values():
            bar = bars_by_symbol.get(position.symbol, {}).get(current_date)
            if bar and bar.close is not None:
                total += bar.close * position.quantity
        return total
