from __future__ import annotations

from datetime import date
from decimal import Decimal

from swing_trading_system.backtest.service import BacktestService
from swing_trading_system.domain import ScreenCandidate, TradePlan
from swing_trading_system.monitoring.service import MonitoringService
from swing_trading_system.repositories.swing_repository import SwingRepository
from swing_trading_system.screening.service import ScreeningService


class SwingOrchestrator:
    def __init__(
        self,
        screening_service: ScreeningService | None = None,
        swing_repository: SwingRepository | None = None,
        backtest_service: BacktestService | None = None,
        monitoring_service: MonitoringService | None = None,
    ) -> None:
        self.screening_service = screening_service or ScreeningService()
        self.swing_repository = swing_repository or SwingRepository()
        self.backtest_service = backtest_service or BacktestService()
        self.monitoring_service = monitoring_service or MonitoringService()

    def run_screen(self, *, strategy_id: str, as_of_date: date, save: bool) -> dict:
        candidates = self.screening_service.run(strategy_id=strategy_id, as_of_date=as_of_date)
        payload = {
            "strategy_id": strategy_id,
            "signal_date": as_of_date.isoformat(),
            "candidate_count": len(candidates),
            "symbols": [candidate.symbol for candidate in candidates],
        }
        if save:
            screen_run_id = self.swing_repository.create_screen_run(strategy_id, as_of_date, payload)
            record = self.swing_repository.save_screen_candidates(screen_run_id, strategy_id, as_of_date, candidates)
            trade_plans = self._build_trade_plans(candidates)
            self.swing_repository.save_trade_plans(trade_plans)
            payload["screen_run_id"] = record.screen_run_id
            payload["trade_plan_count"] = len(trade_plans)
        return payload

    def run_backtest(self, *, strategy_id: str, start_date: date, end_date: date, initial_capital: Decimal, save: bool) -> dict:
        if save:
            backtest_run_id, result = self.backtest_service.run_and_save(
                strategy_id=strategy_id,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
            )
        else:
            result = self.backtest_service.run(
                strategy_id=strategy_id,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
            )
            backtest_run_id = None
        return {
            "backtest_run_id": backtest_run_id,
            "strategy_id": strategy_id,
            "final_equity": str(result.final_equity),
            "total_return": str(result.total_return),
            "cagr": str(result.cagr),
            "max_drawdown": str(result.max_drawdown),
            "win_rate": str(result.win_rate),
            "trade_count": len(result.trades),
        }

    def run_end_of_day(self, *, as_of_date: date, save: bool, send_alerts: bool) -> dict:
        summaries = [
            self.run_screen(strategy_id="breakout", as_of_date=as_of_date, save=save),
            self.run_screen(strategy_id="pullback", as_of_date=as_of_date, save=save),
        ]
        alert_count = self.monitoring_service.run_end_of_day_monitor(as_of_date=as_of_date, send=send_alerts)
        return {"screen_runs": summaries, "alert_count": alert_count}

    def _build_trade_plans(self, candidates: list[ScreenCandidate]) -> list[TradePlan]:
        plans: list[TradePlan] = []
        for candidate in candidates[:5]:
            quantity = Decimal("100") if candidate.close_price <= 0 else (Decimal("10000") / candidate.close_price).quantize(Decimal("1"))
            if quantity <= 0:
                continue
            plans.append(
                TradePlan(
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
            )
        return plans
