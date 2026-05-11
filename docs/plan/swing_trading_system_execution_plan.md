# Swing Trading System 실행 계획

## 전제

- Swing은 Quant 인프라 PostgreSQL/MinIO를 공유한다.
- Swing은 Quant 코드 import보다 데이터 계약 공유를 우선한다.
- 초기 범위는 EOD 기반 스크리닝 → 백테스트 → UI → 알림 → Paper execution이다.
- 문서상 Phase는 `Phase 0 ~ Phase 10`이며, `Phase 0`은 Sprint 0(착수/계약 확정)으로 분리한다.

## Sprint 구성 요약

| Sprint | 포함 Phase | 핵심 목표 |
|---|---:|---|
| Sprint 0 | Phase 0 | 아키텍처/데이터/포트/운영 계약 확정 |
| Sprint 1 | Phase 1~3 | 프로젝트 골격, 공유 데이터 접근, Swing 전용 스키마 |
| Sprint 2 | Phase 4~5 | 스크리너와 눌림목/돌파 전략 엔진 |
| Sprint 3 | Phase 6~7 | 백테스트 엔진과 웹 UI 1차 |
| Sprint 4 | Phase 8~9 | 모니터링/알림, Alpaca paper execution |
| Sprint 5 | Phase 10 | 운영 안정화, 테스트, 문서, 릴리즈 준비 |

## Sprint 0 — Architecture Contract 확정

### Phase 0: 아키텍처 계약 확정

#### 목표
Swing/Quant 경계, 공유 데이터 계약, 포트, 배포, 운영 책임 범위를 명확히 확정한다.

#### 주요 업무

- Quant/Swing 경계 정의
  - 산출물: `architecture_contract.md` 초안 또는 최종 계약
  - AC: Swing shared relation 목록, 전용 schema 책임 범위 확정
  - Subagents: `project-manager`, `scout`, `quant-trading-expert`, `senior-backend-engineer-python`

- 인프라/포트/환경변수 계약 확정
  - 산출물: `INFRA_HOST`, PostgreSQL, MinIO, Swing 84xx 포트 계약
  - AC: Quant/Swing 포트 충돌 없음, Swing compose의 중복 기동 원칙 명시
  - Subagents: `scout`, `senior-backend-engineer-python`, `paranoid-staff-engineer-reviewer`

---

## Sprint 1 — Foundation & Data Layer

### Phase 1: 프로젝트 부트스트랩

- 산출물: `pyproject.toml`, `.env.example`, `docker-compose.yml`, `infra/web/Dockerfile`, 기본 FastAPI 앱, CLI, 테스트 골격
- AC: `uv sync`, `uv run swing-system --help`, `/healthz` skeleton 응답 가능
- Subagents: `senior-backend-engineer-python`, `worker`, `qa-engineer`

### Phase 2: 공유 데이터 접근 계층 구축

- 산출물: `config.py`, `storage.py`, `db.py`, `repositories/shared_market.py`, `repositories/swing_repository.py`
- AC: Quant PostgreSQL/MinIO 접속, shared table readiness check 가능
- Subagents: `scout`, `senior-backend-engineer-python`, `qa-engineer`

### Phase 3: Swing 전용 스키마 설계

- 산출물: `swing_meta.*`, `swing_mart.*`, 필요 시 `swing_raw.*`, migration/init SQL
- AC: Quant schema와 충돌 없음, trade plan/signal/backtest run/position/alert 저장 구조 정의
- Subagents: `senior-backend-engineer-python`, `quant-trading-expert`, `paranoid-staff-engineer-reviewer`

---

## Sprint 2 — Screening & Strategy Engine

### Phase 4: 스크리너 1차 구현

- 기능: 유동성/약세 제거, 상대강도, ATR, 거래량 확장, trend filter
- 산출물: `screening/` 및 candidate scoring 결과 저장
- AC: 기준일 기준 후보 산출 가능, 미래 데이터 미사용, 재현 가능
- Subagents: `quant-trading-expert`, `senior-backend-engineer-python`, `qa-engineer`

### Phase 5: 전략 엔진 1차 구현

- 기능: 눌림목, 돌파 전략
- AC: entry/stop/target 산출, 종목당 계좌 리스크 1% 계산 가능, 공통 인터페이스 사용
- Subagents: `quant-trading-expert`, `senior-backend-engineer-python`, `paranoid-staff-engineer-reviewer`

---

## Sprint 3 — Backtest & Web UI v1

### Phase 6: 백테스트 엔진 구축

- 기능: 일봉 event-driven 백테스트, 손절/익절, 거래비용, 슬리피지, 포지션 사이징, equity curve/trade log 저장
- AC: look-ahead bias 방지, 재현 가능한 결과, 핵심 성과 지표 계산 가능
- Subagents: `quant-trading-expert`, `senior-backend-engineer-python`, `qa-engineer`, `paranoid-staff-engineer-reviewer`

### Phase 7: 웹 UI 1차 구현

- 화면: 데이터 상태, 스크리닝 결과, 차트, 백테스트 설정/결과, 거래 로그, 성과 분석, trade plan, position/alert
- AC: `/healthz` readiness, 후보 조회, 백테스트 실행/결과 조회, 기본 차트 렌더링
- Subagents: `senior-frontend-engineer`, `ui-ux-designer`, `senior-backend-engineer-python`, `qa-engineer`

---

## Sprint 4 — Monitoring, Alerts & Paper Execution

### Phase 8: 모니터링/알림

- 기능: 후보 digest, 포지션 stop/target 체크, alert 생성, Slack/Telegram/Email notifier
- AC: end-of-day CLI 실행, alert dry-run, notifier 실패 분리 처리
- Subagents: `senior-backend-engineer-python`, `qa-engineer`, `paranoid-staff-engineer-reviewer`

### Phase 9: Paper execution 연동

- 기능: trade plan 제출, dry-run, paper order 생성, execution result 저장
- AC: 실거래 API와 paper API 분리, `ALPACA_PAPER=true` 기본값, 주문 전 최종 risk validation 통과
- Subagents: `senior-backend-engineer-python`, `quant-trading-expert`, `paranoid-staff-engineer-reviewer`, `qa-engineer`

---

## Sprint 5 — Hardening, QA & Release

### Phase 10: 운영 안정화

- 산출물: dbt, tests, `docs/operations_runbook.md`, troubleshooting, 배포/롤백/전환 체크리스트
- AC: 신규 환경에서 문서만 보고 실행 가능, 장애 복구 절차 존재
- Subagents: `project-manager`, `qa-engineer`, `paranoid-staff-engineer-reviewer`

---

## Phase → Sprint 매핑

| Phase | 내용 | Sprint |
|---:|---|---|
| 0 | 아키텍처 계약 확정 | Sprint 0 |
| 1 | 프로젝트 부트스트랩 | Sprint 1 |
| 2 | 공유 데이터 접근 계층 | Sprint 1 |
| 3 | Swing 전용 스키마 | Sprint 1 |
| 4 | 스크리너 1차 | Sprint 2 |
| 5 | 전략 엔진 1차 | Sprint 2 |
| 6 | 백테스트 엔진 | Sprint 3 |
| 7 | 웹 UI 1차 | Sprint 3 |
| 8 | 모니터링/알림 | Sprint 4 |
| 9 | Paper execution | Sprint 4 |
| 10 | 운영 안정화 | Sprint 5 |

## 주요 리스크

1. Look-ahead bias
2. Quant shared schema 변경 리스크
3. 실거래 안전장치
4. 알림/주문 중복 실행
5. 전략 과최적화

## 권장 다음 단계

1. Sprint 0부터 시작
2. `architecture_contract.md`를 현재 코드 상태 기준으로 갱신
3. Sprint 1 착수 전 shared relation 목록 확정
4. 각 Sprint 종료 시 산출물 리뷰 + QA 체크 + 안전성 리뷰 수행
5. Paper execution 전까지는 dry-run/mock 우선으로 제한
