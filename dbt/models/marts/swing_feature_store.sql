{{ config(tags=["mart"], materialized='table') }}

with prices as (
    select
        symbol,
        trade_date,
        open,
        high,
        low,
        coalesce(adjusted_close, close) as close_price,
        coalesce(adjusted_volume, volume) as volume,
        dollar_volume
    from {{ source('stg', 'stg_daily_prices') }}
),
spy as (
    select
        observation_date as trade_date,
        value as spy_close
    from {{ source('stg', 'stg_benchmark_series') }}
    where benchmark_name = 'SPY'
),
master as (
    select symbol, sector, industry, security_type, active_delisted_status
    from {{ source('stg', 'stg_security_master') }}
),
base as (
    select
        p.*,
        lag(close_price) over (partition by symbol order by trade_date) as prev_close,
        avg(close_price) over (partition by symbol order by trade_date rows between 19 preceding and current row) as sma20,
        avg(close_price) over (partition by symbol order by trade_date rows between 49 preceding and current row) as sma50,
        avg(close_price) over (partition by symbol order by trade_date rows between 199 preceding and current row) as sma200,
        avg(dollar_volume) over (partition by symbol order by trade_date rows between 19 preceding and current row) as adv20,
        avg(volume) over (partition by symbol order by trade_date rows between 19 preceding and current row) as avg_volume20,
        max(high) over (partition by symbol order by trade_date rows between 20 preceding and 1 preceding) as breakout_20d,
        min(low) over (partition by symbol order by trade_date rows between 19 preceding and current row) as low_20d,
        lag(close_price, 5) over (partition by symbol order by trade_date) as close_5d,
        lag(close_price, 20) over (partition by symbol order by trade_date) as close_20d,
        lag(close_price, 60) over (partition by symbol order by trade_date) as close_60d,
        greatest(
            high - low,
            abs(high - lag(close_price) over (partition by symbol order by trade_date)),
            abs(low - lag(close_price) over (partition by symbol order by trade_date))
        ) as true_range
    from prices p
),
features as (
    select
        b.symbol,
        b.trade_date,
        b.close_price,
        b.volume,
        b.dollar_volume,
        b.sma20,
        b.sma50,
        b.sma200,
        avg(true_range) over (partition by symbol order by trade_date rows between 13 preceding and current row) as atr14,
        b.adv20,
        case when b.avg_volume20 > 0 then b.volume / b.avg_volume20 else null end as volume_ratio20,
        b.breakout_20d,
        b.low_20d,
        case when b.close_5d > 0 then b.close_price / b.close_5d - 1 end as return_5d,
        case when b.close_20d > 0 then b.close_price / b.close_20d - 1 end as return_20d,
        case when b.close_60d > 0 then b.close_price / b.close_60d - 1 end as return_60d
    from base b
),
spy_returns as (
    select
        trade_date,
        case when lag(spy_close, 20) over (order by trade_date) > 0 then spy_close / lag(spy_close, 20) over (order by trade_date) - 1 end as spy_return_20d,
        case when lag(spy_close, 60) over (order by trade_date) > 0 then spy_close / lag(spy_close, 60) over (order by trade_date) - 1 end as spy_return_60d
    from spy
)
select
    f.symbol,
    f.trade_date,
    m.sector,
    m.industry,
    m.security_type,
    m.active_delisted_status,
    f.close_price,
    f.volume,
    f.dollar_volume,
    f.sma20,
    f.sma50,
    f.sma200,
    f.atr14,
    f.adv20,
    f.volume_ratio20,
    f.breakout_20d,
    f.low_20d,
    f.return_5d,
    f.return_20d,
    f.return_60d,
    case when s.spy_return_20d is not null and f.return_20d is not null then f.return_20d - s.spy_return_20d end as relative_strength_20d,
    case when s.spy_return_60d is not null and f.return_60d is not null then f.return_60d - s.spy_return_60d end as relative_strength_60d
from features f
left join master m using (symbol)
left join spy_returns s using (trade_date)
where coalesce(m.security_type, '') <> 'ETF'
