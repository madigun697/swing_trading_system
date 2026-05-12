# Sprint 3 Review — Backtest & Web UI v1

작성일: 2026-05-12

## 결과 요약

Sprint 3 목표였던 signal 기반 일봉 event-driven 백테스트, result persistence, Web UI v1 route 구현을 완료했다.

## 완료 항목

- `backtest/models.py`: backtest config/signal/price/trade/equity/result model 구현
- `backtest/engine.py`: t+1 open entry, stop/target/max-hold exit engine 구현
- `backtest/metrics.py`: total return, MDD, win rate, profit factor, expectancy 등 구현
- `backtest/repository.py`: signal/price 조회 및 trade/equity 저장 구현
- `swing-system run-backtest`: dry-run/write CLI 추가
- Web UI v1 route 추가:
  - `/`
  - `/signals`
  - `/backtests`
  - `/backtests/{run_id}`
- look-ahead/backtest safety tests 추가

## Backtest Safety 확인

- signal day bar는 entry에 사용하지 않음
- entry는 `signal_date` 이후 첫 번째 trading day open 사용
- entry bar same-bar exit 금지
- stop/target 동시 터치 시 stop 우선 처리
- missing next bar / insufficient future bars reject 처리
- Quant-owned schema write 없음

## 실제 실행 결과

| 검증 | 결과 |
|---|---|
| `uv run pytest` | Pass, 42 tests |
| `uv run swing-system run-backtest --dry-run` | Pass |
| `uv run swing-system run-daily --as-of 2026-05-01 --max-universe 10` | Pass, signal 2 |
| `uv run swing-system run-backtest --start-date 2026-05-01 --end-date 2026-05-01` | Pass, trades 2 / equity points 2 |
| Web UI TestClient `/`, `/signals`, `/backtests` | Pass, HTTP 200 |

## 저장 결과

- `swing_mart.backtest_trade_log`: 2 rows 저장 확인
- `swing_mart.backtest_equity_curve`: 2 rows 저장 확인
- latest run total PnL: positive

## Sprint 4 진입 판정

- 개발 준비: **Approved**
- 데이터 준비: **Approved**
- QA 기준: **Approved**

## Sprint 4 권장 시작점

1. `swing_meta.signal`과 backtest 결과를 기반으로 trade plan 후보 생성
2. position snapshot 구조와 현재 보유 포지션 loader 구현
3. stop/target monitoring job 구현
4. alert dry-run 및 notifier adapter 구현
5. Alpaca paper execution 전 risk validation gate 구현
