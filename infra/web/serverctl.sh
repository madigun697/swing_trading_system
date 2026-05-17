#!/bin/sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
RUNTIME_DIR="$REPO_ROOT/.run"
PID_FILE="$RUNTIME_DIR/swing-web.pid"
LOG_FILE="$RUNTIME_DIR/swing-web.log"
HOST="${SWING_WEB_HOST:-0.0.0.0}"
PORT="${SWING_WEB_PORT:-8401}"
UVICORN_BIN="$REPO_ROOT/.venv/bin/uvicorn"

mkdir -p "$RUNTIME_DIR"

is_running() {
  if [ ! -f "$PID_FILE" ]; then
    return 1
  fi

  PID=$(cat "$PID_FILE")
  if [ -z "$PID" ]; then
    return 1
  fi

  if kill -0 "$PID" 2>/dev/null; then
    return 0
  fi

  rm -f "$PID_FILE"
  return 1
}

start_server() {
  if is_running; then
    echo "swing-web already running (pid $(cat "$PID_FILE"))"
    return 0
  fi

  cd "$REPO_ROOT"
  if [ -x "$UVICORN_BIN" ]; then
    nohup "$UVICORN_BIN" swing_trading_system.web.app:app --host "$HOST" --port "$PORT" >>"$LOG_FILE" 2>&1 &
  else
    nohup uv run uvicorn swing_trading_system.web.app:app --host "$HOST" --port "$PORT" >>"$LOG_FILE" 2>&1 &
  fi
  PID=$!
  echo "$PID" >"$PID_FILE"
  sleep 1

  if ! kill -0 "$PID" 2>/dev/null; then
    rm -f "$PID_FILE"
    echo "swing-web failed to start; inspect $LOG_FILE"
    exit 1
  fi

  echo "swing-web started (pid $PID, log $LOG_FILE)"
}

stop_server() {
  if ! is_running; then
    echo "swing-web is not running"
    return 0
  fi

  PID=$(cat "$PID_FILE")
  kill "$PID"

  i=0
  while kill -0 "$PID" 2>/dev/null; do
    i=$((i + 1))
    if [ "$i" -ge 20 ]; then
      echo "swing-web did not stop gracefully (pid $PID)"
      exit 1
    fi
    sleep 0.5
  done

  rm -f "$PID_FILE"
  echo "swing-web stopped"
}

show_status() {
  if is_running; then
    echo "swing-web running (pid $(cat "$PID_FILE"), port $PORT)"
  else
    echo "swing-web stopped"
  fi
}

show_logs() {
  touch "$LOG_FILE"
  tail -f "$LOG_FILE"
}

case "${1:-}" in
  start)
    start_server
    ;;
  stop)
    stop_server
    ;;
  restart)
    stop_server
    start_server
    ;;
  status)
    show_status
    ;;
  logs)
    show_logs
    ;;
  *)
    echo "usage: $0 {start|stop|restart|status|logs}"
    exit 1
    ;;
esac
