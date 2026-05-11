"""Screening input, feature, and pipeline foundations."""

from swing_trading_system.screening.features import ScreeningFeatures, calculate_features
from swing_trading_system.screening.input_loader import ScreeningInputLoader
from swing_trading_system.screening.pipeline import CandidateSignal, ScreeningPipeline, ScreeningPipelineResult
from swing_trading_system.screening.screener import Screener, ScreenerConfig, ScreeningCandidate
from swing_trading_system.screening.universe import UniverseSelection, UniverseSelector

__all__ = [
    "CandidateSignal",
    "Screener",
    "ScreenerConfig",
    "ScreeningCandidate",
    "ScreeningFeatures",
    "ScreeningInputLoader",
    "ScreeningPipeline",
    "ScreeningPipelineResult",
    "UniverseSelection",
    "UniverseSelector",
    "calculate_features",
]
