from swing_trading_system import cli
from swing_trading_system.db import DatabaseCheck
from swing_trading_system.repositories.shared_market import ReadinessStatus


def test_build_parser_accepts_required_commands() -> None:
    parser = cli.build_parser()

    assert parser.parse_args(["check-connection"]).command == "check-connection"
    assert parser.parse_args(["check-readiness"]).command == "check-readiness"
    assert parser.parse_args(["init-db"]).command == "init-db"
    assert parser.parse_args(["backfill-bootstrap"]).command == "backfill-bootstrap"


def test_check_connection_handler_reports_ok(monkeypatch) -> None:
    monkeypatch.setattr(cli, "check_database_connection", lambda settings: DatabaseCheck(True, "connected"))
    monkeypatch.setattr(cli, "check_minio_connection", lambda settings: True)

    code, payload = cli.handle_check_connection()

    assert code == 0
    assert payload["ok"] is True


def test_check_readiness_handler_uses_repository(monkeypatch) -> None:
    class FakeRepository:
        def __init__(self, settings=None) -> None:
            pass

        def check_readiness(self) -> ReadinessStatus:
            return ReadinessStatus(ok=True, code="ready", detail="ok", checked_relations=("stg.foo",))

    monkeypatch.setattr(cli, "SharedMarketRepository", FakeRepository)

    code, payload = cli.handle_check_readiness()

    assert code == 0
    assert payload["code"] == "ready"
    assert payload["checked_relations"] == ["stg.foo"]


def test_backfill_bootstrap_handler(monkeypatch) -> None:
    class FakeResult:
        def to_dict(self):
            return {"skipped": False, "feature_rows_upserted": 2}

    monkeypatch.setattr(cli, "backfill_sprint2_bootstrap", lambda market_repository, swing_repository: FakeResult())

    code, payload = cli.handle_backfill_bootstrap()

    assert code == 0
    assert payload["ok"] is True
    assert payload["feature_rows_upserted"] == 2
