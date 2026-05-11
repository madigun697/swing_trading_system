# Swing Trading System Architecture Contract

작성일: 2026-05-10

## 1. 목적

이 문서는 `swing_trading_system`과 `quant_trading_system` 사이의 시스템 경계, 소유권, 통합 방식, 확장 원칙을 정의한다.
Sprint 1 이후 구현은 이 계약을 기준으로 진행한다.

## 2. 핵심 원칙

1. **인프라는 공유하고 도메인 코드는 분리한다.**
2. **데이터 계약 공유를 우선하고 Python 모듈 직접 의존은 피한다.**
3. **Swing은 Quant 데이터를 읽되 Quant의 ingestion 책임을 가져오지 않는다.**
4. **실거래 자동화보다 EOD 분석/백테스트/paper execution을 우선한다.**
5. **안전성 규칙은 구현보다 먼저 계약으로 확정한다.**

## 3. 시스템 경계

### Quant 소유
- 시장/재무/SEC/FRED 데이터 ingestion
- 공유 PostgreSQL raw/stg/mart/meta 데이터 파이프라인
- 공유 MinIO 원천 archive
- Airflow 기반 적재/변환 orchestration
- Quant 전용 web/backtest UI

### Swing 소유
- swing 전용 screening logic
- swing 전용 strategy signal
- swing 전용 trade plan / position / alert / execution log
- swing 전용 backtest engine / UI / CLI / notifier / paper execution adapter
- swing 전용 schema와 object storage namespace

## 4. 코드 의존성 계약

### 허용
- Quant 문서/구현 패턴 참고
- Quant DB schema 및 dbt relation 읽기
- Quant와 동일한 infra/runtime 패턴 재사용

### 금지
- `swing_trading_system`이 `quant_trading_system`의 내부 Python 모듈을 직접 import하여 핵심 기능에 의존하는 것
- Swing이 Quant raw/meta/stg/mart relation에 쓰기 수행하는 것
- Swing이 Quant ingestion 책임을 가져가는 것

### 예외
- 향후 공통 패키지 추출은 가능하나, 이는 별도 리팩터링 과제로 분리한다.

## 5. 데이터 ownership

### Shared read-only contract
- `stg.stg_daily_prices`
- `stg.stg_security_master`
- `stg.stg_benchmark_series`
- 필요 시 `stg.stg_listing_status_history`
- 필요 시 `stg.int_universe_snapshots`
- 필요 시 `stg.int_point_in_time_fundamentals`
- 제한적 예외로 `raw.market_corporate_actions` read-only 사용 가능

### Swing write contract
- `swing_meta.*`
- `swing_mart.*`
- 필요 시 `swing_raw.*`
- `swing-*` MinIO bucket/prefix

## 6. Swing 전용 schema namespace

### 확정 namespace
- `swing_meta`
- `swing_mart`
- `swing_raw` (선택)

### Sprint 1 기준 최소 테이블 후보
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

## 7. 실행 단계 계약

### v1 범위
1. shared data read
2. screening
3. pullback / breakout signal
4. event-driven daily backtest
5. web UI
6. notifier
7. Alpaca paper execution

### v1 제외 범위
- LLM 직접 매수/매도 결정
- live trading 자동화
- intraday/HFT 전략
- Quant factor mart 재사용을 전제로 한 강결합 구조

## 8. 전략/백테스트/실행 안전 원칙

### Strategy v1
- 미국 주식 일봉 기준
- long-only swing만 허용
- 보유 5~20 영업일 범위
- 동시 보유 종목 수 상한 적용
- 종목당 리스크 한도와 섹터 cap 적용

### Backtest safety
- 신호는 `t`일 종가 확정 후 생성
- 체결은 `t+1` 시가 또는 더 보수적인 체결 규칙만 허용
- same-bar 진입/청산 금지
- 상장폐지/거래정지/분할/배당 처리 규칙 명시
- 수수료/슬리피지/갭 비용 반영

### Execution safety
- `ALPACA_PAPER=true` 기본
- dry-run 우선
- duplicate order 방지
- stale signal rejection
- 일손실/주손실 kill switch 도입 예정

## 9. 구현 순서상 의존성

- Sprint 1은 이 계약을 기준으로 config/repository/schema를 구현한다.
- Sprint 2는 여기서 확정한 전략 v1 범위를 넘지 않는다.
- Sprint 3은 여기서 확정한 backtest invariant를 깨지 않는다.
- Sprint 4는 paper/live safety gate를 유지한다.

## 10. 남겨둔 결정(비차단)

1. `raw.market_corporate_actions`를 Sprint 2에서 직접 읽을지, Swing 내부 정규화 레이어를 만들지
2. `swing_raw`를 Sprint 1부터 만들지, Sprint 4 이후에 도입할지
3. chart artifact를 MinIO에 저장할지 DB/파일 기반으로 처리할지

## 11. Sprint 1 진입 판정

다음 조건을 만족하므로 **Sprint 1 착수 가능**으로 판정한다.

- 경계와 ownership이 문서화되었다.
- shared read contract가 확정되었다.
- Swing write namespace가 확정되었다.
- runtime/env 원칙이 별도 계약으로 분리되었다.
- 남은 미결정 사항은 모두 비차단이다.
