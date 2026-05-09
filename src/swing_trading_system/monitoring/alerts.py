from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Protocol

import requests

from swing_trading_system.config import Settings
from swing_trading_system.domain import AlertEvent


class Notifier(Protocol):
    def send(self, alert: AlertEvent) -> None: ...


class SlackNotifier:
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send(self, alert: AlertEvent) -> None:
        requests.post(self.webhook_url, json={"text": alert.message}, timeout=10)


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send(self, alert: AlertEvent) -> None:
        requests.post(
            f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
            json={"chat_id": self.chat_id, "text": alert.message},
            timeout=10,
        )


class EmailNotifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send(self, alert: AlertEvent) -> None:
        if not self.settings.alert_email_to:
            return
        message = EmailMessage()
        message["Subject"] = f"[Swing] {alert.severity.upper()} {alert.alert_type}"
        message["From"] = self.settings.smtp_username or "swing-system@example.com"
        message["To"] = ", ".join(self.settings.alert_email_to)
        message.set_content(alert.message)
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if self.settings.smtp_username and self.settings.smtp_password:
                smtp.login(self.settings.smtp_username, self.settings.smtp_password)
            smtp.send_message(message)
