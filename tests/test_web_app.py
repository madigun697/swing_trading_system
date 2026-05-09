from fastapi.testclient import TestClient

from swing_trading_system.domain import ReadinessStatus
from swing_trading_system.web.app import AppServices, create_app


class FakeSharedRepository:
    def check_readiness(self):
        return ReadinessStatus(True, "ok", "ready")


class FakeSwingRepository:
    def list_latest_candidates(self, strategy_id=None, limit=25):
        return []

    def list_latest_backtests(self, limit=5):
        return []

    def list_recent_alerts(self, limit=10):
        return []

    def list_ready_trade_plans(self, limit=10):
        return []

    def list_open_positions(self):
        return []


class FakeOrchestrator:
    def run_screen(self, **kwargs):
        return {"ok": True}

    def run_backtest(self, **kwargs):
        return {"ok": True}


class FakeExecutionService:
    def execute(self, *, submit: bool, limit: int = 20):
        return {"ok": True, "submitted": submit}


def test_healthz_endpoint() -> None:
    app = create_app(AppServices(FakeSharedRepository(), FakeSwingRepository(), FakeOrchestrator(), FakeExecutionService()))
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["code"] == "ok"
