from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Iterable

import psycopg

from swing_trading_system.config import get_settings
from swing_trading_system.domain import MarketBar, ReadinessStatus
from swing_trading_system.storage import postgres_connection


class SharedMarketRepository:
    def __init__(self) -> None:
        self.settings = get_settings()

    def required_relations(self) -> tuple[str, ...]:
        return (
            "stg.stg_daily_prices",
            "stg.stg_security_master",
            "stg.stg_benchmark_series",
        )

    def check_readiness(self) -> ReadinessStatus:
        try:
            with postgres_connection(read_only=True) as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    select schema_name
                    from information_schema.schemata
                    where schema_name = any(%s::text[])
                    """,
                    (["stg", "swing_meta", "swing_mart"],),
                )
                schemas = {row["schema_name"] for row in cur.fetchall()}
                missing = [schema for schema in ["stg", "swing_meta", "swing_mart"] if schema not in schemas]
                if missing:
                    return ReadinessStatus(False, "missing_schema", f"missing schema: {', '.join(missing)}", self.required_relations())
                for relation in self.required_relations():
                    cur.execute(f"select 1 from {relation} limit 1")
                    cur.fetchone()
                cur.execute("select max(trade_date) as latest_trade_date from stg.stg_daily_prices")
                latest_trade_date = cur.fetchone()["latest_trade_date"]
                if latest_trade_date is None:
                    return ReadinessStatus(False, "missing_market_data", "shared price history is empty", self.required_relations())
                age_days = (datetime.now(UTC).date() - latest_trade_date).days
                if age_days > 7:
                    return ReadinessStatus(False, "stale_shared_data", f"shared price history is stale by {age_days} days", self.required_relations())
        except psycopg.Error as exc:
            return ReadinessStatus(False, "database_error", " ".join(str(exc).split()), self.required_relations())
        return ReadinessStatus(True, "ok", "shared market data is ready", self.required_relations())

    def latest_trade_date(self) -> date | None:
        with postgres_connection(read_only=True) as conn, conn.cursor() as cur:
            cur.execute("select max(trade_date) as trade_date from stg.stg_daily_prices")
            row = cur.fetchone()
            return row["trade_date"] if row else None

    def fetch_market_bars(
        self,
        *,
        as_of_date: date,
        lookback_days: int,
        max_universe: int | None = None,
        min_adv_usd: float | None = None,
        symbols: Iterable[str] | None = None,
    ) -> dict[str, list[MarketBar]]:
        settings = self.settings
        start_date = as_of_date - timedelta(days=max(lookback_days * 2, lookback_days + 20))
        max_universe = max_universe or settings.swing_max_universe
        min_adv_usd = min_adv_usd or settings.swing_min_adv_usd
        symbol_filter = [symbol.upper() for symbol in symbols] if symbols else None
        with postgres_connection(read_only=True) as conn, conn.cursor() as cur:
            cur.execute(
                """
                with latest_liquid as (
                    select
                        p.symbol,
                        avg(p.dollar_volume) filter (where p.trade_date > %(lookback_start)s) as adv20,
                        row_number() over (
                            order by avg(p.dollar_volume) filter (where p.trade_date > %(lookback_start)s) desc nulls last, p.symbol
                        ) as universe_rank
                    from stg.stg_daily_prices p
                    join stg.stg_security_master s using (symbol)
                    where p.trade_date between %(start_date)s and %(as_of_date)s
                      and (%(symbols)s::text[] is null or p.symbol = any(%(symbols)s::text[]))
                      and coalesce(s.security_type, '') <> 'ETF'
                      and coalesce(s.active_delisted_status, 'Active') not ilike '%%delisted%%'
                    group by p.symbol
                ),
                selected as (
                    select symbol
                    from latest_liquid
                    where coalesce(adv20, 0) >= %(min_adv_usd)s
                       or symbol = 'SPY'
                    order by universe_rank
                    limit %(max_universe)s
                )
                select
                    p.symbol,
                    p.trade_date,
                    p.open,
                    p.high,
                    p.low,
                    coalesce(p.adjusted_close, p.close) as close,
                    coalesce(p.adjusted_volume, p.volume) as volume,
                    p.dollar_volume,
                    s.sector,
                    s.industry
                from stg.stg_daily_prices p
                left join stg.stg_security_master s using (symbol)
                where p.trade_date between %(start_date)s and %(as_of_date)s
                  and (
                    p.symbol = 'SPY'
                    or p.symbol in (select symbol from selected)
                  )
                order by p.symbol, p.trade_date
                """,
                {
                    "start_date": start_date,
                    "lookback_start": as_of_date - timedelta(days=40),
                    "as_of_date": as_of_date,
                    "max_universe": max_universe,
                    "min_adv_usd": min_adv_usd,
                    "symbols": symbol_filter,
                },
            )
            rows = cur.fetchall()
        bars: dict[str, list[MarketBar]] = defaultdict(list)
        for row in rows:
            bars[row["symbol"]].append(
                MarketBar(
                    symbol=row["symbol"],
                    trade_date=row["trade_date"],
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=row["volume"],
                    dollar_volume=row["dollar_volume"],
                    sector=row["sector"],
                    industry=row["industry"],
                )
            )
        return dict(bars)
