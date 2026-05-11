from swing_trading_system.config import Settings


def test_settings_parse_alert_email_csv() -> None:
    settings = Settings(ALERT_EMAIL_TO="a@example.com, b@example.com")
    assert settings.alert_email_to == ("a@example.com", "b@example.com")
    assert settings.swing_web_port == 8401


def test_infra_host_backfills_postgres_and_minio_defaults() -> None:
    settings = Settings(INFRA_HOST="10.0.0.5")
    assert settings.postgres_host == "10.0.0.5"
    assert settings.minio_endpoint == "http://10.0.0.5:9000"
