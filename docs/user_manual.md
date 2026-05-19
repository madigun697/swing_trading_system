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
- `missing_vix_benchmark`: `stg.stg_benchmark_series`에 `VIXCLS`가 아직 적재되지 않음
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
- regime id
- signal date
- entry / stop / target
- score

전략명은 현재 `pullback`, `breakout`, `quality_momentum`이 저장될 수 있다.
regime column은 신규 market regime switching 로직이 해당 signal에 어떤 시장 국면을 붙였는지 보여준다.

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

입력 항목은 많지만, 역할은 크게 4가지다.

- 언제의 signal을 볼지: `Signal 시작일`, `Signal 종료일`
- 어떤 signal을 실행할지: `Strategy`, `Symbols`
- 얼마를 어떤 규칙으로 배분할지: `Initial Equity`, `Max Positions`, `Max Position %`, `Gross Exposure`, `Portfolio Heat`, `Pullback Size Multiplier`
- 거래 비용과 청산 규칙을 어떻게 볼지: `Fee bps`, `Slippage bps`, `Max Hold Days`, `Target Scale-out`, `Trailing MA Days`, `Failed Exit Days`, `Failed Exit R`, `Trailing Stop`, `Breakeven Stop`

실행 결과:

- 백테스트 결과를 저장한 뒤 상세 화면으로 이동

- `Strategy`의 `Market Regime Switching` 옵션은 저장된 regime-aware signal 전체를 사용한다.
- 개별 전략 비교가 필요하면 `breakout`, `pullback`, `quality_momentum` 또는 조합 옵션을 선택한다.
- regime-aware backtest 비교 전에는 `backfill-signals --force` 또는 `run-daily`로 최신 signal을 다시 생성하는 것이 기준이다.
- `VIXCLS` 데이터가 readiness에서 필수로 설정된 환경이라면 먼저 Quant repo에서 아래 명령으로 데이터를 적재해야 한다.

```bash
uv run python -m quant_data_platform.cli sync-fred --series VIXCLS
```

실행이 끝나면 `/backtests/{run_id}` 상세 화면의 `Run Config`에서 같은 설정값을 다시 확인할 수 있다. 이 화면은 “내가 어떤 조건으로 백테스트를 돌렸는지”를 나중에 추적할 때 특히 중요하다.

### 입력 항목 상세

#### `Signal 시작일`

- 의미: 백테스트가 읽어 올 signal의 시작 기준일이다.
- 전략 영향: 시작일이 너무 늦으면 학습 기간이 짧아지고, 너무 이르면 오래된 시장 환경까지 섞여 결과가 희석될 수 있다.
- 초심자 팁: 먼저 최근 6개월이나 1년 정도로 시작하고, 결과가 재현되는지 확인한 뒤 기간을 넓히는 편이 안전하다.

#### `Signal 종료일`

- 의미: 백테스트가 읽어 올 signal의 마지막 기준일이다.
- 전략 영향: 종료일 이후의 signal은 포함되지 않으므로, 이 날짜가 짧으면 최근 시장 국면을 놓칠 수 있다.
- 초심자 팁: 실제 분석하려는 기간의 마지막 거래일보다 조금 넓게 잡으면 데이터 누락을 줄이기 쉽다.

#### `Strategy`

- 의미: 어떤 전략 집합을 실행할지 고르는 값이다. `Market Regime Switching`은 시장 국면 규칙까지 반영한 저장 signal을 사용한다.
- 전략 영향: 전략 선택은 진입 조건 자체를 바꾸므로, 결과 차이의 대부분이 여기서 발생한다.
- 초심자 팁: 처음에는 단일 전략(`pullback`, `breakout`, `quality_momentum`)부터 확인하고, 그 다음 조합 전략이나 regime-aware 옵션을 비교하는 것이 이해하기 쉽다.

#### `Symbols`

- 의미: 특정 종목만 쉼표로 나열해 백테스트를 좁히는 필터다.
- 전략 영향: 종목 수를 줄이면 결과 해석은 쉬워지지만, 분산이 줄어 성과가 특정 종목에 과도하게 의존할 수 있다.
- 초심자 팁: 처음에는 비워 두고 전체 signal을 보다가, 이후 관심 종목군만 따로 재현해 보는 방식이 좋다.

#### `Initial Equity`

- 의미: 백테스트 시작 시 가정하는 초기 자본이다.
- 전략 영향: 절대 손익, 포지션 크기, portfolio heat 한도, gross exposure 한도가 모두 이 값의 영향을 받는다.
- 초심자 팁: 실제 운용 자금과 비슷한 숫자를 넣어야 리스크 감각이 왜곡되지 않는다.

#### `Benchmark`

- 의미: 전략 성과를 비교할 기준 자산이다. 기본값은 `SPY`다.
- 전략 영향: 벤치마크는 직접 거래 성과를 바꾸지는 않지만, 초과수익과 상대적인 낙폭 해석을 바꾼다.
- 초심자 팁: 전략이 미국 주식 전반을 대상으로 한다면 `SPY`를 기본 비교 기준으로 쓰는 것이 이해하기 쉽다.

#### `Max Positions`

- 의미: 동시에 보유할 수 있는 최대 종목 수다.
- 전략 영향: 값이 낮으면 기회가 있어도 신규 진입이 막힐 수 있고, 값이 높으면 자본이 너무 얇게 분산될 수 있다.
- 초심자 팁: 보통 “내가 한 번에 몇 종목까지 관리할 수 있는가”와 비슷한 감각으로 보면 된다.

#### `Max Position %`

- 의미: 한 종목에 넣을 수 있는 최대 자본 비율이다.
- 전략 영향: 특정 종목 쏠림을 막아 주지만, 너무 낮으면 좋은 신호가 와도 충분히 실을 수 없다.
- 초심자 팁: 초보자는 이 값을 너무 크게 잡지 않는 편이 낫다. 한 종목의 변동성이 포트폴리오 전체를 흔드는 것을 막아 주기 때문이다.

#### `Gross Exposure`

- 의미: 전체 보유 포지션의 총 매수 노출 상한이다. 예를 들어 `1.10`이면 초기 자본의 110%까지 노출할 수 있다는 뜻이다.
- 전략 영향: 값이 높을수록 자본을 공격적으로 쓸 수 있고, 낮을수록 방어적으로 운용된다.
- 초심자 팁: 노출이 크다고 항상 좋은 것은 아니다. 추세장이 아닐 때는 과도한 노출이 손실을 키운다.

#### `Portfolio Heat`

- 의미: 동시에 열려 있는 포지션들의 초기 손절 위험 합계를 뜻한다. 쉽게 말해 “지금 열어 둔 포지션들이 한꺼번에 손절 나면 전체 자본의 몇 %를 잃을 수 있는가”를 제한하는 값이다.
- 전략 영향: 값이 낮을수록 리스크가 강하게 제한되지만, 진입 가능한 기회도 줄어든다. 값이 높으면 더 많은 포지션을 동시에 보유할 수 있지만 손실이 겹칠 위험도 커진다.
- 초심자 팁: `Gross Exposure`는 “얼마를 넣는가”, `Portfolio Heat`는 “최악의 경우 얼마를 잃을 수 있는가”에 가깝다. 둘은 비슷해 보이지만 역할이 다르다.

#### `Pullback Size Multiplier`

- 의미: `pullback` 전략에서 진입 수량에 곱해지는 배율이다.
- 전략 영향: 값이 1보다 크면 pullback 신호에 더 크게 베팅하고, 1보다 작으면 더 보수적으로 진입한다. 따라서 pullback 전략의 수익률과 변동성 모두에 영향을 준다.
- 초심자 팁: 이 값은 pullback 전략에만 적용되므로, 다른 전략까지 함께 조절하는 값으로 생각하면 안 된다.

#### `Fee bps`

- 의미: 거래 수수료를 basis point 단위로 넣는 값이다.
- 전략 영향: 비용이 높을수록 순이익이 줄고, 특히 잦은 매매를 하는 전략의 성과가 더 크게 나빠진다.
- 초심자 팁: 백테스트에서 비용을 0으로 두면 실제보다 좋게 보일 수 있다. 작은 비용이라도 넣는 습관이 중요하다.

#### `Slippage bps`

- 의미: 체결 시 가격이 불리하게 미끄러진다고 가정하는 비용이다.
- 전략 영향: 시장가 체결이 잦거나 변동성이 큰 종목에서 성과를 더 보수적으로 만든다.
- 초심자 팁: 슬리피지는 “내가 원한 가격보다 조금 더 나쁘게 체결되는 현실 비용”이라고 이해하면 된다.

#### `Max Hold Days`

- 의미: 한 포지션을 최대 몇 일까지 보유할지 정하는 값이다.
- 전략 영향: 너무 짧으면 추세가 나오기 전에 강제 청산될 수 있고, 너무 길면 좋지 않은 포지션을 오래 끌 수 있다.
- 초심자 팁: 이 값은 전략의 “인내심”이라고 생각하면 된다.

#### `Target Scale-out`

- 의미: 목표가에 도달했을 때 몇 %를 먼저 익절할지 정하는 값이다.
- 전략 영향: 값을 높이면 수익을 빨리 확정하는 대신, 이후 큰 추세를 따라가는 물량이 줄어든다. 값을 낮추면 더 오래 남겨 두어 큰 추세 수익을 기대할 수 있지만, 되돌림 위험이 커진다.
- 초심자 팁: 부분 익절은 “반은 챙기고 반은 더 먹자”는 식의 절충 장치다.

#### `Trailing MA Days`

- 의미: 남은 포지션을 추적 청산할 때 사용하는 이동평균 기간이다.
- 전략 영향: 짧은 기간은 반응이 빠르지만 노이즈에도 쉽게 청산되고, 긴 기간은 더 넉넉하지만 손익이 더 많이 되돌아갈 수 있다.
- 초심자 팁: 짧을수록 민감하고, 길수록 둔감하다고 생각하면 된다.

#### `Failed Exit Days`

- 의미: 진입 후 이 기간 안에 충분히 유리한 방향으로 움직이지 못하면 실패 거래로 보고 청산하는 규칙이다.
- 전략 영향: 이 값을 낮추면 “안 가는 종목”을 빨리 정리할 수 있지만, 아직 출발 전인 좋은 종목도 잘릴 수 있다. 높이면 기다림은 길어지지만 자본이 묶일 수 있다.
- 초심자 팁: 방향은 맞았지만 힘이 없는 종목을 오래 들고 있는 실수를 줄이기 위한 안전장치다.

#### `Failed Exit R`

- 의미: 실패 거래로 판단하기 전에 요구하는 최소 유리한 움직임의 기준이다.
- 전략 영향: 값이 높을수록 “충분히 좋아지지 않은 거래”를 더 엄격하게 잘라낸다. 값이 낮으면 실패 판정이 덜 엄격해진다.
- 초심자 팁: `R`은 진입 기준 위험 대비 보상 단위로 이해하면 된다. 예를 들어 1R은 “초기 손절 폭만큼 유리하게 움직인 상태”에 가깝다.

#### `Trailing Stop`

- 의미: 목표가에 도달한 뒤 남은 수량을 이동평균 기준으로 추적 청산할지 결정하는 옵션이다.
- 전략 영향: 켜면 추세가 이어질 때 더 오래 붙잡을 수 있지만, 노이즈에 의해 일부 수익을 되돌려 줄 수도 있다. 끄면 더 단순한 청산이 된다.
- 초심자 팁: 강한 추세를 기대하면 켜는 쪽이 유리할 수 있지만, 횡보장이 많으면 잦은 흔들림을 겪을 수 있다.

#### `Breakeven Stop`

- 의미: 일정 수준까지 유리하게 움직인 뒤 손절선을 진입가 근처로 올려 손실 전환을 줄이는 옵션이다.
- 전략 영향: 손실 거래를 줄이는 데는 도움이 되지만, 아직 크게 뻗기 전의 종목도 일찍 청산될 수 있다.
- 초심자 팁: 이 기능은 “큰 손실을 막는 대신 큰 수익의 일부를 포기할 수 있는” 안전장치다.

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

레짐은 SPY 추세와 `VIXCLS`를 함께 사용해 분류한다.

- `R1_STRONG_BULL`: `SPY > MA50 > MA200`, 20일 수익률 양수, `VIX <= 18`
- `R2_VOLATILE_BULL`: `SPY > MA200`, `VIX < 30`
- `R3_SIDEWAYS`: 위 조건 사이의 중립 구간
- `R4_EARLY_BEAR`: `SPY < MA200`, 20일 수익률 약세, 또는 `VIX >= 30`
- `R5_DEEP_BEAR`: `SPY < MA200`이면서 60일 낙폭이 깊거나 `VIX >= 40`

기본 aggressive profile 동작:

- `R1`: breakout 55%, quality momentum 45%, gross 110%
- `R2`: pullback 45%, breakout 35%, quality momentum 20%, gross 110%
- `R3`: pullback 60%, quality momentum 25%, breakout 15%, gross 60%
- `R4`, `R5`: 신규 진입 중단

기존 포지션은 Grace Period다. 즉, 레짐이 바뀌어도 이미 열린 포지션은 기존 stop/target/trailing/max-hold 규칙으로 종료한다.

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

- `Run Config`
- `Strategy vs SPY`
- `Regime Slice`
- `Symbol Contribution`
- `Strategy / Exit Summary`
- `Monthly Slice`
- `Sector Slice`
- `Strategy Slice`
- `Exit Slice`

### 해석 요령

- 초과수익이 낮고 MDD가 양호하면 진입 품질 문제일 가능성이 크다.
- `Regime Slice`에서 수익이 특정 레짐에만 집중되면, 해당 전략은 시장 국면 의존성이 높은 상태다.
- 특정 symbol contribution 쏠림이 크면 전략 분산이 부족한 상태다.
- 손실이 과도한데도 `Run Config`가 공격적으로 설정되어 있다면, 먼저 포지션 크기와 리스크 한도를 낮춰야 한다.
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
- market regime가 `R4` 또는 `R5`로 신규 진입 차단 상태인지 확인
- `VIXCLS` readiness가 깨졌는지 확인
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
