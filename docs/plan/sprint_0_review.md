# Sprint 0 Review

작성일: 2026-05-10

## 요약

Sprint 0의 목표였던 아키텍처/데이터/포트/운영 계약을 문서화했다.
이후 실제 infra 접근성과 DB/MinIO 생성 권한까지 검증했으며, Sprint 1은 바로 시작 가능하다.

## 완료 항목

- ownership boundary 확정
- shared data contract 확정
- `INFRA_HOST` 중심 runtime contract 확정
- Swing write namespace 확정
- MinIO namespace 확정
- 전략 v1 / backtest safety / execution safety 원칙 확정
- Sprint 1 readiness checklist 작성

## 승인된 핵심 결정

1. Swing은 Quant Python 모듈에 직접 의존하지 않는다.
2. shared input은 `stg` 중심으로 사용한다.
3. Swing write namespace는 `swing_meta`, `swing_mart`, optional `swing_raw`다.
4. runtime의 canonical host는 `INFRA_HOST`다.
5. Sprint 2 전략 범위는 pullback / breakout으로 제한한다.
6. backtest는 t 종가 신호, t+1 체결 원칙을 유지한다.
7. execution은 paper/dry-run 우선이다.

## 남은 비차단 결정

- `raw.market_corporate_actions` 직접 사용 여부
- `swing_raw` 도입 시점
- chart artifact 저장 방식

## 확인 완료된 운영 전제 조건

- Quant shared infra 접근 가능 (remote host)
- Swing schema 생성 권한 확보 (`quant` 계정 create/drop 검증)
- MinIO namespace 생성 권한 확보 (임시 bucket create/upload/delete/drop 검증)

## Sprint 1 판정

- 개발/설계 관점: **Approved**
- 운영 준비 관점: **Approved**

## 다음 단계

1. Sprint 1 bootstrap 착수
2. config/repository/schema 초기 구현
3. shared relation readiness smoke test 작성
4. `/healthz`와 `init-db` 기준선 구현
