# Swing Trading System User Manual

## 1. 목적

이 문서는 현재 구현된 Swing Trading System을 실제로 사용하는 운영자 기준 매뉴얼이다. 데이터 상태 확인, 시그널 생성, 백테스트 실행, 결과 해석까지의 흐름을 다룬다.

## 2. 시작 전 확인

### 필수 준비

- PostgreSQL과 MinIO가 접근 가능해야 한다.
- Quant shared relation이 읽기 가능해야 한다.
- Python 환경은 `uv`로 준비해야 한다.

### 초기 실행

```bash
uv sync
uv run swing-system check-connection
uv run swing-system check-readiness
uv run swing-system init-db
```

### 주요 readiness 의미

- `ready`: 필수 shared relation 접근 가능
- `missing_relation`: Quant shared table 누락
- `database_unreachable`: DB 연결 문제

## 3. 시스템 구성 요약

### 입력 데이터

- `stg.stg_daily_prices`
- `stg.stg_security_master`
- `stg.stg_benchmark_series`
- `stg.int_point_in_time_fundamentals`
- `stg.stg_filing_metadata`

### 생성 데이터

- `swing_mart.swing_feature_store`
- `swing_meta.signal`
- `swing_mart.backtest_trade_log`
- `swing_mart.backtest_equity_curve`
- `swing_mart.backtest_run_summary`

## 4. 웹 UI 사용법

### 서버 실행

```bash
uv run uvicorn swing_trading_system.web.app:app --host 0.0.0.0 --port 8401
```

기본 접속 주소:

- `http://localhost:8401/`

### Dashboard

경로: `/`

확인 항목:

- readiness 상태
- 최신 shared price date
- 저장된 signal 수
- 최근 backtest run 목록

이 화면은 운영 시작 전 데이터 상태를 보는 첫 화면이다.

### Signals

경로: `/signals`

확인 항목:

- 최근 시그널 목록
- 전략명
- signal date
- entry / stop / target
- score

전략명은 현재 `pullback`, `breakout`, `quality_momentum`이 저장될 수 있다.

### Backtests

경로: `/backtests`

확인 항목:

- 최근 run id
- trade 수
- 총 PnL
- run 기간

상세 분석이 필요하면 run id를 눌러 상세 화면으로 이동한다.

### Backtest Runner

경로: `/backtests/run`

입력 항목:

- Signal 시작일 / 종료일
- Strategy
- Symbols
- Initial Equity
- Benchmark
- Max Positions
- Max Position %
- Gross Exposure
- Pullback Size Multiplier
- Fee bps / Slippage bps
- Max Hold Days
- Target Scale-out
- Trailing MA Days
- Trailing Stop 사용 여부

실행 결과:

- 백테스트 결과를 저장한 뒤 상세 화면으로 이동

- `Strategy`를 비워두면 해당 기간의 전체 저장 signal을 사용한다. `breakout`, `pullback`, `quality_momentum` 단일 선택뿐만 아니라 `breakout+pullback` 처럼 두 개 이상의 전략 조합을 선택하여 동시에 백테스트를 실행할 수 있다.

## 5. CLI 운영 흐름

### 1) Bootstrap

```bash
uv run swing-system backfill-bootstrap
```

용도:

- 초기 strategy config seed
- bootstrap feature row 생성

### 2) Daily screening

```bash
uv run swing-system run-daily --max-universe 10 --dry-run
uv run swing-system run-daily --max-universe 10
```

설명:

- `--dry-run`: 계산만 수행, DB 미기록
- 일반 실행: feature와 signal 저장

이 단계에서 `screening_v2_context` feature set이 생성된다.

### 3) Historical signal backfill

```bash
uv run swing-system backfill-signals --start-date 2025-01-01 --end-date 2026-05-01 --frequency weekly --max-universe 10
```

설명:

- `daily`, `weekly`, `monthly` 지원
- 기본적으로 기존 signal/feature row가 있으면 skip
- 강제 재생성은 `--force`

과거 백테스트를 하려면 먼저 해당 기간 signal이 저장되어 있어야 한다.

### 4) Backtest

```bash
uv run swing-system run-backtest --start-date 2025-01-02 --end-date 2026-05-01 --dry-run
uv run swing-system run-backtest --start-date 2025-01-02 --end-date 2026-05-01
```

설명:

- `start-date`, `end-date`는 `signal_date` 기준 필터다.
- 실제 진입일은 `t+1` 시가다.
- 저장 실행 시 trade log, equity curve, summary가 기록된다.

## 6. 전략 설명

### Pullback

- 상승 추세 종목의 눌림목 진입
- `relative_strength_60d >= 0`
- `return_60d >= 0`
- MA20 또는 MA50 근처 pullback
- quality 또는 RS가 강하면 목표 R multiple 상향

### Breakout

- 전고점 돌파 진입
- 약한 breakout도 거래량 기준을 강하게 적용
- `atr_pct <= 0.08`
- quality 또는 RS가 강하면 목표 R multiple 상향

### Quality Momentum

- quality와 momentum이 동시에 강한 continuation setup
- 조건 예:
  - `RS >= 0.15`
  - `return_20d > 0`
  - `close > MA20 > MA50 > MA200`
  - 매출/이익/OCF 품질 확인

## 7. 시장 레짐 규칙

- SPY가 MA50 아래이고 20일 수익률이 음수면 신규 signal size는 `0.5x`
- SPY가 MA200 아래면 신규 signal은 생성하지 않음

이 규칙은 알파보다 시장 역풍이 강한 구간에서 손실 확산을 줄이기 위한 것이다.

## 8. 백테스트 결과 해석

### 핵심 지표

- `Total Return`: 총 수익률
- `PnL`: 누적 손익
- `MDD`: 최대 낙폭
- `Sharpe`: 변동성 대비 수익
- `CAGR`: 연환산 수익률
- `Calmar`: CAGR / |MDD|
- `Profit Factor`: 총이익 / 총손실
- `Win Rate`: 승률

### 상세 화면에서 꼭 볼 항목

- `Strategy vs SPY`
- `Symbol Contribution`
- `Strategy / Exit Summary`
- `Monthly Slice`
- `Sector Slice`
- `Strategy Slice`
- `Exit Slice`

### 해석 요령

- 초과수익이 낮고 MDD가 양호하면 진입 품질 문제일 가능성이 크다.
- 특정 symbol contribution 쏠림이 크면 전략 분산이 부족한 상태다.
- `stop_loss` 손실이 과도하면 신호 품질 또는 레짐 필터가 약한 것이다.
- `Monthly Slice`가 특정 구간에만 의존하면 지속성이 낮다.

## 9. 운영 시 주의사항

- Swing는 Quant-owned schema에 쓰면 안 된다.
- `dry-run`으로 먼저 확인하고 저장 실행으로 넘어가는 것이 안전하다.
- 백테스트 기간보다 signal 저장 기간이 좁으면 원하는 결과가 나오지 않는다.
- PIT fundamentals와 filing metadata는 `available_at <= as_of_date`만 사용해야 한다.

## 10. 추천 운영 순서

1. `check-connection`
2. `check-readiness`
3. `run-daily --dry-run`
4. `run-daily`
5. 필요 시 `backfill-signals`
6. `run-backtest --dry-run`
7. `run-backtest`
8. `/backtests/{run_id}`에서 결과 해석

## 11. 문제 해결 빠른 체크

### Signal이 안 나올 때

- readiness 확인
- universe가 너무 좁지 않은지 확인
- market regime 차단 상태인지 확인
- 최근 구간에서 RS / ATR / return 필터가 너무 엄격한지 확인

### Backtest 결과가 비어 있을 때

- 해당 기간 signal이 저장되어 있는지 확인
- `start-date`, `end-date`가 signal date 기준이라는 점 확인
- symbol filter가 너무 좁지 않은지 확인

### UI에서 degraded 경고가 뜰 때

- shared relation 접근
- backtest summary table 접근
- signal fetch 오류 여부

확인 순서로 보면 된다.
