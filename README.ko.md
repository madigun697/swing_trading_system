# 스윙 트레이딩 시스템

공유 Quant Data Platform 인프라 위에서 동작하는 EOD(end-of-day) 스윙 트레이딩 리서치 및 리뷰 시스템입니다.

이 프로젝트는 point-in-time 주식 유니버스를 스크리닝하고, 스윙 트레이딩 시그널을 생성하며, 이벤트 기반 백테스트를 실행하고, Swing 소유 결과를 저장한 뒤 FastAPI 웹 UI에서 시그널과 백테스트 상세를 검토할 수 있게 합니다.

> 리서치와 학습 목적의 프로젝트입니다. 투자 조언이나 실거래 성과를 보장하지 않습니다.

English documentation: [README.md](README.md)

## 주요 기능

- Quant Data Platform이 제공하는 공유 PostgreSQL 및 MinIO 인프라에 연결
- Swing workflow 실행 전 필요한 Quant 공유 relation readiness 점검
- Swing 소유 schema와 table 초기화
- `screening_v2_context` 기반 일일 screening context 생성
- 세 가지 전략 시그널 생성:
  - `pullback`
  - `breakout`
  - `quality_momentum`
- daily, weekly, monthly 선택 기준으로 과거 시그널 백필
- T+1 open entry, stop/target/max-hold exit, target scale-out, trailing stop, SPY benchmark comparison을 포함한 이벤트 기반 백테스트
- dashboard, signal review, backtest run, backtest detail 확인용 브라우저 UI 제공

## 아키텍처

```text
공유 Quant Platform
  PostgreSQL marts + MinIO
        |
        v
Swing repositories 및 readiness checks
        |
        v
Universe selection, feature generation, screeners
        |
        v
Pullback / breakout / quality momentum strategies
        |
        v
Swing-owned schemas, event backtests, FastAPI web UI
```

핵심 구성 요소:

- Python 패키지: `swing_trading_system`
- CLI 엔트리포인트: `swing-system`
- Screening pipeline: `swing_trading_system.screening`
- 전략 구현: `swing_trading_system.strategies`
- Backtest engine: `swing_trading_system.backtest`
- 웹 앱: `swing_trading_system.web.app`

## 요구 사항

- Python 3.13 이상
- `uv`
- 공유 Quant PostgreSQL 및 MinIO 인프라 접근 권한
- Swing readiness check가 통과할 만큼 채워진 Quant mart

예시 환경 파일을 복사하고 로컬 값을 채웁니다.

```bash
cp .env.example .env
```

주요 환경 변수 동작:

- `INFRA_HOST`는 공유 인프라 host를 지정하는 기본 override입니다.
- `POSTGRES_HOST`를 명시하지 않으면 `INFRA_HOST`를 사용합니다.
- `MINIO_ENDPOINT`를 명시하지 않으면 `http://${INFRA_HOST}:9000`을 사용합니다.
- 계좌 규모, slippage, fee, position limit, Swing port 같은 runtime 기본값은 `.env.example`과 `src/swing_trading_system/config.py`에 있습니다.

`.env` 파일이나 실제 credential은 커밋하지 마세요.

## 빠른 시작

의존성을 설치하고 공유 인프라를 검증합니다.

```bash
uv sync
uv run swing-system check-connection
uv run swing-system check-readiness
uv run swing-system init-db
```

웹 UI 실행:

```bash
uv run uvicorn swing_trading_system.web.app:app --host 0.0.0.0 --port 8401
```

웹 UI 백그라운드 실행:

```bash
chmod +x infra/web/serverctl.sh
infra/web/serverctl.sh start
infra/web/serverctl.sh status
infra/web/serverctl.sh logs
infra/web/serverctl.sh stop
```

헬퍼 스크립트는 PID와 로그를 `.run/` 아래에 저장합니다.

Health check:

```bash
curl http://localhost:8401/healthz
```

## 주요 CLI 명령

```bash
uv run swing-system --help
uv run swing-system check-connection
uv run swing-system check-readiness
uv run swing-system init-db
uv run swing-system backfill-bootstrap
uv run swing-system run-daily --max-universe 10 --dry-run
uv run swing-system run-daily --max-universe 10
uv run swing-system backfill-signals --start-date 2025-01-01 --end-date 2026-05-01 --frequency weekly --max-universe 10
uv run swing-system run-backtest --start-date 2025-01-02 --end-date 2026-05-01 --dry-run
uv run swing-system run-backtest --start-date 2025-01-02 --end-date 2026-05-01
```

## 스크리닝과 전략

`run-daily`는 point-in-time EOD 데이터를 읽고 Swing 소유 schema에 feature와 signal을 기록합니다.

`screening_v2_context` 포함 정보:

- 가격 및 변동성 feature
- sector, industry, market cap context
- SPY 20일 수익률 및 MA50/MA200 market-regime context
- point-in-time fundamentals
- 최근 SEC filing metadata

Screener는 유동성과 우호적인 setup에 초점을 둡니다.

- `relative_strength_60d >= 0`
- `return_60d >= 0`
- `atr_pct <= 0.08`
- SPY가 MA200 아래에 있으면 신규 signal 생성 차단

전략 메모:

- `pullback`: quality와 relative strength가 강한 종목에 더 큰 target multiple 적용
- `breakout`: 약한 volume breakout은 더 강하게 필터링하고 quality/relative strength가 강한 종목을 우대
- `quality_momentum`: quality와 momentum 확인을 활용하는 continuation setup

Market-regime sizing:

- SPY MA50/MA200 추세와 FRED `VIXCLS`를 결합해 R1-R5 시장 국면을 산출
- 기본 aggressive profile은 R1/R2에서 공격 노출, R3에서 축소 운용, R4/R5에서 신규 진입 중단
- VIX 데이터는 Quant repo에서 `uv run python -m quant_data_platform.cli sync-fred --series VIXCLS`로 적재

## 백테스트 모델

`run-backtest`는 `swing_meta.signal`에 저장된 signal을 읽고 이벤트 기반 engine을 실행한 뒤 아래 테이블에 저장합니다.

- `swing_mart.backtest_trade_log`
- `swing_mart.backtest_equity_curve`
- `swing_mart.backtest_run_summary`

백테스트 지원 기능:

- T+1 open entry
- Stop, target, max-hold exit
- Target scale-out
- Trailing moving-average stop
- Position count 및 gross exposure limit
- Fee 및 slippage assumption
- SPY benchmark comparison

## 웹 UI

Routes:

- `/`: dashboard
- `/signals`: 최근 signal
- `/backtests`: 최근 backtest run
- `/backtests/run`: 브라우저에서 backtest 실행 및 저장, `breakout+pullback` 같은 combined strategy 선택 지원
- `/backtests/{run_id}`: strategy vs SPY chart, contribution view, slice metrics, trade log, daily equity table을 포함한 detail page

사용자 workflow와 화면 안내: [docs/user_manual.md](docs/user_manual.md)

## 데이터 소유권

Swing은 아래 schema에만 씁니다.

- `swing_meta.*`
- `swing_mart.*`
- `swing_raw.*`

Swing은 Quant 소유 schema에 쓰면 안 됩니다.

- `raw.*`
- `stg.*`
- `meta.*`
- `mart.*`

공유 경계는 [docs/architecture_contract.md](docs/architecture_contract.md), [docs/shared_data_contract.md](docs/shared_data_contract.md), [docs/infra_runtime_contract.md](docs/infra_runtime_contract.md)를 참고하세요.

## 테스트

테스트 실행:

```bash
uv run pytest
```

Lint 실행:

```bash
uv run ruff check
```

## 관련 문서

- [User Manual](docs/user_manual.md)
- [Architecture Contract](docs/architecture_contract.md)
- [Shared Data Contract](docs/shared_data_contract.md)
- [Infrastructure Runtime Contract](docs/infra_runtime_contract.md)
- [Swing Trading System Plan](docs/swing_trading_system_plan.md)
- [Market Regime Switching Strategy Plan](docs/market_regime_switching_strategy_plan.md)

## 공개 저장소 주의 사항

- `.env`, 로컬 데이터 볼륨, 캐시, 생성된 결과 폴더는 ignore 대상입니다.
- API key, broker credential, 개인 계정 식별자, 로컬 DB dump는 커밋하지 마세요.
- 백테스트 결과는 리서치 근거일 뿐 미래 성과를 보장하지 않습니다.
