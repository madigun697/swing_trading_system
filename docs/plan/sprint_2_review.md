# Sprint 2 Review — Screening & Strategy Engine

작성일: 2026-05-11

## 결과 요약

Sprint 2 목표였던 EOD 기반 screening feature 계산, Screener v1, Pullback/Breakout strategy v1, CLI daily run, feature/signal 저장을 완료했다.

## 완료 항목

- `screening/features.py`: Sprint 2 feature contract 및 계산 구현
- `screening/indicators.py`: SMA, rolling return, ATR, relative strength 등 구현
- `screening/universe.py`: 기준일 universe 선택 구현
- `screening/screener.py`: 유동성/추세/상대강도/ATR/거래량 기반 candidate scoring 구현
- `strategies/base.py`: 공통 `StrategySignal`, `StrategyContext` 구현
- `strategies/pullback.py`: Pullback v1 구현
- `strategies/breakout.py`: Breakout v1 구현
- `ScreeningPipeline.run_daily()`: feature → screener → strategies → persistence 통합
- `swing-system run-daily`: dry-run/write 실행 command 추가

## 실제 실행 결과

| 검증 | 결과 |
|---|---|
| `uv run pytest` | Pass, 31 tests |
| `uv run swing-system run-daily --max-universe 10 --dry-run` | Pass, feature 10 / candidate 5 / signal 1 |
| `uv run swing-system run-daily --max-universe 10` | Pass, screening_run_id 2 / feature 10 / signal 1 |
| DB 검증 | `swing_mart.swing_feature_store` `screening_v1` rows 10, `swing_meta.signal` rows 1 |

## 저장된 실제 signal 예시

- symbol: `AVGO`
- strategy: `pullback`
- signal_date: latest shared trade date
- entry/stop/target/risk fields: populated

## QA / 안전성 확인

- `ScreeningInputLoader`와 `calculate_features()`가 `trade_date <= as_of_date`만 사용
- feature rows는 `swing_mart.swing_feature_store`에 저장
- signals는 `swing_meta.signal`에 저장
- Quant-owned `raw.*`, `stg.*`, `meta.*`, `mart.*` write 없음
- 실제 host IP 문서 노출 없음

## Sprint 3 진입 판정

- 개발 준비: **Approved**
- 데이터 준비: **Approved**
- QA 기준: **Approved**

## Sprint 3 권장 시작점

1. `swing_meta.signal`을 backtest input으로 읽는 repository/query 추가
2. `entry_price`, `stop_price`, `target_price`, `risk_per_share`, `position_size` 기반 trade simulation 구현
3. t일 signal → t+1 open execution invariant를 테스트로 고정
4. equity curve와 trade log를 `swing_mart.backtest_*`에 저장
