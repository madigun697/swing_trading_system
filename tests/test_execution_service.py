from decimal import Decimal

from swing_trading_system.execution.service import PaperExecutionService


class FakeSwingRepository:
    def __init__(self) -> None:
        self.submitting: list[int] = []
        self.updated: list[tuple[int, str | None, str, bool]] = []

    def list_ready_trade_plans(self, limit: int = 20):
        return [
            {"trade_plan_id": 1, "symbol": "AAA", "quantity": Decimal("10"), "side": "buy"},
            {"trade_plan_id": 2, "symbol": "BBB", "quantity": Decimal("5"), "side": "buy"},
        ]

    def mark_trade_plan_submitting(self, trade_plan_id: int) -> None:
        self.submitting.append(trade_plan_id)

    def mark_trade_plan_execution_result(self, trade_plan_id: int, broker_order_id: str | None, broker_status: str, *, submitted: bool) -> None:
        self.updated.append((trade_plan_id, broker_order_id, broker_status, submitted))


class FakeClient:
    def __init__(self, settings) -> None:
        pass

    def submit_orders(self, requests):
        from swing_trading_system.execution.alpaca import OrderResult
        return [
            OrderResult(1, "AAA", "submitted", "ord-1"),
            OrderResult(2, "BBB", "error", None, "rejected"),
        ]


def test_execute_dry_run(monkeypatch) -> None:
    service = PaperExecutionService(swing_repository=FakeSwingRepository())
    result = service.execute(submit=False)
    assert result["submitted"] is False
    assert len(result["orders"]) == 2


def test_execute_marks_partial_results(monkeypatch) -> None:
    fake_repo = FakeSwingRepository()
    monkeypatch.setattr("swing_trading_system.execution.service.AlpacaClient", FakeClient)
    service = PaperExecutionService(swing_repository=fake_repo)
    result = service.execute(submit=True)
    assert result["ok"] is False
    assert fake_repo.submitting == [1, 2]
    assert fake_repo.updated == [
        (1, "ord-1", "submitted", True),
        (2, None, "error:rejected", False),
    ]
