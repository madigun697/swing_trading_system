"""Screening pipeline connecting inputs, feature store, screener, and strategies."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Protocol, Sequence

from swing_trading_system.screening.features import calculate_features
from swing_trading_system.screening.input_loader import ScreeningInputLoader
from swing_trading_system.screening.screener import Screener
from swing_trading_system.strategies.base import Strategy, StrategyContext, StrategySignal


class ScreeningPersistence(Protocol):
    def create_screening_run(
        self,
        run_date: date,
        universe_name: str | None = None,
        criteria: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...

    def complete_screening_run(self, screening_run_id: int, result_count: int, status: str = "completed") -> dict[str, Any]:
        ...

    def upsert_feature_store(
        self,
        symbol: str,
        feature_date: date,
        feature_set: str,
        features: dict[str, Any],
    ) -> dict[str, Any]:
        ...

    def create_signal(
        self,
        screening_run_id: int,
        symbol: str,
        signal_date: date,
        strategy: str,
        entry_price: Decimal | float | None = None,
        stop_price: Decimal | float | None = None,
        target_price: Decimal | float | None = None,
        risk_per_share: Decimal | float | None = None,
        position_size: Decimal | float | None = None,
        score: Decimal | float | None = None,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class CandidateSignal:
    symbol: str
    strategy: str
    score: Decimal | float | None = None
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScreeningPipelineResult:
    screening_run_id: int
    signal_count: int
    feature_count: int
    candidate_count: int = 0
    symbols: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "screening_run_id": self.screening_run_id,
            "signal_count": self.signal_count,
            "feature_count": self.feature_count,
            "candidate_count": self.candidate_count,
            "symbols": list(self.symbols),
        }


class ScreeningPipeline:
    def __init__(
        self,
        input_loader: ScreeningInputLoader,
        repository: ScreeningPersistence,
        screener: Screener | None = None,
        strategies: Sequence[Strategy] = (),
    ) -> None:
        self.input_loader = input_loader
        self.repository = repository
        self.screener = screener or Screener()
        self.strategies = tuple(strategies)

    def run_daily(
        self,
        symbols: list[str],
        as_of_date: date,
        universe_name: str | None = None,
        feature_set: str = "screening_v1",
        lookback_days: int = 365,
        benchmark_symbol: str = "SPY",
        context: StrategyContext | None = None,
    ) -> ScreeningPipelineResult:
        screening_run = self.repository.create_screening_run(
            run_date=as_of_date,
            universe_name=universe_name,
            criteria={
                "feature_set": feature_set,
                "lookback_days": lookback_days,
                "benchmark_symbol": benchmark_symbol,
                "strategies": [strategy.name for strategy in self.strategies],
            },
        )
        screening_run_id = int(screening_run["id"])
        inputs = self.input_loader.load_universe(symbols=symbols, as_of_date=as_of_date, lookback_days=lookback_days)
        benchmark_input = self.input_loader.load_symbol(
            symbol=benchmark_symbol,
            as_of_date=as_of_date,
            lookback_days=lookback_days,
        )

        features = [
            calculate_features(
                symbol=symbol,
                as_of_date=as_of_date,
                rows=list(screening_input.rows),
                benchmark_rows=list(benchmark_input.rows),
            )
            for symbol, screening_input in inputs.items()
        ]
        for feature in features:
            self.repository.upsert_feature_store(
                symbol=feature.symbol,
                feature_date=as_of_date,
                feature_set=feature_set,
                features=feature.to_dict(),
            )

        candidates = self.screener.screen(features)
        strategy_context = context or StrategyContext(as_of_date=as_of_date)
        signals: list[StrategySignal] = []
        for candidate in candidates:
            for strategy in self.strategies:
                signal = strategy.generate(candidate, strategy_context)
                if signal is not None:
                    signals.append(signal)

        for signal in signals:
            self.repository.create_signal(**signal.to_repository_kwargs(screening_run_id))

        self.repository.complete_screening_run(screening_run_id, result_count=len(signals))
        return ScreeningPipelineResult(
            screening_run_id=screening_run_id,
            signal_count=len(signals),
            feature_count=len(features),
            candidate_count=len(candidates),
            symbols=tuple(symbols),
        )

    def run_candidates(
        self,
        symbols: list[str],
        as_of_date: date,
        candidates: list[CandidateSignal],
        universe_name: str | None = None,
        feature_set: str = "screening_v1",
        lookback_days: int = 260,
    ) -> ScreeningPipelineResult:
        screening_run = self.repository.create_screening_run(
            run_date=as_of_date,
            universe_name=universe_name,
            criteria={"feature_set": feature_set, "lookback_days": lookback_days},
        )
        screening_run_id = int(screening_run["id"])

        inputs = self.input_loader.load_universe(symbols=symbols, as_of_date=as_of_date, lookback_days=lookback_days)
        for symbol, screening_input in inputs.items():
            latest = screening_input.latest_row or {}
            self.repository.upsert_feature_store(
                symbol=symbol,
                feature_date=as_of_date,
                feature_set=feature_set,
                features={
                    "row_count": len(screening_input.rows),
                    "latest_trade_date": str(latest.get("trade_date")) if latest else None,
                    "latest_close": str(latest.get("close")) if latest.get("close") is not None else None,
                },
            )

        for candidate in candidates:
            self.repository.create_signal(
                screening_run_id=screening_run_id,
                symbol=candidate.symbol,
                signal_date=as_of_date,
                strategy=candidate.strategy,
                score=candidate.score,
                reason=candidate.reason,
                details=candidate.details,
            )

        self.repository.complete_screening_run(screening_run_id, result_count=len(candidates))
        return ScreeningPipelineResult(
            screening_run_id=screening_run_id,
            signal_count=len(candidates),
            feature_count=len(inputs),
            candidate_count=len(candidates),
            symbols=tuple(symbols),
        )
