# Swing Trading System 운영 Runbook

## 일일 운영 순서
1. Quant daily pipeline 완료 확인
2. `uv run swing-system healthcheck`
3. `uv run swing-system end-of-day --save --send-alerts`
4. 후보/알림/포지션 점검
5. 필요 시 `uv run swing-system execute-paper --all-ready --dry-run`
6. 검토 후 `--submit` 실행

## 장애 대응
### DB readiness 실패
- Quant PostgreSQL 포트/접속 정보 확인
- `stg.stg_daily_prices`, `stg.stg_security_master`, `stg.stg_benchmark_series` 존재 확인
- `uv run swing-system init-db` 재실행으로 swing schema 누락 여부 확인

### 후보 생성 실패
- `SWING_MAX_UNIVERSE`, `SWING_MIN_ADV_USD`, `SWING_MIN_PRICE` 설정 확인
- 최신 shared 데이터 날짜와 대상 날짜가 일치하는지 확인
- `uv run swing-system screen --strategy breakout` 수동 재실행

### 알림 실패
- Slack/Telegram/SMTP 자격 증명 확인
- alert 이벤트는 DB와 MinIO에 남으므로 notifier만 재실행 가능
- `uv run swing-system monitor --send-alerts` 재실행

### Paper execution 실패
- `uv run swing-system execute-paper --all-ready --dry-run`으로 payload 확인
- Alpaca 키/권한/market hours 확인
- 실패한 trade plan만 상태 갱신 후 재전송

## 재실행 규칙
- screen run은 날짜+전략 기준으로 재생성 가능
- backtest run은 parameter hash 단위로 재실행 가능
- alert는 이미 발송된 항목을 중복 발송하지 않도록 `status`를 확인
