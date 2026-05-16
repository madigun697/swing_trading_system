from datetime import date

from fastapi.testclient import TestClient

from swing_trading_system.backtest.models import BacktestSignal, PriceBar
from swing_trading_system.repositories.shared_market import ReadinessStatus
from swing_trading_system.web.app import create_app


class FakeSharedRepository:
    def check_readiness(self):
        return ReadinessStatus(True, "ready", "ok")

    def fetch_latest_trade_date(self):
        return date(2026, 1, 2)


class UnavailableSharedRepository:
    def check_readiness(self):
        return ReadinessStatus(False, "missing_relation", "missing")

    def fetch_latest_trade_date(self):
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
        return [{"run_id": run_id, "equity_date": date(2026, 1, 3), "equity": 100010}]

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
                "benchmark_symbol": "SPY",
                "enable_trailing_stop": True,
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
    assert "Regime Slice" in detail.text
    assert "regime-aware" in detail.text
    assert "Symbol Contribution" in detail.text
    assert "Monthly Slice" in detail.text
    assert "Sector Slice" in detail.text
    assert "Sharpe" in detail.text
    assert c.get("/backtests/run").status_code == 200
    assert "백테스트 실행" in c.get("/backtests/run").text
    assert "Market Regime Switching" in c.get("/backtests/run").text
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
