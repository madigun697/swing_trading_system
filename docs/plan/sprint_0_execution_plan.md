# Sprint 0 실행 계획 — Architecture Contract 확정

## Sprint 목표

Sprint 1 개발 착수 전에 아래 계약을 확정한다.

1. Swing/Quant 시스템 경계
2. 공유 데이터 계약
3. Swing 전용 schema/MinIO ownership
4. 포트/env/배포 계약
5. 운영/장애/보안 책임 범위
6. Sprint 1 진입 가능 여부 판단 기준

## Sprint 산출물

| 산출물 | 경로 제안 |
|---|---|
| Architecture Contract | `swing_trading_system/docs/architecture_contract.md` |
| Shared Data Contract | `swing_trading_system/docs/shared_data_contract.md` |
| Infra Runtime Contract | `swing_trading_system/docs/infra_runtime_contract.md` |
| Sprint 1 Readiness Checklist | `swing_trading_system/docs/plan/sprint_1_readiness_checklist.md` |

## S0-01. 현재 Quant shared data inventory 조사

### 목적
Swing이 재사용할 수 있는 Quant 원천/정규화/mart 데이터를 실제 코드와 DBT 기준으로 확인한다.

### 작업
- Quant DB schema/source 목록 조사
- Swing 후보 source로 사용할 relation 선정
- 문서상 후보:
  - `raw.market_daily_prices`
  - `raw.market_corporate_actions`
  - `raw.sec_*`
  - `raw.alpha_vantage_*`
  - `stg.stg_daily_prices`
  - `stg.stg_security_master`
  - `stg.stg_benchmark_series`
  - 필요 시 `mart.*`

### 산출물
- shared relation 후보 목록
- 각 relation의 owner, refresh 주기, expected columns, freshness 기준

### Acceptance Criteria
- Swing Sprint 1~3에서 읽을 최소 relation 목록 확정
- 각 relation의 “읽기 전용” 여부 명시
- freshness/readiness check 대상 확정

### 필요 subagents
- `scout`
- `senior-backend-engineer-python`
- `quant-trading-expert`

## S0-02. Swing/Quant ownership boundary 확정

### 목적
Swing이 Quant를 어디까지 재사용하고, 어디부터 독립 소유하는지 결정한다.

### 작업
- Quant 소유:
  - ingestion
  - raw/stg market/fundamental data
  - shared MinIO source archive
- Swing 소유:
  - screening result
  - strategy signal
  - trade plan
  - backtest run/result
  - position snapshot
  - alert/execution log
- Quant 코드 import 금지/허용 범위 결정
- 공통 모듈 추출은 후속 과제로 분리

### 산출물
- ownership matrix

### Acceptance Criteria
- “Swing은 Quant DB를 읽지만 Quant 내부 Python module에 직접 의존하지 않는다” 원칙 확정
- Sprint 1에서 생성할 Swing package/module boundary 확정

### 필요 subagents
- `project-manager`
- `senior-backend-engineer-python`
- `paranoid-staff-engineer-reviewer`

## S0-03. Swing 전용 schema 계약 확정

### 목적
Sprint 1에서 만들 Swing 전용 DB schema/table의 범위를 확정한다.

### 작업
- schema namespace 확정:
  - `swing_meta`
  - `swing_mart`
  - 필요 시 `swing_raw`
- 핵심 table 후보 정의:
  - `swing_meta.strategy_config`
  - `swing_meta.screening_run`
  - `swing_meta.signal`
  - `swing_meta.trade_plan`
  - `swing_meta.position_snapshot`
  - `swing_meta.alert`
  - `swing_meta.execution_order`
  - `swing_mart.swing_feature_store`
  - `swing_mart.backtest_trade_log`
  - `swing_mart.backtest_equity_curve`

### 산출물
- schema/table 계약 초안
- table별 owner/read-write policy

### Acceptance Criteria
- Quant schema와 충돌 없음
- Sprint 1에서 `init-db` 또는 migration 구현 가능한 수준의 table 목록 확정
- backtest, alert, paper execution까지 확장 가능한 구조인지 리뷰 완료

### 필요 subagents
- `senior-backend-engineer-python`
- `quant-trading-expert`
- `paranoid-staff-engineer-reviewer`

## S0-04. MinIO bucket/prefix 계약 확정

### 목적
Swing 산출물이 Quant object storage와 충돌하지 않게 한다.

### 작업
- bucket 또는 prefix naming 결정
- 후보:
  - `swing-watchlists`
  - `swing-backtests`
  - `swing-alerts`
  - `swing-executions`
- 저장 포맷 결정:
  - JSON
  - CSV/Parquet
  - chart artifact PNG/HTML 여부

### 산출물
- MinIO namespace contract

### Acceptance Criteria
- Quant bucket/prefix와 충돌 없음
- 각 artifact의 보존 기간/재생성 가능 여부 명시

### 필요 subagents
- `senior-backend-engineer-python`
- `qa-engineer`

## S0-05. Infra/env/port runtime contract 확정

### 목적
`INFRA_HOST` 기반 실행 방식을 Swing 계약에 반영한다.

### 작업
- 공통 host:
  - `INFRA_HOST`
- 기존 포트 유지:
  - PostgreSQL: `55432`
  - MinIO API: `9000`
  - MinIO Console: `9001`
  - pgAdmin: `5050`
  - Airflow: `8080`
  - Quant web: `8000`
  - Swing web: `8401`
  - Swing API reserve: `8402`
  - metrics/debug reserve: `8403`
- Swing compose가 PostgreSQL/MinIO를 새로 띄우지 않는다는 원칙 명시
- local/docker/remote infra 실행 예시 확정

### 산출물
- infra runtime contract

### Acceptance Criteria
- `.env.example`에 반영할 env key 목록 확정
- Docker/uv 실행 방식별 연결 대상이 명확함
- 포트 충돌 없음

### 필요 subagents
- `scout`
- `senior-backend-engineer-python`
- `paranoid-staff-engineer-reviewer`

## S0-06. Strategy scope v1 확정

### 목적
Sprint 2에서 구현할 전략 범위를 과도하지 않게 제한한다.

### 작업
- v1 전략 확정:
  - Pullback
  - Breakout
- 공통 signal output schema 정의:
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
- v1 제외 범위 정의:
  - LLM 판단 기반 매수/매도
  - 실거래 자동화
  - intraday 고빈도 전략

### 산출물
- strategy v1 scope

### Acceptance Criteria
- Sprint 2 구현 가능할 정도로 entry/exit/risk rule 개념 확정
- LLM은 보조 분석만 수행한다는 원칙 유지

### 필요 subagents
- `quant-trading-expert`
- `senior-backend-engineer-python`
- `paranoid-staff-engineer-reviewer`

## S0-07. Backtest safety contract 확정

### 목적
Look-ahead bias와 과최적화를 방지할 백테스트 원칙을 미리 고정한다.

### 작업
- 기준일 데이터 제한 원칙 정의
- 다음날 시가 진입 원칙 정의
- transaction cost/slippage 기본값 정의
- metric 목록 확정:
  - CAGR
  - MDD
  - Sharpe
  - Win Rate
  - Profit Factor
  - Expectancy
  - monthly returns
  - symbol contribution
- backtest result 저장 구조 초안 정의

### 산출물
- backtest safety contract

### Acceptance Criteria
- Sprint 3 백테스트 구현 시 반드시 지킬 invariant 목록 확정
- QA에서 검증할 look-ahead bias test 항목 정의

### 필요 subagents
- `quant-trading-expert`
- `qa-engineer`
- `paranoid-staff-engineer-reviewer`

## S0-08. Execution safety contract 확정

### 목적
Paper execution 이전부터 실거래 안전장치를 계약화한다.

### 작업
- 기본값:
  - `ALPACA_PAPER=true`
  - dry-run 우선
- 주문 전 validation rule 정의:
  - max positions
  - sector cap
  - risk per trade
  - duplicate order prevention
  - market open 상태
  - stale signal rejection
- live trading은 Sprint 4 이후 별도 승인 gate로 분리

### 산출물
- execution safety contract

### Acceptance Criteria
- paper/live 분리 원칙 명시
- 실거래 자동화는 Sprint 0 범위 밖으로 명확히 제외
- duplicate order 방지 요구사항 확정

### 필요 subagents
- `quant-trading-expert`
- `paranoid-staff-engineer-reviewer`
- `senior-backend-engineer-python`

## S0-09. Sprint 1 readiness checklist 작성

### 목적
Sprint 1 착수 여부를 판단할 체크리스트를 만든다.

### 체크 항목 예시
- shared relation 목록 확정
- Swing schema namespace 확정
- env/port contract 확정
- MinIO bucket/prefix 확정
- strategy v1 scope 확정
- backtest safety invariant 확정
- execution safety gate 확정

### 산출물
- `sprint_1_readiness_checklist.md`

### Acceptance Criteria
- 모든 체크 항목이 Yes/No로 판단 가능
- 미확정 항목은 owner와 deadline이 있음

### 필요 subagents
- `project-manager`
- `qa-engineer`

## S0-10. Final architecture review

### 목적
Sprint 0 산출물을 개발 착수 가능한 상태로 승인한다.

### 작업
- 전체 계약 문서 리뷰
- 모순/누락/위험 항목 정리
- Sprint 1 작업 티켓으로 분해 가능한지 확인

### 산출물
- review notes
- open decision log
- Sprint 1 kickoff 승인 여부

### Acceptance Criteria
- `paranoid-staff-engineer-reviewer` 관점에서 blocking risk 없음
- Sprint 1에서 코드 작성 가능한 수준으로 scope가 구체화됨

### 필요 subagents
- `project-manager`
- `paranoid-staff-engineer-reviewer`
- `senior-backend-engineer-python`
- `quant-trading-expert`
- `qa-engineer`

## 권장 진행 순서

### Day 1
1. S0-01 shared data inventory
2. S0-02 ownership boundary

### Day 2
3. S0-03 Swing schema contract
4. S0-04 MinIO namespace contract

### Day 3
5. S0-05 infra/env/port contract
6. S0-06 strategy scope v1

### Day 4
7. S0-07 backtest safety contract
8. S0-08 execution safety contract

### Day 5
9. S0-09 Sprint 1 readiness checklist
10. S0-10 final architecture review

## Sprint 0 Definition of Done

- [ ] Swing/Quant ownership boundary 문서화
- [ ] shared data relation 목록 확정
- [ ] Swing 전용 schema/table 초안 확정
- [ ] MinIO bucket/prefix 계약 확정
- [ ] `INFRA_HOST` 기반 runtime contract 확정
- [ ] 전략 v1 범위 확정
- [ ] backtest safety invariant 확정
- [ ] execution safety gate 확정
- [ ] Sprint 1 readiness checklist 작성
- [ ] 최종 architecture review 완료

## Sprint 1 진입 조건

1. 개발자가 schema/config/repository를 구현할 수 있을 정도로 계약이 구체적임
2. Swing이 읽을 Quant shared relation이 확정됨
3. Swing이 쓸 schema/table namespace가 확정됨
4. Docker/uv 실행 환경의 env contract가 확정됨
5. QA가 Sprint 1 smoke test 기준을 작성할 수 있음
