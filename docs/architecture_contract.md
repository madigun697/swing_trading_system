# Swing / Quant 아키텍처 계약

## 시스템 경계
- `quant_trading_system/`
  - 책임: 공용 시장/재무 데이터 수집, 정규화, dbt staging/intermediate/mart 관리
  - 소유 스키마: `raw`, `stg`, `mart`, `meta`
- `swing_trading_system/`
  - 책임: 스윙 후보 선별, 전략 규칙, trade plan, position tracking, alerting, paper execution, swing UI
  - 소유 스키마: `swing_meta`, `swing_mart`, `swing_raw`

## 데이터 계약
Swing는 아래 shared relation을 read-only consumer로 사용한다.
- `stg.stg_daily_prices`
- `stg.stg_security_master`
- `stg.stg_benchmark_series`
- 필요 시 `raw.market_daily_prices`, `raw.sec_*`, `raw.alpha_vantage_*`

Swing가 직접 수정 가능한 대상은 아래로 제한한다.
- `swing_meta.*`
- `swing_mart.*`
- `swing_raw.*`
- MinIO `swing-*` bucket/prefix

## 배포 계약
- Quant와 Swing는 별도 compose / 별도 app / 별도 release unit으로 배포한다.
- Swing 배포는 Quant web/API 재시작을 요구하지 않는다.
- Quant 장애가 아니면 Swing만 독립적으로 롤백 가능해야 한다.

## 포트 계약
- Quant existing: `55432`, `9000`, `9001`, `5050`, `8080`, `8000`
- Swing reserved: `8401`, `8402`, `8403`

## 운영 계약
- 장 마감 후 shared data freshness 확인 후 Swing screening 실행
- 신호/백테스트/알림 결과는 swing schema와 swing bucket에만 기록
- Paper execution은 opt-in이며 기본은 dry-run이다.
