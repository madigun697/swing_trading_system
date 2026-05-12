"""Backtest performance metrics."""

from __future__ import annotations

from math import prod
from typing import Any, Sequence

from swing_trading_system.backtest.models import BacktestTrade, EquityCurvePoint


def calculate_metrics(trades: Sequence[BacktestTrade], equity_curve: Sequence[EquityCurvePoint], initial_equity: float) -> dict[str, Any]:
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
    symbol_contribution = _group_pnl(trades, "symbol")
    strategy_contribution = _group_pnl(trades, "strategy")
    top_symbol_pnl = max((abs(value) for value in symbol_contribution.values()), default=0.0)
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
