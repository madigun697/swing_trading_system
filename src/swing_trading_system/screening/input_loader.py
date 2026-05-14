"""Screening input loader built on shared market read-only access."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Protocol


class DailyPriceReader(Protocol):
    def fetch_daily_prices(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class ScreeningInput:
    symbol: str
    as_of_date: date
    rows: tuple[dict[str, Any], ...]

    @property
    def latest_row(self) -> dict[str, Any] | None:
        return self.rows[-1] if self.rows else None


class ScreeningInputLoader:
    """Loads point-in-time price history for screening.

    The loader enforces `trade_date <= as_of_date` before downstream screening code
    receives rows. This is the Sprint 2 boundary against look-ahead leakage.
    """

    def __init__(self, market_repository: DailyPriceReader) -> None:
        self.market_repository = market_repository

    def load_symbol(
        self,
        symbol: str,
        as_of_date: date,
        lookback_days: int = 260,
    ) -> ScreeningInput:
        if lookback_days <= 0:
            raise ValueError("lookback_days must be positive")
        start_date = as_of_date - timedelta(days=lookback_days)
        rows = self.market_repository.fetch_daily_prices(
            symbol=symbol,
            start_date=start_date,
            end_date=as_of_date,
            limit=lookback_days + 10,
        )
        filtered = [
            row
            for row in rows
            if row.get("trade_date") is not None and row["trade_date"] <= as_of_date
        ]
        ordered = tuple(sorted(filtered, key=lambda row: row["trade_date"]))
        return ScreeningInput(symbol=symbol, as_of_date=as_of_date, rows=ordered)

    def load_universe(
        self,
        symbols: list[str],
        as_of_date: date,
        lookback_days: int = 260,
    ) -> dict[str, ScreeningInput]:
        return {
            symbol: self.load_symbol(
                symbol=symbol, as_of_date=as_of_date, lookback_days=lookback_days
            )
            for symbol in symbols
        }

    def load_context(
        self, symbols: list[str], as_of_date: date
    ) -> dict[str, dict[str, Any]]:
        context: dict[str, dict[str, Any]] = {
            symbol: {"security_metadata": {}, "fundamentals": (), "filings": ()}
            for symbol in symbols
        }
        fetch_security_metadata = getattr(
            self.market_repository, "fetch_security_metadata", None
        )
        if fetch_security_metadata is not None:
            for symbol, metadata in fetch_security_metadata(
                symbols, as_of_date
            ).items():
                context.setdefault(symbol, {})["security_metadata"] = metadata
        fetch_point_in_time_fundamentals = getattr(
            self.market_repository, "fetch_point_in_time_fundamentals", None
        )
        if fetch_point_in_time_fundamentals is not None:
            for symbol, rows in fetch_point_in_time_fundamentals(
                symbols, as_of_date
            ).items():
                context.setdefault(symbol, {})["fundamentals"] = tuple(rows)
        fetch_filing_metadata = getattr(
            self.market_repository, "fetch_filing_metadata", None
        )
        if fetch_filing_metadata is not None:
            for symbol, rows in fetch_filing_metadata(symbols, as_of_date).items():
                context.setdefault(symbol, {})["filings"] = tuple(rows)
        return context
