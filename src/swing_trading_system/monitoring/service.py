from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from swing_trading_system.config import get_settings
from swing_trading_system.domain import AlertEvent
from swing_trading_system.monitoring.alerts import EmailNotifier, SlackNotifier, TelegramNotifier
from swing_trading_system.repositories.shared_market import SharedMarketRepository
from swing_trading_system.repositories.swing_repository import SwingRepository


class MonitoringService:
    def __init__(
        self,
        shared_repository: SharedMarketRepository | None = None,
        swing_repository: SwingRepository | None = None,
    ) -> None:
        self.settings = get_settings()
        self.shared_repository = shared_repository or SharedMarketRepository()
        self.swing_repository = swing_repository or SwingRepository()

    def generate_alerts(self, *, as_of_date: date, include_candidates: bool = True) -> list[AlertEvent]:
        alerts: list[AlertEvent] = []
        positions = self.swing_repository.list_open_positions()
        position_symbols = [row["symbol"] for row in positions]
        symbol_bars = self.shared_repository.fetch_market_bars(
            as_of_date=as_of_date,
            lookback_days=30,
            symbols=position_symbols,
            max_universe=max(len(position_symbols), 1),
            min_adv_usd=0,
        ) if position_symbols else {}
        for position in positions:
            latest_bar = symbol_bars.get(position["symbol"], [])[-1] if symbol_bars.get(position["symbol"]) else None
            if latest_bar is None or latest_bar.close is None:
                continue
            stop_price = Decimal(str(position["stop_price"])) if position["stop_price"] is not None else None
            target_price = Decimal(str(position["target_price"])) if position["target_price"] is not None else None
            if stop_price is not None and latest_bar.close <= stop_price:
                alerts.append(AlertEvent("stop_loss", position["symbol"], "critical", f"{position['symbol']} closed below stop at {latest_bar.close}", {"trade_date": str(as_of_date), "stop_price": str(stop_price)}))
            if target_price is not None and latest_bar.close >= target_price:
                alerts.append(AlertEvent("take_profit", position["symbol"], "info", f"{position['symbol']} reached target at {latest_bar.close}", {"trade_date": str(as_of_date), "target_price": str(target_price)}))
        if include_candidates:
            latest_candidates = self.swing_repository.list_latest_candidates(limit=5)
            if latest_candidates:
                top = latest_candidates[0]
                alerts.append(AlertEvent("candidate_digest", top["symbol"], "info", f"Latest top swing candidate: {top['symbol']} score={top['score']}", {"trade_date": str(as_of_date), "screen_run_id": top["screen_run_id"]}))
        return alerts

    def persist_and_dispatch(self, alerts: list[AlertEvent], *, send: bool) -> int:
        saved_count = self.swing_repository.save_alerts(alerts)
        if send:
            for notifier in self._notifiers():
                for alert in alerts:
                    notifier.send(alert)
        return saved_count

    def run_end_of_day_monitor(self, *, as_of_date: date, send: bool) -> int:
        alerts = self.generate_alerts(as_of_date=as_of_date)
        return self.persist_and_dispatch(alerts, send=send)

    def _notifiers(self):
        settings = self.settings
        notifiers = []
        if settings.slack_webhook_url:
            notifiers.append(SlackNotifier(settings.slack_webhook_url))
        if settings.telegram_bot_token and settings.telegram_chat_id:
            notifiers.append(TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id))
        if settings.smtp_host and settings.alert_email_to:
            notifiers.append(EmailNotifier(settings))
        return notifiers
