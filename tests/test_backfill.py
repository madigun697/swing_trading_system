from datetime import date

from swing_trading_system.backfill import backfill_sprint2_bootstrap


class FakeMarketRepository:
    def fetch_latest_trade_date(self):
        return date(2026, 5, 7)

    def fetch_top_liquid_symbols(self, as_of_date, limit=10):
        assert as_of_date == date(2026, 5, 7)
        assert limit == 10
        return ["SPY", "AAPL"]

    def fetch_daily_prices(self, symbol, start_date=None, end_date=None, limit=500):
        return [
            {"symbol": symbol, "trade_date": date(2026, 5, 6), "close": 100},
            {"symbol": symbol, "trade_date": date(2026, 5, 7), "close": 110},
        ]


class FakeSwingRepository:
    def __init__(self, counts=None):
        self.counts = counts or {"strategy_configs": 0, "screening_runs": 0, "signals": 0, "feature_rows": 0}
        self.configs = []
        self.features = []
        self.signals = []
        self.completed = []

    def get_bootstrap_counts(self):
        return self.counts

    def create_strategy_config(self, strategy_name, version="v1", params=None):
        self.configs.append(strategy_name)
        return {"strategy_name": strategy_name, "version": version, "params": params or {}}

    def create_screening_run(self, run_date, universe_name=None, criteria=None):
        self.run = {"id": 3, "run_date": run_date, "universe_name": universe_name, "criteria": criteria}
        return self.run

    def complete_screening_run(self, screening_run_id, result_count, status="completed"):
        self.completed.append((screening_run_id, result_count, status))
        return {"id": screening_run_id}

    def upsert_feature_store(self, symbol, feature_date, feature_set, features):
        self.features.append((symbol, feature_date, feature_set, features))
        return {"symbol": symbol}

    def create_signal(self, screening_run_id, symbol, signal_date, strategy, score=None, reason=None, details=None):
        self.signals.append(symbol)
        return {"symbol": symbol}


def test_backfill_seeds_configs_and_feature_store() -> None:
    result = backfill_sprint2_bootstrap(FakeMarketRepository(), FakeSwingRepository())

    assert result.skipped is False
    assert result.strategy_configs_seeded == 2
    assert result.feature_rows_upserted == 2
    assert result.signal_count == 0
    assert result.symbols == ("SPY", "AAPL")


def test_backfill_skips_existing_feature_data() -> None:
    result = backfill_sprint2_bootstrap(
        FakeMarketRepository(),
        FakeSwingRepository(counts={"strategy_configs": 1, "screening_runs": 1, "signals": 0, "feature_rows": 5}),
    )

    assert result.skipped is True
    assert result.feature_rows_upserted == 0
