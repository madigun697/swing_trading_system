"""Backtest parameter sweep optimizer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from math import inf
from typing import Any, Mapping, Sequence

from swing_trading_system.backtest.engine import BacktestEngine
from swing_trading_system.backtest.models import (
    BacktestConfig,
    BacktestResult,
    BacktestSignal,
    PriceBar,
)
from swing_trading_system.backtest.repository import BacktestRepository
from swing_trading_system.config import Settings
from swing_trading_system.market_regime import regime_policy_from_json
from swing_trading_system.repositories.shared_market import SharedMarketRepository

DEFAULT_OPTIMIZE_START_DATE = date(2025, 1, 2)
DEFAULT_OPTIMIZE_END_DATE = date(2026, 5, 1)
RECENT_SEED_LIMIT = 5
MIN_ELIGIBLE_TRADES = 30

STAGE1_VALUES: dict[str, tuple[object, ...]] = {
    "max_positions": (10, 15, 20, 30),
    "max_gross_exposure_pct": (1.0, 1.1, 1.2),
    "max_portfolio_risk_pct": (0.04, 0.06, 0.08, 0.10),
    "max_position_pct": (0.10, 0.125, 0.15),
    "pullback_size_multiplier": (0.75, 1.0, 1.25),
}

STAGE2_VALUES: dict[str, tuple[object, ...]] = {
    "max_hold_days": (20, 30, 40),
    "target_scale_out_pct": (0.25, 0.5, 0.75, 1.0),
    "enable_trailing_stop": (True, False),
    "trailing_ma_days": (5, 10, 20),
    "enable_breakeven_stop": (True, False),
    "failed_trade_exit_days": (4, 6, 8),
    "failed_trade_min_r_multiple": (0.3, 0.5, 0.7),
}


@dataclass(frozen=True)
class StrategySelection:
    key: str
    allowed_strategies: frozenset[str] | None = None
    require_market_regime: bool = False


@dataclass(frozen=True)
class OptimizationCandidate:
    strategy: str
    config: BacktestConfig


@dataclass(frozen=True)
class CandidateEvaluation:
    candidate: OptimizationCandidate
    result: BacktestResult

    @property
    def trade_count(self) -> int:
        return len(self.result.trades)

    @property
    def signal_count(self) -> int:
        return self.result.signal_count

    @property
    def metrics(self) -> dict[str, Any]:
        return self.result.metrics

    @property
    def eligible(self) -> bool:
        return self.signal_count > 0 and self.trade_count >= MIN_ELIGIBLE_TRADES

    def summary(self) -> dict[str, Any]:
        metrics = self.metrics
        return {
            "run_id": self.result.run_id,
            "strategy": self.candidate.strategy,
            "config": self.candidate.config.to_dict(),
            "signal_count": self.signal_count,
            "trade_count": self.trade_count,
            "cagr": metrics.get("cagr"),
            "max_drawdown": metrics.get("max_drawdown"),
            "calmar_ratio": metrics.get("calmar_ratio"),
            "total_return": metrics.get("total_return"),
            "rejection_count": metrics.get(
                "rejection_count", len(self.result.rejections)
            ),
        }


STRATEGY_OPTIONS: tuple[StrategySelection, ...] = (
    StrategySelection("market_regime", require_market_regime=True),
    StrategySelection("all_signals"),
    StrategySelection("breakout", frozenset({"breakout"})),
    StrategySelection("pullback", frozenset({"pullback"})),
    StrategySelection("quality_momentum", frozenset({"quality_momentum"})),
    StrategySelection("breakout+pullback", frozenset({"breakout", "pullback"})),
    StrategySelection(
        "breakout+quality_momentum",
        frozenset({"breakout", "quality_momentum"}),
    ),
    StrategySelection(
        "pullback+quality_momentum",
        frozenset({"pullback", "quality_momentum"}),
    ),
)
STRATEGY_BY_KEY = {option.key: option for option in STRATEGY_OPTIONS}


def optimize_backtest(
    *,
    settings: Settings,
    start_date: date | None = None,
    end_date: date | None = None,
    symbols: list[str] | None = None,
    persist_winners: bool = False,
    repository: BacktestRepository | None = None,
    shared_market_repository: SharedMarketRepository | None = None,
    engine: BacktestEngine | None = None,
) -> dict[str, Any]:
    repository = repository or BacktestRepository(settings)
    engine = engine or BacktestEngine()
    start_date = start_date or DEFAULT_OPTIMIZE_START_DATE
    end_date = end_date or DEFAULT_OPTIMIZE_END_DATE
    base_config = build_base_config(settings)

    signals = repository.fetch_signals(
        start_date=start_date,
        end_date=end_date,
        strategy=None,
        symbols=symbols,
        limit=None,
        require_market_regime=False,
    )
    price_horizon = max(
        base_config.max_hold_days,
        *(int(value) for value in STAGE2_VALUES["max_hold_days"]),
    )
    prices_by_symbol = repository.fetch_prices_for_signals(
        signals,
        end_date=None,
        max_hold_days=price_horizon,
        benchmark_symbol=base_config.benchmark_symbol,
    )

    signal_cache = {
        option.key: _filter_signals(signals, option) for option in STRATEGY_OPTIONS
    }
    regime_candidates = signal_cache["market_regime"]
    regime_policy = (
        regime_policy_from_json(
            settings.swing_regime_policy_json,
            require_vix=settings.swing_require_vix,
            profile=settings.swing_regime_profile,
        )
        if regime_candidates
        else None
    )
    regime_by_date = (
        _build_regime_by_date(
            signals=regime_candidates,
            prices_by_symbol=prices_by_symbol,
            shared_market_repository=shared_market_repository
            or SharedMarketRepository(settings),
            settings=settings,
            benchmark_symbol=base_config.benchmark_symbol,
        )
        if regime_candidates
        else {}
    )

    seed_runs = repository.list_optimization_seed_runs(
        signal_start_date=start_date,
        signal_end_date=end_date,
        limit=RECENT_SEED_LIMIT,
    )
    seed_configs = _collect_seed_configs(base_config, seed_runs)

    stage1_candidates = _generate_stage_candidates(
        seed_configs=seed_configs,
        stage_values=STAGE1_VALUES,
        include_all_strategies=True,
    )
    stage1_evaluations = _evaluate_candidates(
        candidates=stage1_candidates,
        signal_cache=signal_cache,
        prices_by_symbol=prices_by_symbol,
        regime_by_date=regime_by_date,
        regime_policy=regime_policy,
        engine=engine,
    )
    survivors = _select_survivors(stage1_evaluations)

    stage2_candidates = _generate_followup_candidates(
        survivors=survivors,
        stage_values=STAGE2_VALUES,
    )
    final_evaluations = _evaluate_candidates(
        candidates=stage2_candidates,
        signal_cache=signal_cache,
        prices_by_symbol=prices_by_symbol,
        regime_by_date=regime_by_date,
        regime_policy=regime_policy,
        engine=engine,
    )

    winners = _select_winners(final_evaluations)
    saved_runs = []
    if persist_winners:
        saved_runs = _persist_winners(repository, winners)

    return {
        "ok": True,
        "persist_winners": persist_winners,
        "search_window": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "symbols": symbols or [],
        },
        "signal_count": len(signals),
        "stage0_seed_count": len(seed_configs),
        "stage1_candidate_count": len(stage1_candidates),
        "stage1_survivor_count": len(survivors),
        "stage2_candidate_count": len(stage2_candidates),
        "eligible_candidate_count": len(
            [evaluation for evaluation in final_evaluations if evaluation.eligible]
        ),
        "winners": {
            "overall_best": winners.get("overall_best").summary()
            if winners.get("overall_best")
            else None,
            "best_cagr": winners.get("best_cagr").summary()
            if winners.get("best_cagr")
            else None,
            "least_mdd": winners.get("least_mdd").summary()
            if winners.get("least_mdd")
            else None,
        },
        "saved_runs": saved_runs,
    }


def build_base_config(settings: Settings) -> BacktestConfig:
    defaults = BacktestConfig()
    return BacktestConfig(
        initial_equity=settings.swing_account_equity,
        fee_bps=settings.swing_fee_bps,
        slippage_bps=settings.swing_slippage_bps,
        max_hold_days=settings.swing_default_max_hold_days,
        max_positions=settings.swing_max_positions,
        max_gross_exposure_pct=settings.swing_max_gross_exposure_pct,
        max_position_pct=settings.swing_max_position_pct,
        max_portfolio_risk_pct=defaults.max_portfolio_risk_pct,
        pullback_size_multiplier=settings.swing_pullback_size_multiplier,
        benchmark_symbol=settings.swing_benchmark_symbol.upper(),
        enable_trailing_stop=settings.swing_enable_trailing_stop,
        target_scale_out_pct=settings.swing_target_scale_out_pct,
        trailing_ma_days=settings.swing_trailing_ma_days,
        enable_breakeven_stop=defaults.enable_breakeven_stop,
        breakeven_r_multiple=defaults.breakeven_r_multiple,
        failed_trade_exit_days=defaults.failed_trade_exit_days,
        failed_trade_min_r_multiple=defaults.failed_trade_min_r_multiple,
    )


def _build_regime_by_date(
    *,
    signals: Sequence[BacktestSignal],
    prices_by_symbol: Mapping[str, Sequence[PriceBar]],
    shared_market_repository: SharedMarketRepository,
    settings: Settings,
    benchmark_symbol: str,
) -> dict[date, str]:
    price_dates = sorted(
        {
            bar.trade_date
            for symbol, bars in prices_by_symbol.items()
            if symbol != benchmark_symbol
            for bar in bars
            if getattr(bar, "trade_date", None) is not None
        }
    )
    if not price_dates or not signals:
        return {}
    start_date = min(price_dates[0], min(signal.signal_date for signal in signals))
    from swing_trading_system.market_regime import classify_market_regime

    history_start = start_date - timedelta(days=400)
    benchmark_rows = shared_market_repository.fetch_daily_prices(
        benchmark_symbol,
        start_date=history_start,
        end_date=price_dates[-1],
        limit=2_000,
    )
    benchmark_series = shared_market_repository.fetch_benchmark_series(
        [settings.swing_vix_benchmark_name],
        start_date=history_start,
        end_date=price_dates[-1],
        limit=2_000,
    )
    vix_rows = benchmark_series.get(settings.swing_vix_benchmark_name, [])
    return {
        price_date: classify_market_regime(
            benchmark_rows=benchmark_rows,
            vix_rows=vix_rows,
            as_of_date=price_date,
            require_vix=settings.swing_require_vix,
        ).regime_id.value
        for price_date in price_dates
    }


def _collect_seed_configs(
    base_config: BacktestConfig, seed_runs: Sequence[dict[str, Any]]
) -> list[BacktestConfig]:
    configs = [base_config]
    seen = {_config_key(base_config)}
    for seed_run in seed_runs:
        config = _seed_config_from_summary(base_config, seed_run.get("config"))
        if config is None:
            continue
        key = _config_key(config)
        if key in seen:
            continue
        seen.add(key)
        configs.append(config)
    return configs


def _seed_config_from_summary(
    base_config: BacktestConfig, value: object
) -> BacktestConfig | None:
    if not isinstance(value, dict):
        return None
    payload = base_config.to_dict()
    for field in payload:
        if field in value and value[field] is not None:
            payload[field] = value[field]
    payload["benchmark_symbol"] = str(payload["benchmark_symbol"]).upper()
    try:
        return BacktestConfig(**payload)
    except (TypeError, ValueError):
        return None


def _generate_stage_candidates(
    *,
    seed_configs: Sequence[BacktestConfig],
    stage_values: Mapping[str, Sequence[object]],
    include_all_strategies: bool,
) -> list[OptimizationCandidate]:
    candidates: list[OptimizationCandidate] = []
    strategy_keys = [option.key for option in STRATEGY_OPTIONS] if include_all_strategies else []
    for seed_config in seed_configs:
        for strategy_key in strategy_keys:
            candidates.append(OptimizationCandidate(strategy_key, seed_config))
            # Sweep one dimension at a time to keep the search tractable.
            for field_name, values in stage_values.items():
                for value in values:
                    candidates.append(
                        OptimizationCandidate(
                            strategy=strategy_key,
                            config=_replace_config(seed_config, field_name, value),
                        )
                    )
    return _dedupe_candidates(candidates)


def _generate_followup_candidates(
    *,
    survivors: Sequence[CandidateEvaluation],
    stage_values: Mapping[str, Sequence[object]],
) -> list[OptimizationCandidate]:
    candidates: list[OptimizationCandidate] = []
    for survivor in survivors:
        candidates.append(survivor.candidate)
        for field_name, values in stage_values.items():
            for value in values:
                candidates.append(
                    OptimizationCandidate(
                        strategy=survivor.candidate.strategy,
                        config=_replace_config(
                            survivor.candidate.config, field_name, value
                        ),
                    )
                )
    return _dedupe_candidates(candidates)


def _evaluate_candidates(
    *,
    candidates: Sequence[OptimizationCandidate],
    signal_cache: Mapping[str, list[BacktestSignal]],
    prices_by_symbol: Mapping[str, Sequence[PriceBar]],
    regime_by_date: Mapping[date, str],
    regime_policy: object,
    engine: BacktestEngine,
) -> list[CandidateEvaluation]:
    evaluations: list[CandidateEvaluation] = []
    for candidate in candidates:
        selection = STRATEGY_BY_KEY[candidate.strategy]
        selected_signals = signal_cache.get(candidate.strategy, [])
        result = engine.run(
            signals=selected_signals,
            prices_by_symbol=prices_by_symbol,
            config=candidate.config,
            regime_by_date=regime_by_date if selection.require_market_regime else {},
            regime_policy=regime_policy if selection.require_market_regime else None,
        )
        result.metrics["strategy_selection"] = candidate.strategy
        evaluations.append(CandidateEvaluation(candidate=candidate, result=result))
    return evaluations


def _filter_signals(
    signals: Sequence[BacktestSignal], selection: StrategySelection
) -> list[BacktestSignal]:
    if selection.require_market_regime:
        return [signal for signal in signals if _signal_has_market_regime(signal)]
    if selection.allowed_strategies is None:
        return list(signals)
    return [
        signal for signal in signals if signal.strategy in selection.allowed_strategies
    ]


def _signal_has_market_regime(signal: BacktestSignal) -> bool:
    details = signal.details if isinstance(signal.details, dict) else {}
    direct = details.get("market_regime")
    if isinstance(direct, dict) and direct.get("regime_id"):
        return True
    features = details.get("features")
    if isinstance(features, dict):
        market_regime = features.get("market_regime")
        if isinstance(market_regime, dict) and market_regime.get("regime_id"):
            return True
    return False


def _select_survivors(
    evaluations: Sequence[CandidateEvaluation],
) -> list[CandidateEvaluation]:
    eligible = [evaluation for evaluation in evaluations if evaluation.eligible]
    if not eligible:
        return []
    survivors: list[CandidateEvaluation] = []
    seen: set[str] = set()
    for evaluation in (
        sorted(eligible, key=_overall_sort_key)[:10]
        + sorted(eligible, key=_best_cagr_sort_key)[:5]
        + sorted(eligible, key=_least_mdd_sort_key)[:5]
    ):
        key = _candidate_key(evaluation.candidate)
        if key in seen:
            continue
        seen.add(key)
        survivors.append(evaluation)
    return survivors


def _select_winners(
    evaluations: Sequence[CandidateEvaluation],
) -> dict[str, CandidateEvaluation | None]:
    eligible = [evaluation for evaluation in evaluations if evaluation.eligible]
    if not eligible:
        return {
            "overall_best": None,
            "best_cagr": None,
            "least_mdd": None,
        }
    return {
        "overall_best": sorted(eligible, key=_overall_sort_key)[0],
        "best_cagr": sorted(eligible, key=_best_cagr_sort_key)[0],
        "least_mdd": sorted(eligible, key=_least_mdd_sort_key)[0],
    }


def _persist_winners(
    repository: BacktestRepository,
    winners: Mapping[str, CandidateEvaluation | None],
) -> list[dict[str, Any]]:
    saved_runs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for category, evaluation in winners.items():
        if evaluation is None or evaluation.result.run_id in seen:
            continue
        seen.add(evaluation.result.run_id)
        saved_runs.append(
            {
                "category": category,
                "run_id": evaluation.result.run_id,
                **repository.save_result(evaluation.result),
            }
        )
    return saved_runs


def _replace_config(
    config: BacktestConfig, field_name: str, value: object
) -> BacktestConfig:
    payload = config.to_dict()
    payload[field_name] = value
    return BacktestConfig(**payload)


def _dedupe_candidates(
    candidates: Sequence[OptimizationCandidate],
) -> list[OptimizationCandidate]:
    deduped: list[OptimizationCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = _candidate_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _candidate_key(candidate: OptimizationCandidate) -> str:
    return json.dumps(
        {"strategy": candidate.strategy, "config": candidate.config.to_dict()},
        sort_keys=True,
    )


def _config_key(config: BacktestConfig) -> str:
    return json.dumps(config.to_dict(), sort_keys=True)


def _overall_sort_key(evaluation: CandidateEvaluation) -> tuple[float, float, float]:
    metrics = evaluation.metrics
    return (
        -_metric(metrics, "calmar_ratio", -inf),
        -_metric(metrics, "cagr", -inf),
        abs(_metric(metrics, "max_drawdown", inf)),
    )


def _best_cagr_sort_key(
    evaluation: CandidateEvaluation,
) -> tuple[float, float, int]:
    metrics = evaluation.metrics
    return (
        -_metric(metrics, "cagr", -inf),
        abs(_metric(metrics, "max_drawdown", inf)),
        -evaluation.trade_count,
    )


def _least_mdd_sort_key(
    evaluation: CandidateEvaluation,
) -> tuple[float, float, int]:
    metrics = evaluation.metrics
    return (
        abs(_metric(metrics, "max_drawdown", inf)),
        -_metric(metrics, "cagr", -inf),
        -evaluation.trade_count,
    )


def _metric(metrics: Mapping[str, Any], key: str, default: float) -> float:
    try:
        value = metrics.get(key)
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default
