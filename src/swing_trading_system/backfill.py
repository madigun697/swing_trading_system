"""Bootstrap backfill helpers for Sprint 2 prerequisites."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from swing_trading_system.repositories.shared_market import SharedMarketRepository
from swing_trading_system.repositories.swing_repository import SwingRepository
from swing_trading_system.screening.input_loader import ScreeningInputLoader
from swing_trading_system.screening.pipeline import ScreeningPipeline

DEFAULT_BACKFILL_SYMBOL_LIMIT = 10
DEFAULT_FEATURE_SET = "bootstrap_screening_v1"
DEFAULT_UNIVERSE_NAME = "bootstrap_liquid_universe"


@dataclass(frozen=True)
class BootstrapBackfillResult:
    strategy_configs_seeded: int
    feature_rows_upserted: int
    screening_run_id: int | None
    signal_count: int
    skipped: bool
    latest_trade_date: date | None
    symbols: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_configs_seeded": self.strategy_configs_seeded,
            "feature_rows_upserted": self.feature_rows_upserted,
            "screening_run_id": self.screening_run_id,
            "signal_count": self.signal_count,
            "skipped": self.skipped,
            "latest_trade_date": self.latest_trade_date,
            "symbols": list(self.symbols),
        }


def backfill_sprint2_bootstrap(
    market_repository: SharedMarketRepository,
    swing_repository: SwingRepository,
    symbol_limit: int = DEFAULT_BACKFILL_SYMBOL_LIMIT,
) -> BootstrapBackfillResult:
    counts = swing_repository.get_bootstrap_counts()
    latest_trade_date = market_repository.fetch_latest_trade_date()
    if latest_trade_date is None:
        raise RuntimeError("No shared price data available for backfill")

    seeded = 0
    seeded += _seed_strategy_configs(swing_repository)

    if counts["feature_rows"] > 0 or counts["screening_runs"] > 0:
        return BootstrapBackfillResult(
            strategy_configs_seeded=seeded,
            feature_rows_upserted=0,
            screening_run_id=None,
            signal_count=0,
            skipped=True,
            latest_trade_date=latest_trade_date,
            symbols=(),
        )

    symbols = tuple(
        market_repository.fetch_top_liquid_symbols(
            as_of_date=latest_trade_date, limit=symbol_limit
        )
    )
    loader = ScreeningInputLoader(market_repository)
    pipeline = ScreeningPipeline(loader, swing_repository)
    pipeline_result = pipeline.run_candidates(
        symbols=list(symbols),
        as_of_date=latest_trade_date,
        candidates=[],
        universe_name=DEFAULT_UNIVERSE_NAME,
        feature_set=DEFAULT_FEATURE_SET,
    )
    return BootstrapBackfillResult(
        strategy_configs_seeded=seeded,
        feature_rows_upserted=pipeline_result.feature_count,
        screening_run_id=pipeline_result.screening_run_id,
        signal_count=pipeline_result.signal_count,
        skipped=False,
        latest_trade_date=latest_trade_date,
        symbols=symbols,
    )


def _seed_strategy_configs(swing_repository: SwingRepository) -> int:
    configs = (
        {
            "strategy_name": "pullback",
            "params": {
                "trend_filter": "ma_50_gt_ma_200",
                "lookback_days": 260,
                "max_hold_days": 20,
                "risk_per_trade_pct": 0.01,
            },
        },
        {
            "strategy_name": "breakout",
            "params": {
                "trend_filter": "ma_50_gt_ma_200",
                "lookback_days": 260,
                "breakout_lookback_days": 20,
                "max_hold_days": 20,
                "risk_per_trade_pct": 0.01,
            },
        },
        {
            "strategy_name": "quality_momentum",
            "params": {
                "trend_filter": "close_gt_ma20_gt_ma50_gt_ma200",
                "min_relative_strength_60d": 0.15,
                "min_quality_score": 0.60,
                "risk_multiple_target": 3.0,
            },
        },
    )
    for config in configs:
        swing_repository.create_strategy_config(**config)
    return len(configs)
