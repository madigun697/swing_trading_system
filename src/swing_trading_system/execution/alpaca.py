from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from swing_trading_system.config import Settings


@dataclass(frozen=True)
class BatchOrderRequest:
    trade_plan_id: int
    symbol: str
    qty: Decimal
    side: str
    client_order_id: str


@dataclass(frozen=True)
class OrderResult:
    trade_plan_id: int
    symbol: str
    status: str
    order_id: str | None
    error: str | None = None


class ConfigurationError(RuntimeError):
    pass


class AlpacaClient:
    def __init__(self, settings: Settings) -> None:
        if not settings.alpaca_api_key or not settings.alpaca_secret_key:
            raise ConfigurationError("ALPACA_API_KEY / ALPACA_SECRET_KEY is required")
        self.client = TradingClient(settings.alpaca_api_key, settings.alpaca_secret_key, paper=settings.alpaca_paper)

    def submit_orders(self, requests: list[BatchOrderRequest]) -> list[OrderResult]:
        results: list[OrderResult] = []
        for request in requests:
            try:
                order = self.client.submit_order(
                    MarketOrderRequest(
                        symbol=request.symbol,
                        qty=float(request.qty),
                        side=OrderSide.BUY if request.side == "buy" else OrderSide.SELL,
                        time_in_force=TimeInForce.DAY,
                        client_order_id=request.client_order_id,
                    )
                )
                results.append(OrderResult(request.trade_plan_id, request.symbol, "submitted", str(order.id)))
            except Exception as exc:  # noqa: BLE001
                results.append(OrderResult(request.trade_plan_id, request.symbol, "error", None, str(exc)))
        return results
