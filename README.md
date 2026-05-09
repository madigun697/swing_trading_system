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
- `55432` PostgreSQL
- `9000` MinIO API
- `9001` MinIO Console
- `5050` pgAdmin
- `8080` Airflow
- `8000` Quant web

Swing 기본 포트:
- `8401` Swing web
- `8402` Swing API reserve
- `8403` metrics/debug reserve

## 빠른 시작
```bash
cp .env.example .env
uv sync
uv run swing-system init-db
uv run uvicorn swing_trading_system.web.app:app --reload --port 8401
```

또는 Docker:
```bash
docker compose up --build web
```

- web: <http://localhost:8401>
- healthz: <http://localhost:8401/healthz>

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
- Swing compose는 Postgres/MinIO를 새로 띄우지 않습니다.
- 장애/재실행 절차는 `docs/operations_runbook.md`를 참고하세요.
