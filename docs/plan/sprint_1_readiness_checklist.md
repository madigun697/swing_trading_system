# Sprint 1 Readiness Checklist

작성일: 2026-05-10

## 판정 요약

- Sprint 1 상태: **READY**
- 확인 완료:
  1. Quant shared infra 접근 가능
  2. Swing schema 생성 권한 확인 완료
  3. MinIO bucket/prefix 생성 권한 확인 완료

## 체크리스트

| 항목 | 상태 | 비고 |
|---|---|---|
| Swing/Quant ownership boundary 문서화 | Ready | `architecture_contract.md` |
| shared read contract 확정 | Ready | `shared_data_contract.md` |
| Swing write namespace 확정 | Ready | `swing_meta`, `swing_mart`, optional `swing_raw` |
| `INFRA_HOST` 기반 runtime contract 확정 | Ready | `infra_runtime_contract.md` |
| Swing compose가 Quant infra를 중복 기동하지 않는 원칙 확정 | Ready | Sprint 1 compose 구현 기준 |
| 필수 shared relation 목록 확정 | Ready | `stg.stg_daily_prices`, `stg.stg_security_master`, `stg.stg_benchmark_series` |
| readiness/freshness 최소 기준 확정 | Ready | relation 존재 + latest date/freshness 확인 |
| MinIO namespace 확정 | Ready | `swing-watchlists`, `swing-backtests`, `swing-alerts`, `swing-executions` |
| 전략 v1 범위 확정 | Ready | pullback / breakout, long-only, EOD |
| backtest safety invariant 확정 | Ready | t 종가 신호, t+1 체결, same-bar 금지 |
| execution safety gate 확정 | Ready | paper default, dry-run 우선, duplicate prevention |
| Sprint 1 산출물 범위 확정 | Ready | bootstrap + config/storage/db + repository + schema |
| Quant infra 접근성 확인 | Ready | remote Quant host 기준 PostgreSQL/MinIO/pgAdmin/Airflow/Quant web 포트 접근 확인 |
| DB schema 생성 권한 확인 | Ready | `quant` 계정으로 schema/table create/drop 검증 완료 |
| MinIO bucket/prefix 생성 권한 확인 | Ready | 임시 bucket create/upload/delete/drop 검증 완료 |

## Sprint 1 시작 조건

아래 조건을 만족하면 Sprint 1을 시작한다.

- [x] 문서 계약이 개발자가 바로 구현 가능한 수준으로 구체화됨
- [x] shared read contract가 확정됨
- [x] Swing write namespace가 확정됨
- [x] env/runtime/port contract가 확정됨
- [x] safety contract가 확정됨
- [x] Quant infra 접근 권한 확보
- [x] DB/MinIO 생성 권한 확보

## Sprint 1 권장 착수 순서

1. 프로젝트 부트스트랩
2. config/storage/db 구현
3. shared market repository 구현
4. swing repository 구현
5. schema init/migration 추가
6. `/healthz` 및 CLI skeleton 추가
7. smoke test 작성

## Blocker 여부

- 문서/설계 기준 blocker: **없음**
- 운영 권한 기준 blocker: **없음**
