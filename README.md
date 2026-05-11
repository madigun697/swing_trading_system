# Swing Trading System

독립적인 스윙 트레이딩 시스템입니다. 전략/백테스트/UI는 별도 코드베이스로 유지하지만,
시장/재무 원천 데이터는 기존 `quant_trading_system`의 `PostgreSQL`/`MinIO`를 공유합니다.

## 아키텍처 원칙
- Quant = 공용 시장/재무 데이터 producer
- Swing = 공용 데이터 consumer + swing 전용 signal/plan/position owner
- Swing는 Quant 전략/실행 코드를 import하지 않음
- Swing 전용 DB 스키마: `swing_meta`, `swing_mart`, `swing_raw`
- Swing 전용 포트: `8401`, `8402`, `8403`

## Quant와 포트 분리
현재 Quant가 사용 중인 포트:
- PostgreSQL: `${INFRA_HOST}:55432`
- MinIO API: `http://${INFRA_HOST}:9000`
- MinIO Console: `http://${INFRA_HOST}:9001`
- pgAdmin: `http://${INFRA_HOST}:5050`
- Airflow: `http://${INFRA_HOST}:8080`
- Quant web: `http://${INFRA_HOST}:8000`

Swing 기본 포트:
- Swing web: `http://${INFRA_HOST}:8401`
- Swing API reserve: `http://${INFRA_HOST}:8402`
- metrics/debug reserve: `http://${INFRA_HOST}:8403`

## 빠른 시작
```bash
cp .env.example .env
uv sync
# 필요하면 .env 의 INFRA_HOST 만 원하는 infra IP/host로 변경
uv run swing-system init-db
uv run uvicorn swing_trading_system.web.app:app --reload --port 8401
```

또는 Docker:
```bash
docker compose up --build web
```

- web: `http://${INFRA_HOST}:8401`
- healthz: `http://${INFRA_HOST}:8401/healthz`
- swing api reserve: `http://${INFRA_HOST}:8402`
- metrics/debug reserve: `http://${INFRA_HOST}:8403`

## 주요 CLI
```bash
uv run swing-system init-db
uv run swing-system screen --strategy breakout --save
uv run swing-system screen --strategy pullback --save
uv run swing-system backtest --strategy breakout --start-date 2023-01-01 --end-date 2024-12-31 --save
uv run swing-system monitor --send-alerts
uv run swing-system end-of-day --save --send-alerts
uv run swing-system execute-paper --all-ready --dry-run
```

## 구현 범위
- 공유 `stg.stg_daily_prices`, `stg.stg_security_master` 기반 스크리닝
- 2개 전략: `pullback`, `breakout`
- 일봉 event-driven backtest engine
- FastAPI/Jinja 운영 UI
- Slack/Telegram/Email notifier
- Alpaca paper execution adapter
- dbt 기반 `swing_mart.swing_feature_store` 모델

## 운영 메모
- Quant 인프라는 별도로 실행 중이어야 합니다.
- 기본 infra 대상은 `INFRA_HOST=localhost`이며, 원격/별도 서버를 쓰려면 `INFRA_HOST`만 해당 IP/host로 지정하세요.
- Swing compose는 Postgres/MinIO를 새로 띄우지 않습니다.
- 장애/재실행 절차는 `docs/operations_runbook.md`를 참고하세요.
