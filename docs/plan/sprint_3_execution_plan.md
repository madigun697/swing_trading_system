# Sprint 3 실행 계획 — Backtest & Web UI v1

작성일: 2026-05-11

## 1. Sprint 목표

Sprint 3의 목표는 **Sprint 2에서 생성된 `swing_meta.signal`을 입력으로 일봉 event-driven 백테스트를 수행하고, 결과를 `swing_mart.backtest_*`에 저장한 뒤, Web UI v1에서 데이터 상태/시그널/백테스트 결과를 조회할 수 있게 하는 것**이다.

Sprint 3는 아래 Phase를 포함한다.

- Phase 6: 백테스트 엔진 구축
- Phase 7: 웹 UI 1차 구현

## 2. Sprint 입력 전제

### 완료된 기반
- Sprint 1 foundation 완료
- Sprint 2 screening/strategy engine 완료
- `swing-system run-daily`로 feature/signal 생성 가능
- 실제 저장 검증 완료:
  - `swing_mart.swing_feature_store` `screening_v1` rows 존재
  - `swing_meta.signal`에 entry/stop/target/risk field가 채워진 signal 존재

### Sprint 3 시작 기준
- `swing_meta.signal`을 backtest input으로 읽을 수 있어야 한다.
- `stg.stg_daily_prices`에서 signal 이후 가격 데이터를 읽을 수 있어야 한다.
- Backtest invariant는 Sprint 0 계약을 따른다.

## 3. Backtest Safety Invariant

Sprint 3 구현은 아래 원칙을 반드시 지킨다.

1. signal은 `t`일 종가 기준으로 생성된 것으로 간주한다.
2. 진입은 `t+1` 시가를 기본 체결가로 사용한다.
3. same-bar 진입/청산은 금지한다.
4. 청산 판정은 진입일 이후 bar부터 수행한다.
5. stop/target 동시 터치 시 보수적으로 stop 우선 처리한다.
6. 수수료/슬리피지 기본값을 반영한다.
7. 결과는 재현 가능해야 하며 run config를 저장한다.
8. Quant-owned schema에는 write하지 않는다.

## 4. Sprint 범위

### 포함
- signal repository/query
- price series loader for backtest
- event-driven daily backtest engine
- stop/target/max-hold exit 처리
- transaction cost/slippage 반영
- trade log/equity curve/summary metric 계산
- `swing_mart.backtest_trade_log` 저장
- `swing_mart.backtest_equity_curve` 저장
- backtest CLI command
- Web UI v1:
  - `/healthz`
  - 데이터 상태
  - 최근 시그널 조회
  - 백테스트 실행/결과 조회
  - 기본 trade log/equity curve 표시

### 제외
- 고급 포트폴리오 최적화
- intraday 백테스트
- 실거래/paper execution
- 알림/notifier
- 고급 차트 인터랙션
- LLM 분석 UI

## 5. Sprint 완료 기준(DoD)

- `swing_meta.signal` 기반 backtest를 실행할 수 있음
- `t signal → t+1 open entry` invariant가 테스트로 고정됨
- trade log가 `swing_mart.backtest_trade_log`에 저장됨
- equity curve가 `swing_mart.backtest_equity_curve`에 저장됨
- 핵심 metric 계산 가능:
  - total return
  - CAGR 또는 기간 수익률
  - MDD
  - win rate
  - profit factor
  - expectancy
- CLI로 backtest 실행 가능
- Web UI v1에서 health/data/signal/backtest 결과 조회 가능
- `uv run pytest` 통과
- reviewer/QA gate에서 look-ahead/data-boundary blocking issue 없음

## 6. 작업 스트림

---

## S3-01. Backtest input repository 구현

### 목적
Sprint 2 signal을 백테스트 입력으로 안정적으로 조회한다.

### 작업
- `swing_meta.signal` 조회 repository 추가
- 필수 field validation:
  - symbol
  - signal_date
  - strategy
  - entry_price
  - stop_price
  - target_price
  - risk_per_share
  - position_size
- signal date range filter
- strategy filter
- symbol filter
- backtest run candidate validation

### 산출물
- `backtest/repository.py` 또는 `repositories/backtest_repository.py`
- signal input model
- repository tests

### Acceptance Criteria
- Sprint 2 signal contract와 호환됨
- 필수 field 누락 signal은 skip/reject reason 제공
- Quant-owned schema write 없음

### 필요 subagents
- `senior-backend-engineer-python`
- `qa-engineer`

---

## S3-02. Backtest price loader 구현

### 목적
진입/청산 시뮬레이션에 필요한 OHLCV를 `stg.stg_daily_prices`에서 읽는다.

### 작업
- symbol/date range price load
- signal_date 이후 가격 조회
- `t+1` entry bar 찾기
- missing price handling
- insufficient future bars handling

### 산출물
- price loader function 또는 repository method
- price loader tests

### Acceptance Criteria
- entry bar는 signal_date보다 큰 첫 번째 trading day
- same-day entry 불가
- missing data는 명확한 reject reason 반환

### 필요 subagents
- `senior-backend-engineer-python`
- `qa-engineer`
- `paranoid-staff-engineer-reviewer`

---

## S3-03. Backtest domain model 정의

### 목적
백테스트 엔진과 저장 계층 사이의 데이터 계약을 명확히 한다.

### 작업
- `BacktestConfig`
- `BacktestRunSummary`
- `BacktestTrade`
- `EquityCurvePoint`
- `BacktestRejection`
- JSON serialization rule

### 산출물
- `backtest/models.py`
- model tests

### Acceptance Criteria
- DB 저장 가능한 형태로 직렬화 가능
- run config가 결과 재현에 충분함
- Sprint 4/5 운영 문서화에 재사용 가능

### 필요 subagents
- `senior-backend-engineer-python`
- `qa-engineer`

---

## S3-04. Event-driven daily backtest engine 구현

### 목적
일봉 OHLCV 기준으로 stop/target/max-hold 백테스트를 수행한다.

### 작업
- signal별 t+1 open entry
- stop loss 처리
- target 처리
- max hold days 처리
- stop/target 동시 터치 시 stop 우선
- 수수료/슬리피지 반영
- position sizing 적용
- trade log 생성

### 산출물
- `backtest/engine.py`
- engine unit tests

### Acceptance Criteria
- look-ahead bias 방지 테스트 통과
- same-bar entry/exit 금지
- stop/target/max-hold 각각 테스트 존재
- deterministic result

### 필요 subagents
- `quant-trading-expert`
- `senior-backend-engineer-python`
- `paranoid-staff-engineer-reviewer`
- `qa-engineer`

---

## S3-05. Performance metrics 구현

### 목적
백테스트 결과를 평가할 핵심 지표를 계산한다.

### 작업
- total return
- CAGR 또는 기간 수익률
- MDD
- win rate
- profit factor
- expectancy
- average win/loss
- exposure days
- symbol/strategy contribution summary

### 산출물
- `backtest/metrics.py`
- metric tests

### Acceptance Criteria
- 빈 trade / 전부 손실 / 전부 이익 케이스 처리
- divide-by-zero 방지
- UI/CLI가 사용할 summary dict 제공

### 필요 subagents
- `quant-trading-expert`
- `senior-backend-engineer-python`
- `qa-engineer`

---

## S3-06. Backtest result persistence 구현

### 목적
trade log와 equity curve를 Swing-owned mart schema에 저장한다.

### 작업
- `swing_mart.backtest_trade_log` insert
- `swing_mart.backtest_equity_curve` upsert/insert
- run_id 생성 규칙
- result summary 저장 위치 결정
- idempotency 정책 정의

### 산출물
- repository persistence methods
- persistence tests

### Acceptance Criteria
- `swing_mart.*`에만 write
- 동일 run_id 재실행 정책 명확함
- 저장 후 조회 가능

### 필요 subagents
- `senior-backend-engineer-python`
- `qa-engineer`
- `paranoid-staff-engineer-reviewer`

---

## S3-07. Backtest CLI command 추가

### 목적
운영자/개발자가 CLI로 백테스트를 실행할 수 있게 한다.

### 작업
- `swing-system run-backtest`
- 옵션:
  - `--start-date`
  - `--end-date`
  - `--strategy`
  - `--symbols`
  - `--initial-equity`
  - `--fee-bps`
  - `--slippage-bps`
  - `--max-hold-days`
  - `--dry-run`
- JSON summary 출력

### 산출물
- CLI command
- CLI tests

### Acceptance Criteria
- dry-run 시 DB write 없음
- write run 시 trade/equity 저장
- exit code가 자동화에 적합함

### 필요 subagents
- `senior-backend-engineer-python`
- `qa-engineer`

---

## S3-08. Web service/repository layer 구현

### 목적
Web UI가 백테스트/시그널/데이터 상태를 조회할 backend service를 만든다.

### 작업
- health/readiness 확장
- recent signals service
- backtest run service
- backtest result 조회 service
- error classification

### 산출물
- `web/services/`
- `web/repositories/` 또는 기존 repository 재사용
- service tests

### Acceptance Criteria
- service layer가 FastAPI route와 분리됨
- fake service로 route test 가능
- DB 오류가 503/500으로 구분됨

### 필요 subagents
- `senior-backend-engineer-python`
- `qa-engineer`

---

## S3-09. Web UI v1 route/template 구현

### 목적
브라우저에서 Sprint 3 핵심 정보를 확인할 수 있게 한다.

### 화면 후보
- `/`
  - 데이터 상태
  - latest shared trade date
  - signal count
  - latest backtest run summary
- `/signals`
  - 최근 signal list
  - strategy/symbol/date filter
- `/backtests`
  - backtest form
  - recent runs/results
- `/backtests/{run_id}`
  - metric summary
  - trade log table
  - equity curve 기본 표시

### 산출물
- FastAPI routes
- Jinja2 templates 또는 단순 HTML response
- route tests

### Acceptance Criteria
- `/healthz` 유지
- `/`, `/signals`, `/backtests` 최소 응답 가능
- 백테스트 실행/결과 조회 흐름이 동작
- UI는 v1 단순 HTML로 제한

### 필요 subagents
- `senior-frontend-engineer`
- `ui-ux-designer`
- `senior-backend-engineer-python`
- `qa-engineer`

---

## S3-10. Look-ahead / backtest safety QA 강화

### 목적
Sprint 3의 핵심 리스크인 look-ahead bias를 테스트로 고정한다.

### 테스트 항목
- signal_date 당일 open/close로 entry하지 않음
- t+1 open을 entry로 사용
- entry bar에서 즉시 stop/target 처리하지 않음
- stop/target 동시 터치 시 stop 우선
- future data 없이 max-hold exit 계산
- missing next bar signal reject

### 산출물
- `tests/test_backtest_safety.py`

### Acceptance Criteria
- 안전 invariant가 regression test로 고정됨
- reviewer gate에서 blocking issue 없음

### 필요 subagents
- `qa-engineer`
- `paranoid-staff-engineer-reviewer`
- `quant-trading-expert`

---

## S3-11. Sprint 3 문서/리뷰 작성

### 목적
Sprint 3 결과와 Sprint 4 진입 조건을 문서화한다.

### 작업
- `sprint_3_review.md` 작성
- 실제 backtest run 결과 기록
- Web UI v1 endpoint 목록 기록
- Sprint 4 monitoring/alerts readiness 작성

### 산출물
- `docs/plan/sprint_3_review.md`

### Acceptance Criteria
- Sprint 4에서 alert/paper execution이 사용할 backtest/signal 상태가 명확함

### 필요 subagents
- `project-manager`
- `qa-engineer`

## 7. 권장 실행 순서

### Day 1
1. S3-01 Backtest input repository
2. S3-02 Backtest price loader
3. S3-03 Backtest domain model

### Day 2
4. S3-04 Event-driven daily backtest engine
5. S3-05 Performance metrics

### Day 3
6. S3-06 Backtest result persistence
7. S3-07 Backtest CLI command

### Day 4
8. S3-08 Web service/repository layer
9. S3-09 Web UI v1 route/template

### Day 5
10. S3-10 Look-ahead / backtest safety QA
11. S3-11 Sprint 3 review 및 Sprint 4 readiness 정리

## 8. Sprint 3 종료 조건

- [x] signal input repository 구현
- [x] backtest price loader 구현
- [x] backtest domain model 구현
- [x] event-driven daily backtest engine 구현
- [x] performance metrics 구현
- [x] trade log/equity curve persistence 구현
- [x] `swing-system run-backtest` 제공
- [x] Web UI v1 endpoint 제공
- [x] look-ahead safety tests 통과
- [x] `uv run pytest` 통과
- [x] 실제 저장된 signal 기반 backtest run 1회 이상 성공
- [x] Sprint 4 진입 조건 문서화

## 9. Sprint 4 진입 조건

1. backtest 결과가 `swing_mart.backtest_trade_log`, `swing_mart.backtest_equity_curve`에 저장된다.
2. Web UI에서 signal과 backtest 결과를 조회할 수 있다.
3. monitoring/alert가 참조할 position/trade plan 후보 데이터 구조가 명확하다.
4. backtest safety invariant가 테스트로 고정되어 있다.
5. Sprint 4 paper execution safety gate와 충돌하지 않는다.

## 10. 주요 리스크와 대응

| 리스크 | 대응 |
|---|---|
| Look-ahead bias | t+1 open entry, same-bar exit 금지 테스트 필수 |
| Overfitting | Sprint 3에서는 parameter optimization 제외 |
| DB result 중복 | run_id/idempotency 정책 명시 |
| 가격 데이터 누락 | missing next bar / insufficient future bars reject 처리 |
| Web UI 범위 확장 | v1 단순 조회/실행 UI로 제한 |
| Performance | 초기에는 max universe/run 제한, 추후 최적화 |

## 11. Sprint 3 산출물 파일 후보

- `src/swing_trading_system/backtest/models.py`
- `src/swing_trading_system/backtest/engine.py`
- `src/swing_trading_system/backtest/metrics.py`
- `src/swing_trading_system/backtest/repository.py`
- `src/swing_trading_system/web/services/backtest_service.py`
- `src/swing_trading_system/web/routes.py`
- `src/swing_trading_system/web/templates/*.html`
- `tests/test_backtest_engine.py`
- `tests/test_backtest_metrics.py`
- `tests/test_backtest_safety.py`
- `tests/test_backtest_repository.py`
- `tests/test_web_routes.py`
- `docs/plan/sprint_3_review.md`
