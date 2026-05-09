from swing_trading_system.strategies.breakout import BreakoutStrategy
from swing_trading_system.strategies.pullback import PullbackStrategy

STRATEGY_REGISTRY = {
    "breakout": BreakoutStrategy(),
    "pullback": PullbackStrategy(),
}

__all__ = ["STRATEGY_REGISTRY", "BreakoutStrategy", "PullbackStrategy"]
