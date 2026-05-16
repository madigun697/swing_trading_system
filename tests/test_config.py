from swing_trading_system.config import Settings


def test_infra_host_backfills_postgres_and_minio() -> None:
    settings = Settings(_env_file=None, INFRA_HOST="infra.example")

    assert settings.postgres_host == "infra.example"
    assert settings.minio_endpoint == "http://infra.example:9000"
    assert settings.postgres_port == 55432


def test_explicit_postgres_and_minio_override_infra_host() -> None:
    settings = Settings(
        _env_file=None,
        INFRA_HOST="infra.example",
        POSTGRES_HOST="db.example",
        MINIO_ENDPOINT="http://minio.example:9000",
    )

    assert settings.postgres_host == "db.example"
    assert settings.minio_endpoint == "http://minio.example:9000"


def test_postgres_dsn_uses_runtime_values() -> None:
    settings = Settings(
        _env_file=None,
        POSTGRES_USER="user",
        POSTGRES_PASSWORD="pass",
        POSTGRES_DB="swing",
        POSTGRES_HOST="db.example",
        POSTGRES_PORT=15432,
    )

    assert settings.postgres_dsn == "postgresql://user:pass@db.example:15432/swing"


def test_aggressive_backtest_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.swing_max_positions == 10
    assert settings.swing_max_position_pct == 0.125
    assert settings.swing_max_gross_exposure_pct == 1.1
    assert settings.swing_benchmark_symbol == "SPY"
    assert settings.swing_regime_profile == "aggressive"
    assert settings.swing_require_vix is True
    assert settings.swing_vix_benchmark_name == "VIXCLS"
    assert settings.swing_enable_trailing_stop is True
