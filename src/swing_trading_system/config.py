"""Runtime configuration for the Swing trading system."""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    postgres_db: str = Field(default="quant", alias="POSTGRES_DB")
    postgres_user: str = Field(default="quant", alias="POSTGRES_USER")
    postgres_password: str = Field(default="quant", alias="POSTGRES_PASSWORD")
    infra_host: str = Field(default="localhost", alias="INFRA_HOST")
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=55432, alias="POSTGRES_PORT")
    postgres_readonly: bool = Field(default=False, alias="POSTGRES_READONLY")

    minio_endpoint: str = Field(default="http://localhost:9000", alias="MINIO_ENDPOINT")
    minio_root_user: str = Field(default="minioadmin", alias="MINIO_ROOT_USER")
    minio_root_password: str = Field(default="minioadmin", alias="MINIO_ROOT_PASSWORD")
    minio_region: str = Field(default="us-east-1", alias="MINIO_REGION")

    swing_web_host: str = Field(default="0.0.0.0", alias="SWING_WEB_HOST")
    swing_web_port: int = Field(default=8401, alias="SWING_WEB_PORT")
    swing_watchlist_bucket: str = Field(default="swing-watchlists", alias="SWING_WATCHLIST_BUCKET")
    swing_backtest_bucket: str = Field(default="swing-backtests", alias="SWING_BACKTEST_BUCKET")
    swing_alert_bucket: str = Field(default="swing-alerts", alias="SWING_ALERT_BUCKET")
    swing_execution_bucket: str = Field(default="swing-executions", alias="SWING_EXECUTION_BUCKET")

    @model_validator(mode="before")
    @classmethod
    def _derive_infra_defaults(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        infra_host = value.get("INFRA_HOST") or value.get("infra_host") or "localhost"
        updated = dict(value)
        if "POSTGRES_HOST" not in updated and "postgres_host" not in updated:
            updated["POSTGRES_HOST"] = infra_host
        if "MINIO_ENDPOINT" not in updated and "minio_endpoint" not in updated:
            updated["MINIO_ENDPOINT"] = f"http://{infra_host}:9000"
        return updated

    @property
    def postgres_dsn(self) -> str:
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        host = self.postgres_host
        port = self.postgres_port
        db = quote_plus(self.postgres_db)
        return f"postgresql://{user}:{password}@{host}:{port}/{db}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
