# Swing Trading System Shared Data Contract

작성일: 2026-05-10

## 1. 목적

Swing가 Quant 인프라의 어떤 relation을 읽을 수 있는지, 어떤 relation을 기본 계약으로 삼는지, freshness/readiness를 어떻게 확인할지 정의한다.

## 2. 기본 원칙

1. Swing의 기본 입력 계약은 `raw`보다 `stg` 우선이다.
2. `int_*`는 명시적 목적이 있을 때만 사용한다.
3. `mart.*`는 Quant 전략/팩터 재사용이 필요할 때만 선택적으로 읽는다.
4. Quant 소유 relation은 모두 **read-only**다.

## 3. 핵심 shared relations

| Relation | 용도 | Sprint | 읽기 정책 |
|---|---|---:|---|
| `stg.stg_daily_prices` | canonical EOD OHLCV/adjusted price | 1~4 | 필수 |
| `stg.stg_security_master` | symbol/stable_id/sector/security metadata | 1~4 | 필수 |
| `stg.stg_benchmark_series` | SPY/FRED benchmark, 시장 상태/비교지표 | 1~4 | 필수 |
| `stg.stg_listing_status_history` | listing/delisting/tradability history | 2~4 | 선택 |
| `stg.int_universe_snapshots` | Quant selected universe snapshot | 2~4 | 선택 |
| `stg.int_point_in_time_fundamentals` | PIT fundamentals | 2~4 | 선택 |
| `raw.market_corporate_actions` | split/dividend event raw source | 2~4 | 예외적 선택 |

## 4. Relation별 계약

### 4.1 `stg.stg_daily_prices`
- 역할: Swing의 기본 가격 입력
- 사용 목적:
  - screening
  - ATR/거래량/모멘텀 계산
  - backtest price source
- 제약:
  - vendor priority는 Quant dbt 결과를 그대로 신뢰
  - Swing은 이 relation을 수정하지 않음

### 4.2 `stg.stg_security_master`
- 역할: 종목 identity / sector / listing 메타데이터
- 사용 목적:
  - 종목 필터링
  - 섹터 상한
  - stable_id 기준 join
- 제약:
  - raw SEC/Alpha Vantage 직접 join 대신 우선 사용

### 4.3 `stg.stg_benchmark_series`
- 역할: 벤치마크/시장 상태 기준 시계열
- 사용 목적:
  - SPY 비교 수익률
  - 시장 필터
  - risk regime proxy

### 4.4 `stg.stg_listing_status_history`
- 역할: 상장/폐지/거래 가능 상태 추적
- 사용 목적:
  - survivorship bias 완화
  - trade eligibility 점검

### 4.5 `stg.int_universe_snapshots`
- 역할: Quant가 선별한 universe snapshot 재사용
- 사용 목적:
  - Swing가 universe를 완전히 새로 만들지 않고 Quant 상위 유동성 universe 위에서 동작하고 싶을 때 사용
- 제약:
  - Quant universe 로직에 간접 의존하므로 선택적으로만 채택

### 4.6 `stg.int_point_in_time_fundamentals`
- 역할: look-ahead 방지된 PIT fundamentals
- 사용 목적:
  - 정성/정량 혼합 필터
  - 전략 보조 feature
- 제약:
  - Sprint 1 필수는 아님

### 4.7 `raw.market_corporate_actions`
- 역할: corporate actions raw event source
- 사용 목적:
  - 필요 시 split/dividend 보정 근거 확인
- 제약:
  - stg 정규화 계층이 없으므로 기본 입력으로는 사용하지 않음
  - 사용 시 Swing 내부에서 명시적 정규화 규칙을 정의해야 함

## 5. 읽지 않는 것을 원칙으로 하는 relation

| Relation | 이유 |
|---|---|
| `raw.*` 일반 relation | schema drift / 정규화 부족 가능성 |
| `meta.*` 일반 relation | Quant 내부 운영 상태에 과도 의존 가능 |
| `mart.*` 전체 | Quant 전략 산출물과 Swing 전략이 강결합될 위험 |

## 6. Freshness / Readiness 계약

### Sprint 1 최소 readiness
다음 relation이 존재해야 한다.
- `stg.stg_daily_prices`
- `stg.stg_security_master`
- `stg.stg_benchmark_series`

### 최소 freshness 신호
- `stg.stg_daily_prices.max(effective_as_of)`
- `stg.stg_benchmark_series.max(observation_date)`
- 필요 시 `meta.ingestion_watermarks`
- 필요 시 `raw.ingestion_artifacts`

### Ready 판정
- relation 존재
- 최근 데이터 날짜가 전략 실행 기준에 부합
- support symbol/SPY 데이터가 비어 있지 않음

## 7. 쓰기 금지 계약

Swing는 아래에 대해 write/upsert/delete를 수행하지 않는다.
- `raw.*`
- `stg.*`
- `meta.*`
- `mart.*`

## 8. Sprint 1에서 확정된 사용 권장안

### 필수 사용
- `stg.stg_daily_prices`
- `stg.stg_security_master`
- `stg.stg_benchmark_series`

### Sprint 2 이후 선택 사용
- `stg.stg_listing_status_history`
- `stg.int_point_in_time_fundamentals`
- `stg.int_universe_snapshots`

### 보류
- `raw.market_corporate_actions`

## 9. Sprint 1 진입 판정

Shared data contract 관점에서 Sprint 1은 **Ready**다.
단, 실제 개발/테스트 착수 시 Quant infra 접근 가능성과 DB 권한은 별도 운영 전제다.
