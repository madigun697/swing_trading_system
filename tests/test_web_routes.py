from datetime import date, timedelta

from fastapi.testclient import TestClient

from swing_trading_system.backtest.models import BacktestSignal, PriceBar
from swing_trading_system.repositories.shared_market import ReadinessStatus
from swing_trading_system.web.app import create_app


class FakeSharedRepository:
    def check_readiness(self):
        return ReadinessStatus(True, "ready", "ok")

    def fetch_latest_trade_date(self):
        return date(2026, 1, 2)

    def fetch_sector_by_symbol_and_date(self, requests):
        sector_map = {
            ("AAA", date(2026, 1, 1)): "Technology",
        }
        return {
            request: sector_map[request]
            for request in requests
            if request in sector_map
        }

    def fetch_daily_prices(self, symbol, start_date=None, end_date=None, limit=500):
        if symbol != "SPY":
            return []
        return [
            *[
                {
                    "symbol": "SPY",
                    "trade_date": date(2025, 6, 1) + timedelta(days=offset),
                    "close": 100.0,
                }
                for offset in range(205)
            ],
            {
                "symbol": "SPY",
                "trade_date": date(2025, 12, 23),
                "close": 103.0,
            },
            {
                "symbol": "SPY",
                "trade_date": date(2025, 12, 24),
                "close": 105.0,
            },
            {
                "symbol": "SPY",
                "trade_date": date(2025, 12, 25),
                "close": 107.0,
            },
            {
                "symbol": "SPY",
                "trade_date": date(2025, 12, 26),
                "close": 109.0,
            },
            {
                "symbol": "SPY",
                "trade_date": date(2025, 12, 27),
                "close": 110.0,
            },
            {
                "symbol": "SPY",
                "trade_date": date(2025, 12, 28),
                "close": 111.0,
            },
            {
                "symbol": "SPY",
                "trade_date": date(2025, 12, 29),
                "close": 112.0,
            },
            {
                "symbol": "SPY",
                "trade_date": date(2025, 12, 30),
                "close": 113.0,
            },
            {
                "symbol": "SPY",
                "trade_date": date(2025, 12, 31),
                "close": 114.0,
            },
            {
                "symbol": "SPY",
                "trade_date": date(2026, 1, 1),
                "close": 115.0,
            },
            {
                "symbol": "SPY",
                "trade_date": date(2026, 1, 2),
                "close": 116.0,
            },
            {
                "symbol": "SPY",
                "trade_date": date(2026, 1, 3),
                "close": 117.0,
            },
        ]

    def fetch_benchmark_series(
        self, benchmark_names, start_date=None, end_date=None, limit=2000
    ):
        return {
            benchmark_name: [
                {
                    "benchmark_name": benchmark_name,
                    "observation_date": date(2026, 1, 2),
                    "value": 22.0,
                    "source": "test",
                },
                {
                    "benchmark_name": benchmark_name,
                    "observation_date": date(2026, 1, 3),
                    "value": 21.0,
                    "source": "test",
                },
            ]
            for benchmark_name in benchmark_names
        }


class UnavailableSharedRepository:
    def check_readiness(self):
        return ReadinessStatus(False, "missing_relation", "missing")

    def fetch_latest_trade_date(self):
        raise RuntimeError("shared data unavailable")

    def fetch_sector_by_symbol_and_date(self, requests):
        raise RuntimeError("shared data unavailable")

    def fetch_daily_prices(self, symbol, start_date=None, end_date=None, limit=500):
        raise RuntimeError("shared data unavailable")

    def fetch_benchmark_series(
        self, benchmark_names, start_date=None, end_date=None, limit=2000
    ):
        raise RuntimeError("shared data unavailable")


class FailingBacktestRepository:
    def count_signals(self):
        raise RuntimeError("db unavailable")

    def list_recent_runs(self, limit=20):
        raise RuntimeError("db unavailable")

    def fetch_signals(self, limit=100, **kwargs):
        raise RuntimeError("db unavailable")

    def fetch_run_trades(self, run_id):
        raise RuntimeError("db unavailable")

    def fetch_run_equity_curve(self, run_id):
        raise RuntimeError("db unavailable")

    def fetch_run_summary(self, run_id):
        raise RuntimeError("db unavailable")


class FakeBacktestRepository:
    def __init__(self) -> None:
        self.saved_run_id = None

    def count_signals(self):
        return 1

    def list_recent_runs(self, limit=20):
        return [
            {
                "run_id": "r1",
                "trade_count": 1,
                "total_pnl": 10,
                "start_date": date(2026, 1, 2),
                "end_date": date(2026, 1, 3),
            }
        ]

    def fetch_signals(self, limit=100, **kwargs):
        return [
            BacktestSignal(
                1,
                "AAA",
                date(2026, 1, 1),
                "pullback",
                100,
                95,
                110,
                5,
                10,
                details={
                    "market_regime": {
                        "regime_id": "R2_VOLATILE_BULL",
                        "reason": "volatile_bull_above_ma200",
                    }
                },
            )
        ]

    def fetch_prices_for_signals(
        self, signals, end_date=None, max_hold_days=20, benchmark_symbol=None
    ):
        return {
            "AAA": [
                PriceBar("AAA", date(2026, 1, 2), 100, 101, 99, 100, 1000),
                PriceBar("AAA", date(2026, 1, 3), 100, 111, 99, 110, 1000),
            ],
            "SPY": [
                PriceBar("SPY", date(2026, 1, 2), 100, 100, 100, 100, 1000),
                PriceBar("SPY", date(2026, 1, 3), 101, 101, 101, 101, 1000),
            ],
        }

    def save_result(self, result):
        self.saved_run_id = result.run_id
        return {
            "trades_saved": len(result.trades),
            "equity_points_saved": len(result.equity_curve),
            "summary_saved": 1,
        }

    def fetch_run_trades(self, run_id):
        return [
            {
                "run_id": run_id,
                "symbol": "AAA",
                "pnl": 10,
                "details": {
                    "signal": {
                        "strategy": "pullback",
                        "signal_date": date(2026, 1, 1),
                        "entry_price": 100,
                        "stop_price": 95,
                        "target_price": 110,
                        "details": {
                            "market_regime": {
                                "regime_id": "R2_VOLATILE_BULL",
                                "reason": "volatile_bull_above_ma200",
                            }
                        },
                    },
                    "entry_notional": 1000,
                    "strategy": "pullback",
                    "exit_reason": "target",
                },
            },
            {
                "run_id": run_id,
                "symbol": "BAD",
                "pnl": "not-a-number",
                "details": {
                    "signal": {
                        "strategy": "breakout",
                        "details": {
                            "market_regime": None,
                            "features": {"market_regime": None},
                        },
                    }
                },
            },
        ]

    def fetch_run_equity_curve(self, run_id):
        return [
            {
                "run_id": run_id,
                "equity_date": date(2026, 1, 2),
                "equity": 100000,
                "details": {"benchmark_equity": 100000},
            },
            {
                "run_id": run_id,
                "equity_date": date(2026, 1, 3),
                "equity": 100010,
                "details": {"benchmark_equity": 101000},
            },
        ]

    def fetch_run_summary(self, run_id):
        return {
            "run_id": run_id,
            "start_date": date(2026, 1, 2),
            "end_date": date(2026, 1, 3),
            "initial_equity": 100000,
            "final_equity": 100010,
            "total_pnl": 10,
            "total_return": 0.0001,
            "max_drawdown": 0,
            "win_rate": 1,
            "profit_factor": None,
            "trade_count": 2,
            "rejection_count": 0,
            "metrics": {
                "symbol_contribution": {"AAA": 10},
                "strategy_contribution": {"pullback": 10},
                "benchmark_return": 0.01,
                "benchmark_mdd": 0,
                "benchmark_cagr": 1.0,
                "excess_return": -0.0099,
                "sharpe_ratio": 1.2,
                "cagr": 0.02,
                "calmar_ratio": 2,
                "average_hold_days": 1,
                "max_consecutive_wins": 1,
                "max_consecutive_losses": 0,
                "expectancy_per_dollar": 0.001,
            },
            "config": {
                "fee_bps": 2,
                "slippage_bps": 10,
                "max_hold_days": 30,
                "max_positions": 10,
                "max_position_pct": 0.125,
                "max_gross_exposure_pct": 1.1,
                "max_portfolio_risk_pct": 0.06,
                "pullback_size_multiplier": 1.25,
                "benchmark_symbol": "SPY",
                "target_scale_out_pct": 0.5,
                "trailing_ma_days": 10,
                "enable_trailing_stop": True,
                "enable_breakeven_stop": True,
                "failed_trade_exit_days": 6,
                "failed_trade_min_r_multiple": 0.5,
            },
            "rejections": [],
        }


def client():
    return TestClient(create_app(FakeSharedRepository(), FakeBacktestRepository()))


def test_index_signals_and_backtests_routes_render() -> None:
    c = client()

    assert c.get("/").status_code == 200
    assert "Signal count: 1" in c.get("/").text
    assert c.get("/signals").status_code == 200
    assert "AAA" in c.get("/signals").text
    assert "R2_VOLATILE_BULL" in c.get("/signals").text
    assert c.get("/backtests").status_code == 200
    assert "r1" in c.get("/backtests").text
    detail = c.get("/backtests/r1")
    assert detail.status_code == 200
    assert "Strategy vs SPY" in detail.text
    assert 'class="chart-legend"' in detail.text
    assert 'class="equity-chart-tooltip"' in detail.text
    assert 'data-date="2026-01-03"' in detail.text
    assert 'data-regime="R2_VOLATILE_BULL"' in detail.text
    assert "<span>Regime</span>" in detail.text
    assert "Regime Slice" in detail.text
    assert "regime-aware" in detail.text
    assert "Symbol Contribution" in detail.text
    assert "Monthly Slice" in detail.text
    assert "Sector Slice" in detail.text
    assert "Technology" in detail.text
    assert '<details class="panel-card collapsible-panel">' in detail.text
    assert "collapsible-summary" in detail.text
    assert "Sharpe" in detail.text
    assert "Portfolio Heat" in detail.text
    assert "Pullback Size Multiplier" in detail.text
    assert "Failed Exit Days" in detail.text
    assert "Failed Exit R" in detail.text
    assert "Breakeven Stop" in detail.text
    assert "사용" in detail.text
    assert 'title="열린 포지션의 초기 손절 위험 합계 한도입니다. 0.06은 초기자본의 6%입니다."' in detail.text
    assert c.get("/backtests/run").status_code == 200
    run_page = c.get("/backtests/run")
    assert "백테스트 실행" in run_page.text
    assert "Market Regime Switching" in run_page.text
    assert 'title="백테스트에 포함할 signal 탐색 시작일입니다."' in run_page.text
    assert 'title="Pullback 전략 진입 수량에 적용하는 배율입니다."' in run_page.text
    assert 'title="+1R 도달 후 손절선을 진입가로 올려 손실 거래 전환을 줄입니다."' in run_page.text
    assert c.get("/static/css/app.css").status_code == 200


def test_backtest_run_form_validates_and_redirects() -> None:
    c = client()

    invalid = c.post("/backtests/run", data={"start_date": "bad-date"})
    assert invalid.status_code == 422
    assert "YYYY-MM-DD" in invalid.text

    valid = c.post(
        "/backtests/run",
        data={"start_date": "2026-01-01", "end_date": "2026-01-01"},
        follow_redirects=False,
    )
    assert valid.status_code == 303
    assert "/backtests/" in valid.headers["location"]


def test_index_renders_degraded_state_when_dependencies_fail() -> None:
    c = TestClient(
        create_app(UnavailableSharedRepository(), FailingBacktestRepository())
    )
    response = c.get("/")

    assert response.status_code == 200
    assert "Dashboard warnings" in response.text
    assert "missing_relation" in response.text


def test_collection_routes_render_degraded_state_when_repository_fails() -> None:
    c = TestClient(create_app(FakeSharedRepository(), FailingBacktestRepository()))

    assert c.get("/signals").status_code == 200
    assert "Signals warnings" in c.get("/signals").text
    assert c.get("/backtests").status_code == 200
    assert "Backtests warnings" in c.get("/backtests").text
    assert c.get("/backtests/r1").status_code == 200
    assert "Backtest detail warnings" in c.get("/backtests/r1").text
    assert (
        c.post(
            "/backtests/run",
            data={"start_date": "2026-01-01", "end_date": "2026-01-01"},
        ).status_code
        == 503
    )


def test_backtest_detail_keeps_rendering_when_chart_regime_lookup_fails() -> None:
    c = TestClient(create_app(UnavailableSharedRepository(), FakeBacktestRepository()))

    detail = c.get("/backtests/r1")

    assert detail.status_code == 200
    assert "chart regime unavailable" in detail.text
    assert 'data-regime="-"' in detail.text
