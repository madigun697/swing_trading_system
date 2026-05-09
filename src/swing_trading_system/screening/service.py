from __future__ import annotations

from decimal import Decimal

from swing_trading_system.config import get_settings
from swing_trading_system.domain import FeatureSnapshot, MarketBar, ScreenCandidate
from swing_trading_system.repositories.shared_market import SharedMarketRepository
from swing_trading_system.screening.indicators import atr, average, highest, lowest, percent_change, volume_ratio
from swing_trading_system.strategies import STRATEGY_REGISTRY


class ScreeningService:
    def __init__(self, repository: SharedMarketRepository | None = None) -> None:
        self.repository = repository or SharedMarketRepository()
        self.settings = get_settings()

    def run(self, *, strategy_id: str, as_of_date, market_bars: dict[str, list[MarketBar]] | None = None, limit: int = 25) -> list[ScreenCandidate]:
        market_bars = market_bars or self.repository.fetch_market_bars(
            as_of_date=as_of_date,
            lookback_days=self.settings.swing_default_lookback_days,
        )
        strategy = STRATEGY_REGISTRY[strategy_id]
        benchmark_bars = market_bars.get("SPY", [])
        benchmark_closes = [bar.close for bar in benchmark_bars if bar.close is not None and bar.trade_date <= as_of_date]
        candidates: list[ScreenCandidate] = []
        for symbol, bars in market_bars.items():
            if symbol == "SPY":
                continue
            snapshot = self._build_snapshot(symbol=symbol, bars=bars, benchmark_closes=benchmark_closes, as_of_date=as_of_date)
            if snapshot is None:
                continue
            if snapshot.close_price < Decimal(str(self.settings.swing_min_price)):
                continue
            if snapshot.adv20 < Decimal(str(self.settings.swing_min_adv_usd)):
                continue
            candidate = strategy.evaluate(snapshot)
            if candidate is not None:
                candidates.append(candidate)
        candidates.sort(key=lambda row: (row.score, row.relative_strength_20d, row.volume_ratio20), reverse=True)
        return candidates[:limit]

    def _build_snapshot(
        self,
        *,
        symbol: str,
        bars: list[MarketBar],
        benchmark_closes: list[Decimal],
        as_of_date,
    ) -> FeatureSnapshot | None:
        filtered = [bar for bar in bars if bar.trade_date <= as_of_date and bar.close is not None and bar.volume is not None]
        if len(filtered) < 210:
            return None
        closes = [bar.close for bar in filtered if bar.close is not None]
        volumes = [bar.volume for bar in filtered if bar.volume is not None]
        adv_values = [bar.dollar_volume for bar in filtered if bar.dollar_volume is not None]
        sma20 = average(closes, 20)
        sma50 = average(closes, 50)
        sma200 = average(closes, 200)
        atr14 = atr(filtered, 14)
        adv20 = average(adv_values, 20)
        vol_ratio = volume_ratio(volumes, 20)
        breakout_20d = highest(closes, 20, exclude_last=True)
        low_20d = lowest(closes, 20)
        return_5d = percent_change(closes, 5)
        return_20d = percent_change(closes, 20)
        return_60d = percent_change(closes, 60)
        spy_20d = percent_change(benchmark_closes, 20) if benchmark_closes else None
        spy_60d = percent_change(benchmark_closes, 60) if benchmark_closes else None
        if None in (sma20, sma50, sma200, atr14, adv20, vol_ratio, breakout_20d, low_20d, return_5d, return_20d, return_60d, spy_20d, spy_60d):
            return None
        last_bar = filtered[-1]
        return FeatureSnapshot(
            symbol=symbol,
            trade_date=last_bar.trade_date,
            sector=last_bar.sector,
            industry=last_bar.industry,
            close_price=last_bar.close,
            adv20=adv20,
            atr14=atr14,
            sma20=sma20,
            sma50=sma50,
            sma200=sma200,
            volume_ratio20=vol_ratio,
            breakout_20d=breakout_20d,
            low_20d=low_20d,
            return_5d=return_5d,
            return_20d=return_20d,
            return_60d=return_60d,
            relative_strength_20d=return_20d - spy_20d,
            relative_strength_60d=return_60d - spy_60d,
        )
