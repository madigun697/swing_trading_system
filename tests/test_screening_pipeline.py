from datetime import date, timedelta

from swing_trading_system.screening.pipeline import CandidateSignal, ScreeningPipeline
from swing_trading_system.screening.screener import ScreeningCandidate
from swing_trading_system.strategies.base import StrategySignal


class FakeInput:
    def __init__(self, rows):
        self.rows = tuple(rows)

    @property
    def latest_row(self):
        return self.rows[-1] if self.rows else None


class FakeLoader:
    def load_universe(self, symbols, as_of_date, lookback_days=260):
        return {
            symbol: FakeInput([
                {"symbol": symbol, "trade_date": date(2026, 1, 2), "close": 100},
                {"symbol": symbol, "trade_date": as_of_date, "close": 110},
            ])
            for symbol in symbols
        }


class FakeRepository:
    def __init__(self):
        self.features = []
        self.signals = []
        self.completed = []

    def create_screening_run(self, run_date, universe_name=None, criteria=None):
        self.run = {"id": 7, "run_date": run_date, "universe_name": universe_name, "criteria": criteria}
        return self.run

    def complete_screening_run(self, screening_run_id, result_count, status="completed"):
        self.completed.append({"screening_run_id": screening_run_id, "result_count": result_count, "status": status})
        return {"id": screening_run_id, "result_count": result_count, "status": status}

    def upsert_feature_store(self, symbol, feature_date, feature_set, features):
        self.features.append({"symbol": symbol, "feature_date": feature_date, "feature_set": feature_set, "features": features})
        return self.features[-1]

    def create_signal(self, screening_run_id, symbol, signal_date, strategy, score=None, reason=None, details=None, **kwargs):
        self.signals.append(
            {
                "screening_run_id": screening_run_id,
                "symbol": symbol,
                "signal_date": signal_date,
                "strategy": strategy,
                "score": score,
                "reason": reason,
                "details": details,
                **kwargs,
            }
        )
        return self.signals[-1]


def test_pipeline_stores_features_signals_and_completes_run() -> None:
    repo = FakeRepository()
    pipeline = ScreeningPipeline(FakeLoader(), repo)

    result = pipeline.run_candidates(
        symbols=["AAPL", "MSFT"],
        as_of_date=date(2026, 1, 3),
        candidates=[CandidateSignal(symbol="AAPL", strategy="pullback", score=0.9, reason="candidate")],
        universe_name="test-universe",
    )

    assert result.screening_run_id == 7
    assert result.feature_count == 2
    assert result.signal_count == 1
    assert repo.features[0]["features"]["latest_trade_date"] == "2026-01-03"
    assert repo.signals[0]["screening_run_id"] == 7
    assert repo.completed == [{"screening_run_id": 7, "result_count": 1, "status": "completed"}]


class HistoricalLoader:
    def load_symbol(self, symbol, as_of_date, lookback_days=260):
        start = as_of_date - timedelta(days=220)
        rows = []
        for idx in range(221):
            close = 100 + idx
            rows.append(
                {
                    "symbol": symbol,
                    "trade_date": start + timedelta(days=idx),
                    "open": close - 0.5,
                    "high": close + 1,
                    "low": close - 1,
                    "close": close,
                    "volume": 1_000_000,
                    "dollar_volume": close * 1_000_000,
                }
            )
        return FakeInput(rows)

    def load_universe(self, symbols, as_of_date, lookback_days=260):
        return {symbol: self.load_symbol(symbol, as_of_date, lookback_days) for symbol in symbols}


class FakeScreener:
    def screen(self, features):
        return [ScreeningCandidate(symbol=features[0].symbol, score=0.9, passed=True, reason="passed", features=features[0])]


class FakeStrategy:
    name = "fake"

    def generate(self, candidate, context):
        return StrategySignal(
            symbol=candidate.symbol,
            signal_date=context.as_of_date,
            strategy=self.name,
            entry_price=100,
            stop_price=95,
            target_price=110,
            risk_per_share=5,
            position_size=10,
            score=candidate.score,
            reason="fake_signal",
        )


def test_run_daily_calculates_features_and_saves_strategy_signal() -> None:
    repo = FakeRepository()
    pipeline = ScreeningPipeline(HistoricalLoader(), repo, screener=FakeScreener(), strategies=(FakeStrategy(),))

    result = pipeline.run_daily(symbols=["AAPL"], as_of_date=date(2026, 1, 3), universe_name="test")

    assert result.feature_count == 1
    assert result.candidate_count == 1
    assert result.signal_count == 1
    assert repo.features[0]["features"]["history_days"] == 221
    assert repo.signals[0]["entry_price"] == 100
    assert repo.completed[-1]["result_count"] == 1
