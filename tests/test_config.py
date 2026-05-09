from swing_trading_system.config import Settings


def test_settings_parse_alert_email_csv() -> None:
    settings = Settings(ALERT_EMAIL_TO="a@example.com, b@example.com")
    assert settings.alert_email_to == ("a@example.com", "b@example.com")
    assert settings.swing_web_port == 8401
