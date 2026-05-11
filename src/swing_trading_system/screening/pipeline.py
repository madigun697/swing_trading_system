"""Screening pipeline foundation connecting inputs, feature store, and signals."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Protocol

from swing_trading_system.screening.input_loader import ScreeningInputLoader


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


class ScreeningPipeline:
    """Minimal Sprint 2-ready pipeline skeleton.

    This intentionally does not implement pullback/breakout rules yet. It wires the
    safe input boundary to Swing-owned persistence so strategy code can be added in
    Sprint 2 without changing storage contracts.
    """

    def __init__(self, input_loader: ScreeningInputLoader, repository: ScreeningPersistence) -> None:
        self.input_loader = input_loader
        self.repository = repository

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
        )
