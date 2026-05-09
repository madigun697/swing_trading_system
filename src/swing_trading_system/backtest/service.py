from __future__ import annotations

from datetime import date
from decimal import Decimal

from swing_trading_system.backtest.engine import BacktestEngine
from swing_trading_system.domain import BacktestResult
from swing_trading_system.repositories.shared_market import SharedMarketRepository
from swing_trading_system.repositories.swing_repository import SwingRepository


class BacktestService:
    def __init__(
        self,
        shared_repository: SharedMarketRepository | None = None,
        swing_repository: SwingRepository | None = None,
        engine: BacktestEngine | None = None,
    ) -> None:
        self.shared_repository = shared_repository or SharedMarketRepository()
        self.swing_repository = swing_repository or SwingRepository()
        self.engine = engine or BacktestEngine()

    def run(self, *, strategy_id: str, start_date: date, end_date: date, initial_capital: Decimal) -> BacktestResult:
        market_bars = self.shared_repository.fetch_market_bars(as_of_date=end_date, lookback_days=520)
        return self.engine.run(
            strategy_id=strategy_id,
            market_bars=market_bars,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
        )

    def run_and_save(self, *, strategy_id: str, start_date: date, end_date: date, initial_capital: Decimal) -> tuple[int, BacktestResult]:
        result = self.run(strategy_id=strategy_id, start_date=start_date, end_date=end_date, initial_capital=initial_capital)
        backtest_run_id = self.swing_repository.save_backtest_result(result)
        return backtest_run_id, result
