from __future__ import annotations

from datetime import date

from swing_trading_system.backtest.models import (
    BacktestConfig,
    BacktestResult,
    BacktestSignal,
    BacktestTrade,
)
from swing_trading_system.backtest.optimizer import (
    CandidateEvaluation,
    OptimizationCandidate,
    STRATEGY_BY_KEY,
    _collect_seed_configs,
    _filter_signals,
    _select_survivors,
    _select_winners,
    build_base_config,
    optimize_backtest,
)
from swing_trading_system.config import Settings


def _signal(
    signal_id: int,
    strategy: str,
    *,
    with_regime: bool = False,
) -> BacktestSignal:
    details = {"market_regime": {"regime_id": "R2_VOLATILE_BULL"}} if with_regime else {}
    return BacktestSignal(
        id=signal_id,
        symbol=f"S{signal_id}",
        signal_date=date(2025, 1, 2),
        strategy=strategy,
        entry_price=100.0,
        stop_price=95.0,
        target_price=110.0,
        risk_per_share=5.0,
        position_size=10.0,
        details=details,
    )


def _trade(signal_id: int) -> BacktestTrade:
    return BacktestTrade(
        run_id="r",
        signal_id=signal_id,
        symbol="AAA",
        strategy="pullback",
        entry_date=date(2025, 1, 3),
        exit_date=date(2025, 1, 10),
        entry_price=100.0,
        exit_price=101.0,
        quantity=1.0,
        pnl=1.0,
        exit_reason="target",
        details={},
    )


def _evaluation(
    *,
    strategy: str,
    cagr: float,
    mdd: float,
    calmar: float | None,
    trade_count: int,
    signal_count: int = 100,
) -> CandidateEvaluation:
    config = BacktestConfig()
    result = BacktestResult(
        run_id=f"{strategy}-{trade_count}-{cagr}",
        config=config,
        trades=tuple(_trade(index) for index in range(trade_count)),
        equity_curve=(),
        rejections=(),
        metrics={
            "cagr": cagr,
            "max_drawdown": mdd,
            "calmar_ratio": calmar,
            "total_return": cagr,
            "rejection_count": 0,
        },
        signal_count=signal_count,
        signal_start_date=date(2025, 1, 2),
        signal_end_date=date(2026, 5, 1),
    )
    return CandidateEvaluation(
        candidate=OptimizationCandidate(strategy=strategy, config=config),
        result=result,
    )


def test_collect_seed_configs_dedupes_identical_configs() -> None:
    base = BacktestConfig(max_positions=10)
    seeds = [
        {"config": base.to_dict()},
        {"config": BacktestConfig(max_positions=20).to_dict()},
        {"config": BacktestConfig(max_positions=20).to_dict()},
    ]

    configs = _collect_seed_configs(base, seeds)

    assert [config.max_positions for config in configs] == [10, 20]


def test_filter_signals_supports_strategy_and_market_regime() -> None:
    signals = [
        _signal(1, "breakout"),
        _signal(2, "pullback", with_regime=True),
        _signal(3, "quality_momentum", with_regime=True),
    ]

    breakout_only = _filter_signals(signals, STRATEGY_BY_KEY["breakout"])
    combo = _filter_signals(signals, STRATEGY_BY_KEY["pullback+quality_momentum"])
    regime_only = _filter_signals(signals, STRATEGY_BY_KEY["market_regime"])

    assert [signal.strategy for signal in breakout_only] == ["breakout"]
    assert [signal.strategy for signal in combo] == [
        "pullback",
        "quality_momentum",
    ]
    assert [signal.strategy for signal in regime_only] == [
        "pullback",
        "quality_momentum",
    ]


def test_select_winners_and_survivors_use_eligibility_and_tiebreaks() -> None:
    evaluations = [
        _evaluation(
            strategy="best-cagr-low-mdd",
            cagr=0.25,
            mdd=-0.08,
            calmar=3.125,
            trade_count=35,
        ),
        _evaluation(
            strategy="best-cagr-high-mdd",
            cagr=0.25,
            mdd=-0.12,
            calmar=2.08,
            trade_count=40,
        ),
        _evaluation(
            strategy="least-mdd-ineligible",
            cagr=0.01,
            mdd=0.0,
            calmar=None,
            trade_count=10,
        ),
        _evaluation(
            strategy="least-mdd-eligible",
            cagr=0.12,
            mdd=-0.03,
            calmar=4.0,
            trade_count=30,
        ),
    ]

    winners = _select_winners(evaluations)
    survivors = _select_survivors(evaluations)

    assert winners["best_cagr"] is not None
    assert winners["best_cagr"].candidate.strategy == "best-cagr-low-mdd"
    assert winners["least_mdd"] is not None
    assert winners["least_mdd"].candidate.strategy == "least-mdd-eligible"
    assert all(survivor.eligible for survivor in survivors)


class _FakeRepository:
    def __init__(self) -> None:
        self.saved_run_ids: list[str] = []

    def fetch_signals(
        self,
        start_date=None,
        end_date=None,
        strategy=None,
        symbols=None,
        limit=None,
        require_market_regime=False,
    ):
        return [
            _signal(1, "breakout"),
            _signal(2, "pullback"),
            _signal(3, "quality_momentum"),
            _signal(4, "breakout"),
        ]

    def fetch_prices_for_signals(
        self, signals, end_date=None, max_hold_days=20, benchmark_symbol=None
    ):
        return {}

    def list_optimization_seed_runs(
        self,
        signal_start_date,
        signal_end_date,
        limit=5,
    ):
        return [
            {"config": build_base_config(Settings(_env_file=None)).to_dict()},
            {"config": BacktestConfig(max_positions=20).to_dict()},
        ]

    def save_result(self, result):
        self.saved_run_ids.append(result.run_id)
        return {"trades_saved": len(result.trades), "equity_points_saved": 0, "summary_saved": 1}


class _FakeEngine:
    def run(
        self,
        signals,
        prices_by_symbol,
        config,
        run_id=None,
        regime_by_date=None,
        regime_policy=None,
    ):
        strategy_key = self._strategy_key(signals, regime_policy)
        cagr = self._cagr(strategy_key, config)
        mdd = self._mdd(strategy_key, config)
        calmar = None if mdd == 0 else cagr / abs(mdd)
        trade_count = self._trade_count(strategy_key)
        run_id = (
            f"{strategy_key}-{config.max_positions}-{config.max_portfolio_risk_pct}-"
            f"{config.max_hold_days}-{config.target_scale_out_pct}"
        )
        return BacktestResult(
            run_id=run_id,
            config=config,
            trades=tuple(_trade(index) for index in range(trade_count)),
            equity_curve=(),
            rejections=(),
            metrics={
                "cagr": round(cagr, 6),
                "max_drawdown": round(mdd, 6),
                "calmar_ratio": round(calmar, 6) if calmar is not None else None,
                "total_return": round(cagr, 6),
                "rejection_count": 0,
            },
            signal_count=len(signals),
            signal_start_date=date(2025, 1, 2),
            signal_end_date=date(2026, 5, 1),
        )

    def _strategy_key(self, signals, regime_policy) -> str:
        if not signals:
            return "market_regime" if regime_policy is not None else "empty"
        if regime_policy is not None:
            return "market_regime"
        strategies = sorted({signal.strategy for signal in signals})
        if strategies == ["breakout", "pullback", "quality_momentum"]:
            return "all_signals"
        return "+".join(strategies)

    def _trade_count(self, strategy_key: str) -> int:
        return {
            "market_regime": 0,
            "all_signals": 42,
            "breakout": 35,
            "pullback": 38,
            "quality_momentum": 40,
            "breakout+pullback": 41,
            "breakout+quality_momentum": 45,
            "pullback+quality_momentum": 39,
        }.get(strategy_key, 36)

    def _cagr(self, strategy_key: str, config: BacktestConfig) -> float:
        base = {
            "all_signals": 0.12,
            "breakout": 0.10,
            "pullback": 0.09,
            "quality_momentum": 0.15,
            "breakout+pullback": 0.11,
            "breakout+quality_momentum": 0.18,
            "pullback+quality_momentum": 0.13,
            "market_regime": 0.0,
            "empty": 0.0,
        }[strategy_key]
        if config.max_positions == 20:
            base += 0.03
        if config.max_portfolio_risk_pct == 0.04:
            base -= 0.01
        if config.max_hold_days == 40:
            base += 0.025
        if config.target_scale_out_pct == 0.75:
            base -= 0.01
        return base

    def _mdd(self, strategy_key: str, config: BacktestConfig) -> float:
        base = {
            "all_signals": -0.10,
            "breakout": -0.09,
            "pullback": -0.06,
            "quality_momentum": -0.08,
            "breakout+pullback": -0.09,
            "breakout+quality_momentum": -0.11,
            "pullback+quality_momentum": -0.075,
            "market_regime": 0.0,
            "empty": 0.0,
        }[strategy_key]
        if config.max_positions == 20:
            base -= 0.01
        if config.max_portfolio_risk_pct == 0.04:
            base += 0.03
        if config.max_hold_days == 40:
            base -= 0.005
        if config.target_scale_out_pct == 0.75:
            base += 0.02
        return base


def test_optimize_backtest_returns_expected_winners_and_persists_unique_runs() -> None:
    repository = _FakeRepository()
    payload = optimize_backtest(
        settings=Settings(_env_file=None),
        start_date=date(2025, 1, 2),
        end_date=date(2026, 5, 1),
        persist_winners=True,
        repository=repository,
        engine=_FakeEngine(),
    )

    winners = payload["winners"]

    assert winners["overall_best"]["strategy"] == "pullback"
    assert winners["overall_best"]["config"]["max_portfolio_risk_pct"] == 0.04
    assert winners["best_cagr"]["strategy"] == "breakout+quality_momentum"
    assert winners["best_cagr"]["config"]["max_hold_days"] == 40
    assert winners["least_mdd"]["strategy"] == "pullback"
    assert winners["least_mdd"]["config"]["max_portfolio_risk_pct"] == 0.04
    assert len(repository.saved_run_ids) == 2
