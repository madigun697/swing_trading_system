from fastapi.testclient import TestClient

from swing_trading_system.repositories.shared_market import ReadinessStatus
from swing_trading_system.web.app import create_app


class FakeRepository:
    def __init__(self, status: ReadinessStatus) -> None:
        self.status = status

    def check_readiness(self) -> ReadinessStatus:
        return self.status


def test_healthz_ok() -> None:
    app = create_app(FakeRepository(ReadinessStatus(ok=True, code="ready", detail="ok")))
    response = TestClient(app).get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["code"] == "ready"


def test_healthz_unavailable() -> None:
    app = create_app(FakeRepository(ReadinessStatus(ok=False, code="missing_relation", detail="missing")))
    response = TestClient(app).get("/healthz")

    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    assert response.json()["code"] == "missing_relation"
