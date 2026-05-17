from argparse import Namespace
from datetime import date

from swing_trading_system import cli
from swing_trading_system.config import Settings
from swing_trading_system.db import DatabaseCheck
from swing_trading_system.repositories.shared_market import ReadinessStatus


def test_build_parser_accepts_required_commands() -> None:
    parser = cli.build_parser()

    assert parser.parse_args(["check-connection"]).command == "check-connection"
    assert parser.parse_args(["check-readiness"]).command == "check-readiness"
    assert parser.parse_args(["init-db"]).command == "init-db"
    assert parser.parse_args(["backfill-bootstrap"]).command == "backfill-bootstrap"
    assert (
        parser.parse_args(
            [
                "backfill-signals",
                "--start-date",
                "2026-01-01",
                "--end-date",
                "2026-01-31",
            ]
        ).command
        == "backfill-signals"
    )
    assert (
        parser.parse_args(["run-daily", "--as-of", "2026-01-01", "--dry-run"]).command
        == "run-daily"
    )
    parsed = parser.parse_args(
        [
            "run-backtest",
            "--start-date",
            "2026-01-01",
            "--benchmark-symbol",
            "SPY",
            "--max-position-pct",
            "0.125",
            "--dry-run",
        ]
    )
    assert parsed.command == "run-backtest"
    assert parsed.benchmark_symbol == "SPY"
    assert parsed.max_position_pct == 0.125


def test_check_connection_handler_reports_ok(monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "check_database_connection",
        lambda settings: DatabaseCheck(True, "connected"),
    )
    monkeypatch.setattr(cli, "check_minio_connection", lambda settings: True)

    code, payload = cli.handle_check_connection()

    assert code == 0
    assert payload["ok"] is True


def test_check_readiness_handler_uses_repository(monkeypatch) -> None:
    class FakeRepository:
        def __init__(self, settings=None) -> None:
            pass

        def check_readiness(self) -> ReadinessStatus:
            return ReadinessStatus(
                ok=True, code="ready", detail="ok", checked_relations=("stg.foo",)
            )

    monkeypatch.setattr(cli, "SharedMarketRepository", FakeRepository)

    code, payload = cli.handle_check_readiness()

    assert code == 0
    assert payload["code"] == "ready"
    assert payload["checked_relations"] == ["stg.foo"]


def test_run_daily_dry_run_handler(monkeypatch) -> None:
    class FakeMarketRepository:
        def __init__(self, settings=None) -> None:
            pass

        def fetch_latest_trade_date(self):
            return date(2026, 1, 1)

        def fetch_top_liquid_symbols(self, as_of_date, limit=10):
            return ["AAPL", "MSFT"]

    class FakePipelineResult:
        def to_dict(self):
            return {
                "screening_run_id": 0,
                "feature_count": 2,
                "candidate_count": 1,
                "signal_count": 1,
                "symbols": ["AAPL", "MSFT"],
            }

    class FakePipeline:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def run_daily(self, **kwargs):
            assert kwargs["as_of_date"] == date(2026, 1, 1)
            return FakePipelineResult()

    monkeypatch.setattr(cli, "SharedMarketRepository", FakeMarketRepository)
    monkeypatch.setattr(cli, "ScreeningPipeline", FakePipeline)

    args = Namespace(as_of="2026-01-01", symbols=None, max_universe=2, dry_run=True)
    code, payload = cli.handle_run_daily(args, Settings(_env_file=None))

    assert code == 0
    assert payload["dry_run"] is True
    assert payload["feature_count"] == 2
    assert payload["would_write"] == {
        "feature_rows": 0,
        "signals": 0,
        "completed_runs": 0,
    }


def test_backfill_signals_handler_selects_trade_dates(monkeypatch) -> None:
    class FakeMarketRepository:
        def __init__(self, settings=None) -> None:
            pass

        def fetch_trade_dates(self, start_date, end_date, symbol="SPY"):
            return [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 8)]

    calls = []

    def fake_run_daily(args, settings=None):
        calls.append(args.as_of)
        return 0, {
            "signal_count": 1,
            "feature_count": 2,
            "candidate_count": 1,
            "screening_run_id": len(calls),
        }

    monkeypatch.setattr(cli, "SharedMarketRepository", FakeMarketRepository)
    monkeypatch.setattr(cli, "handle_run_daily", fake_run_daily)

    args = Namespace(
        start_date="2026-01-01",
        end_date="2026-01-31",
        frequency="weekly",
        max_universe=2,
        symbols=None,
        dry_run=True,
        force=False,
    )
    code, payload = cli.handle_backfill_signals(args, Settings(_env_file=None))

    assert code == 0
    assert calls == ["2026-01-01", "2026-01-08"]
    assert payload["processed_dates"] == 2
    assert payload["total_signals"] == 2


def test_run_backtest_handler_dry_run(monkeypatch) -> None:
    fetch_kwargs = {}

    class FakeRepository:
        def __init__(self, settings=None) -> None:
            pass

        def fetch_signals(self, **kwargs):
            fetch_kwargs.update(kwargs)
            return ["signal"]

        def fetch_prices_for_signals(
            self, signals, end_date=None, max_hold_days=20, benchmark_symbol=None
        ):
            assert benchmark_symbol == "SPY"
            return {"AAA": []}

        def save_result(self, result):
            raise AssertionError("dry-run must not save")

    class FakeTrade:
        entry_date = date(2026, 1, 2)
        exit_date = date(2026, 1, 3)

    class FakeResult:
        run_id = "r1"
        trades = [FakeTrade()]
        rejections = []
        metrics = {"total_return": 0.01}
        signal_start_date = date(2026, 1, 1)
        signal_end_date = date(2026, 1, 1)

    class FakeEngine:
        def run(self, signals, prices_by_symbol, config):
            return FakeResult()

    monkeypatch.setattr(cli, "BacktestRepository", FakeRepository)
    monkeypatch.setattr(cli, "BacktestEngine", lambda: FakeEngine())
    args = Namespace(
        start_date="2026-01-01",
        end_date=None,
        strategy=None,
        symbols=None,
        initial_equity=None,
        fee_bps=None,
        slippage_bps=None,
        max_hold_days=None,
        max_positions=None,
        max_gross_exposure_pct=None,
        max_position_pct=None,
        pullback_size_multiplier=None,
        benchmark_symbol=None,
        target_scale_out_pct=None,
        trailing_ma_days=None,
        disable_trailing_stop=False,
        dry_run=True,
    )

    code, payload = cli.handle_run_backtest(args, Settings(_env_file=None))

    assert code == 0
    assert payload["dry_run"] is True
    assert payload["market_regime_required"] is False
    assert payload["trade_count"] == 1
    assert payload["trades_saved"] == 0
    assert fetch_kwargs["limit"] is None
    assert fetch_kwargs["require_market_regime"] is False


def test_run_backtest_market_regime_strategy_requires_regime_signals(
    monkeypatch,
) -> None:
    fetch_kwargs = {}

    class FakeRepository:
        def __init__(self, settings=None) -> None:
            pass

        def fetch_signals(self, **kwargs):
            fetch_kwargs.update(kwargs)
            return []

        def fetch_prices_for_signals(
            self, signals, end_date=None, max_hold_days=20, benchmark_symbol=None
        ):
            return {}

        def save_result(self, result):
            raise AssertionError("dry-run must not save")

    class FakeResult:
        run_id = "r1"
        trades = []
        rejections = []
        metrics = {"total_return": 0.0}
        signal_start_date = None
        signal_end_date = None

    class FakeEngine:
        def run(self, signals, prices_by_symbol, config):
            return FakeResult()

    monkeypatch.setattr(cli, "BacktestRepository", FakeRepository)
    monkeypatch.setattr(cli, "BacktestEngine", lambda: FakeEngine())
    args = Namespace(
        start_date="2026-01-01",
        end_date=None,
        strategy="market_regime",
        symbols=None,
        initial_equity=None,
        fee_bps=None,
        slippage_bps=None,
        max_hold_days=None,
        max_positions=None,
        max_gross_exposure_pct=None,
        max_position_pct=None,
        pullback_size_multiplier=None,
        benchmark_symbol=None,
        target_scale_out_pct=None,
        trailing_ma_days=None,
        disable_trailing_stop=False,
        dry_run=True,
    )

    code, payload = cli.handle_run_backtest(args, Settings(_env_file=None))

    assert code == 0
    assert payload["market_regime_required"] is True
    assert fetch_kwargs["strategy"] is None
    assert fetch_kwargs["limit"] is None
    assert fetch_kwargs["require_market_regime"] is True


def test_backfill_bootstrap_handler(monkeypatch) -> None:
    class FakeResult:
        def to_dict(self):
            return {"skipped": False, "feature_rows_upserted": 2}

    monkeypatch.setattr(
        cli,
        "backfill_sprint2_bootstrap",
        lambda market_repository, swing_repository: FakeResult(),
    )

    code, payload = cli.handle_backfill_bootstrap()

    assert code == 0
    assert payload["ok"] is True
    assert payload["feature_rows_upserted"] == 2
