create schema if not exists swing_meta;
create schema if not exists swing_mart;
create schema if not exists swing_raw;

create table if not exists swing_meta.screen_runs (
  screen_run_id bigserial primary key,
  strategy_id text not null,
  signal_date date not null,
  status text not null default 'completed',
  params jsonb not null default '{}'::jsonb,
  candidate_count integer not null default 0,
  artifact_bucket text,
  artifact_key text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists swing_mart.screen_candidates (
  screen_run_id bigint not null references swing_meta.screen_runs(screen_run_id) on delete cascade,
  strategy_id text not null,
  signal_date date not null,
  symbol text not null,
  sector text,
  industry text,
  close_price numeric,
  adv20 numeric,
  atr14 numeric,
  relative_strength_20d numeric,
  relative_strength_60d numeric,
  volume_ratio_20d numeric,
  breakout_level numeric,
  pullback_distance_pct numeric,
  score numeric not null,
  risk_per_share numeric,
  stop_price numeric,
  target_price numeric,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  primary key (screen_run_id, symbol)
);
create index if not exists ix_swing_candidates_signal_date on swing_mart.screen_candidates(signal_date, strategy_id, score desc);

create table if not exists swing_meta.watchlist (
  watchlist_id bigserial primary key,
  symbol text not null,
  source_screen_run_id bigint references swing_meta.screen_runs(screen_run_id),
  status text not null default 'active',
  notes text,
  tags jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists ix_swing_watchlist_symbol on swing_meta.watchlist(symbol, status);

create table if not exists swing_meta.trade_plans (
  trade_plan_id bigserial primary key,
  strategy_id text not null,
  signal_date date not null,
  entry_date date,
  symbol text not null,
  side text not null default 'buy',
  quantity numeric,
  entry_price numeric,
  stop_price numeric,
  target_price numeric,
  risk_per_share numeric,
  score numeric,
  sector text,
  status text not null default 'planned',
  broker_order_id text,
  broker_status text,
  notes text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists ix_swing_trade_plans_status on swing_meta.trade_plans(status, signal_date desc);

create table if not exists swing_meta.positions (
  position_id bigserial primary key,
  trade_plan_id bigint references swing_meta.trade_plans(trade_plan_id),
  strategy_id text not null,
  symbol text not null,
  quantity numeric not null,
  entry_price numeric not null,
  stop_price numeric,
  target_price numeric,
  opened_at timestamptz not null default now(),
  closed_at timestamptz,
  status text not null default 'open',
  notes text,
  metadata jsonb not null default '{}'::jsonb
);
create index if not exists ix_swing_positions_status on swing_meta.positions(status, symbol);

create table if not exists swing_meta.alert_events (
  alert_event_id bigserial primary key,
  alert_type text not null,
  symbol text,
  severity text not null default 'info',
  message text not null,
  status text not null default 'pending',
  payload jsonb not null default '{}'::jsonb,
  artifact_bucket text,
  artifact_key text,
  created_at timestamptz not null default now(),
  sent_at timestamptz
);
create index if not exists ix_swing_alert_events_status on swing_meta.alert_events(status, created_at desc);

create table if not exists swing_mart.backtest_runs (
  backtest_run_id bigserial primary key,
  strategy_id text not null,
  start_date date not null,
  end_date date not null,
  initial_capital numeric not null,
  final_equity numeric not null,
  total_return numeric not null,
  cagr numeric,
  max_drawdown numeric,
  sharpe_ratio numeric,
  win_rate numeric,
  trade_count integer not null default 0,
  params jsonb not null default '{}'::jsonb,
  artifact_bucket text,
  artifact_key text,
  created_at timestamptz not null default now()
);

create table if not exists swing_mart.backtest_trades (
  backtest_run_id bigint not null references swing_mart.backtest_runs(backtest_run_id) on delete cascade,
  trade_id bigint not null,
  strategy_id text not null,
  symbol text not null,
  entry_date date not null,
  exit_date date not null,
  quantity numeric not null,
  entry_price numeric not null,
  exit_price numeric not null,
  pnl numeric not null,
  return_pct numeric not null,
  exit_reason text not null,
  hold_days integer not null,
  primary key (backtest_run_id, trade_id)
);

create table if not exists swing_mart.backtest_equity_curve (
  backtest_run_id bigint not null references swing_mart.backtest_runs(backtest_run_id) on delete cascade,
  trade_date date not null,
  cash numeric not null,
  market_value numeric not null,
  total_equity numeric not null,
  drawdown numeric not null,
  primary key (backtest_run_id, trade_date)
);
