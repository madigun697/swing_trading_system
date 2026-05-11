from pathlib import Path


def test_swing_repository_connects_screening_outputs_to_owned_schemas() -> None:
    source = Path("src/swing_trading_system/repositories/swing_repository.py").read_text()

    assert "INSERT INTO swing_mart.swing_feature_store" in source
    assert "INSERT INTO swing_meta.signal" in source
    assert "UPDATE swing_meta.screening_run" in source
    assert "INSERT INTO raw." not in source
    assert "INSERT INTO stg." not in source
    assert "UPDATE stg." not in source
