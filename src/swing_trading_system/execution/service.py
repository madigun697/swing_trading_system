from __future__ import annotations

from swing_trading_system.config import get_settings
from swing_trading_system.execution.alpaca import AlpacaClient, BatchOrderRequest, ConfigurationError
from swing_trading_system.repositories.swing_repository import SwingRepository


class PaperExecutionService:
    def __init__(self, swing_repository: SwingRepository | None = None) -> None:
        self.settings = get_settings()
        self.swing_repository = swing_repository or SwingRepository()

    def build_batch_requests(self, *, limit: int = 20) -> list[BatchOrderRequest]:
        plans = self.swing_repository.list_ready_trade_plans(limit=limit)
        requests: list[BatchOrderRequest] = []
        for plan in plans:
            if plan["quantity"] is None:
                continue
            trade_plan_id = int(plan["trade_plan_id"])
            requests.append(
                BatchOrderRequest(
                    trade_plan_id=trade_plan_id,
                    symbol=plan["symbol"],
                    qty=plan["quantity"],
                    side=plan["side"],
                    client_order_id=f"swing-{trade_plan_id}",
                )
            )
        return requests

    def execute(self, *, submit: bool, limit: int = 20) -> dict:
        batch = self.build_batch_requests(limit=limit)
        if not submit:
            return {
                "ok": True,
                "submitted": False,
                "orders": [request.__dict__ for request in batch],
            }
        try:
            client = AlpacaClient(self.settings)
        except ConfigurationError as exc:
            return {"ok": False, "submitted": False, "error": str(exc), "orders": []}
        for request in batch:
            self.swing_repository.mark_trade_plan_submitting(request.trade_plan_id)
        results = client.submit_orders(batch)
        for result in results:
            self.swing_repository.mark_trade_plan_execution_result(
                result.trade_plan_id,
                result.order_id,
                result.status if result.error is None else f"{result.status}:{result.error}",
                submitted=result.status == "submitted",
            )
        return {
            "ok": all(result.status == "submitted" for result in results),
            "submitted": True,
            "results": [result.__dict__ for result in results],
        }
