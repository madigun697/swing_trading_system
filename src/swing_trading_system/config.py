from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    postgres_db: str = Field(default="quant", alias="POSTGRES_DB")
    postgres_user: str = Field(default="quant", alias="POSTGRES_USER")
    postgres_password: str = Field(default="quant", alias="POSTGRES_PASSWORD")
    postgres_host: str = Field(default="127.0.0.1", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=55432, alias="POSTGRES_PORT")
    postgres_readonly: bool = Field(default=False, alias="POSTGRES_READONLY")

    minio_root_user: str = Field(default="minioadmin", alias="MINIO_ROOT_USER")
    minio_root_password: str = Field(default="minioadmin", alias="MINIO_ROOT_PASSWORD")
    minio_endpoint: str = Field(default="http://127.0.0.1:9000", alias="MINIO_ENDPOINT")
    minio_region: str = Field(default="us-east-1", alias="MINIO_REGION")

    alpaca_api_key: str | None = Field(default=None, alias="ALPACA_API_KEY")
    alpaca_secret_key: str | None = Field(default=None, alias="ALPACA_SECRET_KEY")
    alpaca_paper: bool = Field(default=True, alias="ALPACA_PAPER")

    swing_web_host: str = Field(default="0.0.0.0", alias="SWING_WEB_HOST")
    swing_web_port: int = Field(default=8401, alias="SWING_WEB_PORT")
    swing_api_port: int = Field(default=8402, alias="SWING_API_PORT")
    swing_metrics_port: int = Field(default=8403, alias="SWING_METRICS_PORT")

    swing_min_price: float = Field(default=10.0, alias="SWING_MIN_PRICE")
    swing_min_adv_usd: float = Field(default=10_000_000.0, alias="SWING_MIN_ADV_USD")
    swing_max_universe: int = Field(default=400, alias="SWING_MAX_UNIVERSE")
    swing_max_positions: int = Field(default=5, alias="SWING_MAX_POSITIONS")
    swing_max_sector_positions: int = Field(default=2, alias="SWING_MAX_SECTOR_POSITIONS")
    swing_risk_per_trade_pct: float = Field(default=0.01, alias="SWING_RISK_PER_TRADE_PCT")
    swing_fee_bps: float = Field(default=2.0, alias="SWING_FEE_BPS")
    swing_slippage_bps: float = Field(default=10.0, alias="SWING_SLIPPAGE_BPS")
    swing_default_lookback_days: int = Field(default=260, alias="SWING_DEFAULT_LOOKBACK_DAYS")
    swing_default_max_hold_days: int = Field(default=30, alias="SWING_DEFAULT_MAX_HOLD_DAYS")
    swing_screen_cutoff_hour_et: int = Field(default=17, alias="SWING_SCREEN_CUTOFF_HOUR_ET")
    swing_monitor_interval_minutes: int = Field(default=60, alias="SWING_MONITOR_INTERVAL_MINUTES")

    swing_watchlist_bucket: str = Field(default="swing-watchlists", alias="SWING_WATCHLIST_BUCKET")
    swing_backtest_bucket: str = Field(default="swing-backtests", alias="SWING_BACKTEST_BUCKET")
    swing_alert_bucket: str = Field(default="swing-alerts", alias="SWING_ALERT_BUCKET")

    slack_webhook_url: str | None = Field(default=None, alias="SLACK_WEBHOOK_URL")
    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(default=None, alias="TELEGRAM_CHAT_ID")
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, alias="SMTP_USERNAME")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    alert_email_to: Annotated[tuple[str, ...], NoDecode] = Field(default=(), alias="ALERT_EMAIL_TO")

    @field_validator("alert_email_to", mode="before")
    @classmethod
    def _normalize_email_list(cls, value: object) -> tuple[str, ...] | object:
        if value is None:
            return ()
        if isinstance(value, str):
            return tuple(token.strip() for token in value.split(",") if token.strip())
        if isinstance(value, (list, tuple, set)):
            return tuple(str(token).strip() for token in value if str(token).strip())
        return value

    @property
    def postgres_dsn(self) -> str:
        return (
            f"host={self.postgres_host} port={self.postgres_port} dbname={self.postgres_db} "
            f"user={self.postgres_user} password={self.postgres_password}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
