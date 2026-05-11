from datetime import date

from swing_trading_system.screening.pipeline import CandidateSignal, ScreeningPipeline


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

    def create_signal(self, screening_run_id, symbol, signal_date, strategy, score=None, reason=None, details=None):
        self.signals.append(
            {
                "screening_run_id": screening_run_id,
                "symbol": symbol,
                "signal_date": signal_date,
                "strategy": strategy,
                "score": score,
                "reason": reason,
                "details": details,
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
