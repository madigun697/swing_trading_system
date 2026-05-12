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


class FakeBacktestRepository:
    def count_signals(self):
        return 1

    def list_recent_runs(self, limit=20):
        return [{"run_id": "r1", "trade_count": 1, "total_pnl": 10, "start_date": date(2026, 1, 2), "end_date": date(2026, 1, 3)}]

    def fetch_signals(self, limit=100, **kwargs):
        return [BacktestSignal(1, "AAA", date(2026, 1, 1), "pullback", 100, 95, 110, 5, 10)]

    def fetch_run_trades(self, run_id):
        return [{"run_id": run_id, "symbol": "AAA", "pnl": 10}]

    def fetch_run_equity_curve(self, run_id):
        return [{"run_id": run_id, "equity_date": date(2026, 1, 3), "equity": 100010}]


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
    assert c.get("/backtests/r1").status_code == 200
