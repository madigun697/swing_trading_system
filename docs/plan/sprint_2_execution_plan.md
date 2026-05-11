# Sprint 2 실행 계획 — Screening & Strategy Engine

작성일: 2026-05-11

## 1. Sprint 목표

Sprint 2의 목표는 **EOD 기반 스크리너와 v1 전략 엔진(Pullback / Breakout)을 구현해, 기준일(as-of date) 기준 후보/시그널을 재현 가능하게 산출하고 Swing-owned schema에 저장하는 것**이다.

Sprint 2는 `Phase 4 — 스크리너 1차 구현`, `Phase 5 — 전략 엔진 1차 구현`을 포함한다.

## 2. Sprint 입력 전제

### 완료된 기반
- Sprint 1 foundation 완료
- `SharedMarketRepository.fetch_daily_prices()` 기반 `ScreeningInputLoader` 준비
- `ScreeningPipeline` skeleton 준비
- `swing_mart.swing_feature_store` 저장 경로 준비
- `swing_meta.screening_run`, `swing_meta.signal` 연결 준비
- Sprint 2 QA starting points 문서화
- Sprint 2 bootstrap backfill 수행 완료

### 사용 데이터 계약
- 필수:
  - `stg.stg_daily_prices`
  - `stg.stg_security_master`
  - `stg.stg_benchmark_series`
- 선택:
  - `stg.stg_listing_status_history`
  - `stg.int_universe_snapshots`
- Sprint 2에서는 기본적으로 `raw.*`, `mart.*` 직접 사용을 피한다.

## 3. Sprint 범위

### 포함
- 유동성/가격/거래량/추세/상대강도/ATR 기반 feature 계산
- screening candidate scoring
- Pullback 전략 v1
- Breakout 전략 v1
- 공통 strategy interface
- entry / stop / target / risk_per_share / position_size 산출
- screening CLI command
- strategy CLI command 또는 통합 run command
- feature / screening run / signal 저장
- look-ahead 방지 테스트

### 제외
- event-driven backtest engine 본 구현
- 웹 UI 기능 확장
- 알림/주문/paper execution
- LLM 기반 투자 판단
- live trading
- intraday 전략

## 4. Sprint 완료 기준(DoD)

- 기준일 기준 universe 후보를 산출할 수 있음
- screening feature가 `swing_mart.swing_feature_store`에 저장됨
- Pullback/Breakout 전략이 공통 interface로 signal을 생성함
- signal이 `swing_meta.signal`에 저장됨
- 모든 계산은 `trade_date <= as_of_date` 데이터만 사용함
- 최소 CLI로 screening/strategy 실행 가능
- `uv run pytest` 통과
- QA 기준의 look-ahead 방지 테스트 통과
- Strategy/risk 리뷰에서 blocking risk 없음

## 5. 작업 스트림

---

## S2-01. Screening feature model 정의

### 목적
스크리너와 전략 엔진이 공유할 feature contract를 확정한다.

### 작업
- feature dataclass 또는 typed dict 정의
- 필수 feature 목록 확정:
  - close
  - volume
  - dollar_volume
  - return_20d
  - return_60d
  - return_120d
  - relative_strength_60d
  - average_dollar_volume_20d
  - atr_14
  - atr_pct
  - volume_ratio_20d
  - ma_20
  - ma_50
  - ma_200
  - trend_up
- feature serialization rule 정의

### 산출물
- `screening/features.py`
- feature schema tests

### Acceptance Criteria
- feature 계산 결과가 JSON 직렬화 가능
- `swing_mart.swing_feature_store.features`에 저장 가능
- missing history 처리 규칙이 명확함

### 필요 subagents
- `quant-trading-expert`
- `senior-backend-engineer-python`
- `qa-engineer`

---

## S2-02. Technical indicator 계산기 구현

### 목적
외부 TA 라이브러리 의존 없이 Sprint 2에 필요한 기본 지표를 계산한다.

### 작업
- simple moving average
- rolling return
- average dollar volume
- ATR 14
- volume ratio
- relative strength vs benchmark
- 최소 history validation

### 산출물
- `screening/indicators.py`
- indicator unit tests

### Acceptance Criteria
- 입력 row가 오름차순일 때 deterministic output
- 미래 row 미사용
- NaN/None/부족한 history 처리 테스트 존재

### 필요 subagents
- `quant-trading-expert`
- `senior-backend-engineer-python`
- `qa-engineer`

---

## S2-03. Universe loader / eligibility filter 구현

### 목적
스크리닝 대상 universe를 구성하고 부적합 종목을 제거한다.

### 작업
- top liquid symbols 또는 configured symbols 조회
- minimum price filter
- minimum ADV filter
- max universe cap
- optional listing status filter
- benchmark/SPY 데이터 availability check

### 산출물
- `screening/universe.py`
- eligibility filter tests

### Acceptance Criteria
- 기준일 기준 universe만 사용
- max universe cap 준수
- 부적합 종목 제거 사유 추적 가능

### 필요 subagents
- `senior-backend-engineer-python`
- `quant-trading-expert`
- `qa-engineer`

---

## S2-04. Screener v1 구현

### 목적
feature와 eligibility를 기반으로 후보 점수를 산출한다.

### 작업
- trend filter: `ma_50 > ma_200`, close above 주요 MA
- liquidity filter: ADV/가격 기준
- relative strength score
- ATR/volatility sanity filter
- volume expansion score
- score aggregation
- candidate reason/details 생성

### 산출물
- `screening/screener.py`
- screening candidate model
- scoring tests

### Acceptance Criteria
- 동일 input에 대해 동일 candidate/score 산출
- feature store 저장과 연결 가능
- 후보별 reject/pass reason 확인 가능

### 필요 subagents
- `quant-trading-expert`
- `senior-backend-engineer-python`
- `qa-engineer`

---

## S2-05. Strategy interface 정의

### 목적
Pullback/Breakout 전략이 동일한 signal output contract를 따르게 한다.

### 작업
- `Strategy` protocol/base class 정의
- `StrategySignal` model 정의
- 공통 output fields 확정:
  - symbol
  - signal_date
  - strategy
  - entry_price
  - stop_price
  - target_price
  - risk_per_share
  - position_size
  - score
  - reason/details
- account equity/risk config 입력 구조 정의

### 산출물
- `strategies/base.py`
- strategy interface tests

### Acceptance Criteria
- repository `create_signal()`과 호환됨
- Sprint 3 backtest가 재사용 가능한 output 형태

### 필요 subagents
- `senior-backend-engineer-python`
- `quant-trading-expert`
- `paranoid-staff-engineer-reviewer`

---

## S2-06. Pullback strategy v1 구현

### 목적
상승 추세 내 조정 후 재상승 후보를 생성한다.

### v1 규칙 초안
- trend_up = true
- close > ma_200
- 최근 고점 대비 조정률이 허용 범위 내
- close가 ma_20 또는 ma_50 근처
- ATR 기반 stop 산출
- target은 최소 2R 또는 최근 고점 기준
- position size는 계좌 리스크 1% 기준

### 산출물
- `strategies/pullback.py`
- pullback tests

### Acceptance Criteria
- entry/stop/target/risk_per_share/position_size 산출
- stop < entry < target 관계 검증
- 조건 미충족 시 signal 미생성

### 필요 subagents
- `quant-trading-expert`
- `senior-backend-engineer-python`
- `qa-engineer`

---

## S2-07. Breakout strategy v1 구현

### 목적
박스/고점 돌파 + 거래량 증가 후보를 생성한다.

### v1 규칙 초안
- trend_up = true
- close가 최근 20일 고점 이상 또는 근접 돌파
- volume_ratio_20d > threshold
- ATR 기반 stop 또는 breakout level 하단 stop
- target은 최소 2R
- position size는 계좌 리스크 1% 기준

### 산출물
- `strategies/breakout.py`
- breakout tests

### Acceptance Criteria
- entry/stop/target/risk_per_share/position_size 산출
- breakout 조건 미충족 시 signal 미생성
- 과도한 gap/volatility 조건은 reject 가능

### 필요 subagents
- `quant-trading-expert`
- `senior-backend-engineer-python`
- `qa-engineer`

---

## S2-08. Screening + Strategy pipeline 통합

### 목적
기준일 기준으로 feature 계산 → candidate 선정 → 전략 signal 생성 → 저장까지 연결한다.

### 작업
- `ScreeningPipeline` 확장
- screener output을 strategy input으로 연결
- feature 저장
- screening_run status/result_count update
- signal 저장
- run summary 반환

### 산출물
- pipeline integration
- integration tests with fake repository

### Acceptance Criteria
- 한 command에서 screening/strategy 결과 저장 가능
- 실패 시 partial 상태 추적 가능
- 동일 기준일 재실행 정책 명확함

### 필요 subagents
- `senior-backend-engineer-python`
- `quant-trading-expert`
- `paranoid-staff-engineer-reviewer`
- `qa-engineer`

---

## S2-09. CLI command 추가

### 목적
운영자가 Sprint 2 기능을 command line에서 실행할 수 있게 한다.

### 작업
- `swing-system run-screening --as-of YYYY-MM-DD`
- `swing-system run-strategies --as-of YYYY-MM-DD`
- 또는 `swing-system run-daily --as-of YYYY-MM-DD`
- `--symbols`, `--max-universe`, `--dry-run` 옵션 검토
- JSON summary 출력

### 산출물
- CLI command
- CLI tests

### Acceptance Criteria
- exit code가 자동화에 적합함
- dry-run 시 DB write 없음
- 실행 결과가 JSON으로 출력됨

### 필요 subagents
- `senior-backend-engineer-python`
- `qa-engineer`

---

## S2-10. QA / 안전성 테스트 강화

### 목적
Look-ahead bias, schema boundary, 재현성을 테스트로 고정한다.

### 작업
- future row filtering test 유지/확장
- indicator가 미래 데이터를 사용하지 않는지 검증
- signal_date = as_of_date 보장
- entry는 다음 단계 backtest에서 t+1 체결됨을 문서화
- Quant schema write 금지 테스트
- deterministic scoring test

### 산출물
- Sprint 2 QA tests
- `sprint_2_review.md` 초안 또는 결과 문서

### Acceptance Criteria
- `uv run pytest` 통과
- reviewer gate에서 data leakage/blocking risk 없음

### 필요 subagents
- `qa-engineer`
- `paranoid-staff-engineer-reviewer`
- `quant-trading-expert`

## 6. 권장 실행 순서

### Day 1
1. S2-01 Screening feature model
2. S2-02 Technical indicator 계산기

### Day 2
3. S2-03 Universe loader / eligibility filter
4. S2-04 Screener v1

### Day 3
5. S2-05 Strategy interface
6. S2-06 Pullback strategy v1
7. S2-07 Breakout strategy v1

### Day 4
8. S2-08 Pipeline 통합
9. S2-09 CLI command 추가

### Day 5
10. S2-10 QA / 안전성 테스트 강화
11. Sprint 2 review 및 Sprint 3 readiness 작성

## 7. Sprint 2 종료 조건

- [x] feature model과 indicator 계산기 구현
- [x] universe eligibility filter 구현
- [x] screener v1 구현
- [x] Pullback strategy v1 구현
- [x] Breakout strategy v1 구현
- [x] strategy output이 `swing_meta.signal`에 저장됨
- [x] feature output이 `swing_mart.swing_feature_store`에 저장됨
- [x] CLI로 기준일 실행 가능
- [x] look-ahead 방지 테스트 통과
- [x] `uv run pytest` 통과
- [x] Sprint 3 backtest가 사용할 signal contract 준비

## 8. Sprint 3 진입 조건

1. signal output contract가 안정적이다.
2. `swing_meta.signal`에 backtest input으로 사용할 entry/stop/target/risk 필드가 채워진다.
3. feature store와 screening_run이 재현성 추적에 충분하다.
4. Sprint 3 backtest safety invariant와 충돌하지 않는다.
5. QA/reviewer gate에서 look-ahead/data-boundary blocking issue가 없다.

## 9. 주요 리스크와 대응

| 리스크 | 대응 |
|---|---|
| Look-ahead bias | `ScreeningInputLoader` 기준 `trade_date <= as_of_date` 테스트 유지, strategy test에 future row fixture 추가 |
| 과최적화 | v1 threshold를 단순/문서화하고 parameter search 제외 |
| 데이터 부족 종목 | minimum history rule로 reject reason 기록 |
| 저유동성 종목 | ADV/price filter를 screener 전단에 적용 |
| Quant schema write 실수 | repository contract tests 유지 |
| signal 품질 불명확 | reason/details에 feature snapshot과 reject/pass 근거 저장 |

## 10. Sprint 2 산출물 파일 후보

- `src/swing_trading_system/screening/features.py`
- `src/swing_trading_system/screening/indicators.py`
- `src/swing_trading_system/screening/universe.py`
- `src/swing_trading_system/screening/screener.py`
- `src/swing_trading_system/strategies/base.py`
- `src/swing_trading_system/strategies/pullback.py`
- `src/swing_trading_system/strategies/breakout.py`
- `tests/test_indicators.py`
- `tests/test_universe.py`
- `tests/test_screener.py`
- `tests/test_strategies.py`
- `tests/test_sprint_2_lookahead.py`
- `docs/plan/sprint_2_review.md`
