from datetime import date

from fastapi.testclient import TestClient

from swing_trading_system.backtest.models import BacktestSignal
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


class FakeBacktestRepository:
    def count_signals(self):
        return 1

    def list_recent_runs(self, limit=20):
        return [{"run_id": "r1", "trade_count": 1, "total_pnl": 10, "start_date": date(2026, 1, 2), "end_date": date(2026, 1, 3)}]

    def fetch_signals(self, limit=100, **kwargs):
        return [BacktestSignal(1, "AAA", date(2026, 1, 1), "pullback", 100, 95, 110, 5, 10)]

    def fetch_run_trades(self, run_id):
        return [{"run_id": run_id, "symbol": "AAA", "pnl": 10}, {"run_id": run_id, "symbol": "BAD", "pnl": "not-a-number"}]

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
            },
            "config": {"fee_bps": 2, "slippage_bps": 10, "max_hold_days": 30, "max_positions": 5, "max_gross_exposure_pct": 1.0},
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
    assert c.get("/backtests").status_code == 200
    assert "r1" in c.get("/backtests").text
    detail = c.get("/backtests/r1")
    assert detail.status_code == 200
    assert "Executive Summary" in detail.text
    assert "Symbol Contribution" in detail.text
    assert c.get("/static/css/app.css").status_code == 200


def test_index_renders_degraded_state_when_dependencies_fail() -> None:
    c = TestClient(create_app(UnavailableSharedRepository(), FailingBacktestRepository()))
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
