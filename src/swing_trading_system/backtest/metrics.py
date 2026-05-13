"""Backtest performance metrics."""

from __future__ import annotations

from math import sqrt
from statistics import fmean, pstdev
from typing import Any, Sequence

from swing_trading_system.backtest.models import BacktestTrade, EquityCurvePoint


def calculate_metrics(trades: Sequence[BacktestTrade], equity_curve: Sequence[EquityCurvePoint], initial_equity: float, risk_free_rate: float = 0.0) -> dict[str, Any]:
    total_pnl = sum(trade.pnl for trade in trades)
    total_return = total_pnl / initial_equity if initial_equity else 0.0
    wins = [trade.pnl for trade in trades if trade.pnl > 0]
    losses = [trade.pnl for trade in trades if trade.pnl < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    win_rate = len(wins) / len(trades) if trades else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss else (None if gross_profit > 0 else 0.0)
    expectancy = total_pnl / len(trades) if trades else 0.0
    max_drawdown = min((point.drawdown for point in equity_curve), default=0.0)
    exposure_days = sum(max(0, (trade.exit_date - trade.entry_date).days) for trade in trades)
    average_hold_days = exposure_days / len(trades) if trades else 0.0
    symbol_contribution = _group_pnl(trades, "symbol")
    strategy_contribution = _group_pnl(trades, "strategy")
    top_symbol_pnl = max((abs(value) for value in symbol_contribution.values()), default=0.0)
    daily_returns = _daily_returns(equity_curve, initial_equity)
    sharpe_ratio = _annualized_sharpe(daily_returns, risk_free_rate)
    cagr = _cagr(equity_curve, initial_equity)
    calmar_ratio = (cagr / abs(max_drawdown)) if max_drawdown else None
    max_consecutive_wins, max_consecutive_losses = _streaks(trades)
    expectancy_per_dollar = _expectancy_per_dollar(trades)
    return {
        "trade_count": len(trades),
        "total_pnl": round(total_pnl, 6),
        "total_return": round(total_return, 8),
        "max_drawdown": round(max_drawdown, 8),
        "win_rate": round(win_rate, 8),
        "profit_factor": None if profit_factor is None else round(profit_factor, 8),
        "expectancy": round(expectancy, 6),
        "average_win": round(gross_profit / len(wins), 6) if wins else 0.0,
        "average_loss": round(sum(losses) / len(losses), 6) if losses else 0.0,
        "exposure_days": exposure_days,
        "average_hold_days": round(average_hold_days, 6),
        "sharpe_ratio": None if sharpe_ratio is None else round(sharpe_ratio, 8),
        "cagr": round(cagr, 8),
        "calmar_ratio": None if calmar_ratio is None else round(calmar_ratio, 8),
        "max_consecutive_wins": max_consecutive_wins,
        "max_consecutive_losses": max_consecutive_losses,
        "expectancy_per_dollar": round(expectancy_per_dollar, 8),
        "top_symbol_contribution_pct": round(top_symbol_pnl / abs(total_pnl), 8) if total_pnl else 0.0,
        "symbol_contribution": symbol_contribution,
        "strategy_contribution": strategy_contribution,
    }


def _group_pnl(trades: Sequence[BacktestTrade], attr: str) -> dict[str, float]:
    grouped: dict[str, float] = {}
    for trade in trades:
        key = str(getattr(trade, attr))
        grouped[key] = grouped.get(key, 0.0) + trade.pnl
    return {key: round(value, 6) for key, value in sorted(grouped.items())}


def _daily_returns(equity_curve: Sequence[EquityCurvePoint], initial_equity: float) -> list[float]:
    returns: list[float] = []
    previous_equity = initial_equity
    for point in equity_curve:
        if previous_equity:
            returns.append((point.equity / previous_equity) - 1.0)
        previous_equity = point.equity
    return returns


def _annualized_sharpe(daily_returns: Sequence[float], risk_free_rate: float) -> float | None:
    if len(daily_returns) < 2:
        return None
    daily_risk_free = risk_free_rate / 252.0
    excess_returns = [value - daily_risk_free for value in daily_returns]
    volatility = pstdev(excess_returns)
    if volatility == 0:
        return None
    return (fmean(excess_returns) / volatility) * sqrt(252)


def _cagr(equity_curve: Sequence[EquityCurvePoint], initial_equity: float) -> float:
    if not equity_curve or initial_equity <= 0:
        return 0.0
    final_equity = equity_curve[-1].equity
    if final_equity <= 0:
        return -1.0
    elapsed_days = max(1, (equity_curve[-1].equity_date - equity_curve[0].equity_date).days)
    return (final_equity / initial_equity) ** (365.0 / elapsed_days) - 1.0


def _streaks(trades: Sequence[BacktestTrade]) -> tuple[int, int]:
    max_wins = 0
    max_losses = 0
    current_wins = 0
    current_losses = 0
    for trade in sorted(trades, key=lambda item: (item.exit_date, item.signal_id)):
        if trade.pnl > 0:
            current_wins += 1
            current_losses = 0
        elif trade.pnl < 0:
            current_losses += 1
            current_wins = 0
        else:
            current_wins = 0
            current_losses = 0
        max_wins = max(max_wins, current_wins)
        max_losses = max(max_losses, current_losses)
    return max_wins, max_losses


def _expectancy_per_dollar(trades: Sequence[BacktestTrade]) -> float:
    values: list[float] = []
    for trade in trades:
        entry_notional = _safe_float((trade.details or {}).get("entry_notional"))
        if entry_notional <= 0:
            entry_notional = trade.entry_price * trade.quantity
        if entry_notional > 0:
            values.append(trade.pnl / entry_notional)
    return fmean(values) if values else 0.0


def _safe_float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
