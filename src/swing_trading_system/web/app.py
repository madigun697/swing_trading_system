"""FastAPI application for Swing runtime health and v1 UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from swing_trading_system import __version__
from swing_trading_system.backtest.repository import BacktestRepository
from swing_trading_system.repositories.shared_market import SharedMarketRepository

WEB_DIR = Path(__file__).parent
TEMPLATE_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


def create_app(
    repository: SharedMarketRepository | None = None,
    backtest_repository: BacktestRepository | None = None,
) -> FastAPI:
    app = FastAPI(title="Swing Trading System", version=__version__)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.state.shared_market_repository = repository or SharedMarketRepository()
    app.state.backtest_repository = backtest_repository or BacktestRepository()

    @app.get("/healthz")
    async def healthz() -> JSONResponse:
        readiness = app.state.shared_market_repository.check_readiness()
        payload = {
            "status": "ok" if readiness.ok else "unavailable",
            **readiness.to_dict(),
        }
        return JSONResponse(payload, status_code=200 if readiness.ok else 503)

    @app.get("/")
    async def index(request: Request):
        readiness = app.state.shared_market_repository.check_readiness()
        latest_trade_date = None
        signal_count = 0
        recent_runs = []
        ui_warnings: list[str] = []
        try:
            latest_trade_date = app.state.shared_market_repository.fetch_latest_trade_date()
        except Exception as exc:  # pragma: no cover - defensive dashboard fallback.
            ui_warnings.append(f"latest trade date unavailable: {type(exc).__name__}")
        try:
            backtest_repo = app.state.backtest_repository
            signal_count = backtest_repo.count_signals()
            recent_runs = backtest_repo.list_recent_runs(limit=5)
        except Exception as exc:
            ui_warnings.append(f"backtest summary unavailable: {type(exc).__name__}")
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "active_page": "dashboard",
                "readiness": readiness,
                "latest_trade_date": latest_trade_date,
                "signal_count": signal_count,
                "recent_runs": recent_runs,
                "ui_warnings": ui_warnings,
            },
        )

    @app.get("/signals")
    async def signals(request: Request):
        rows = []
        ui_warnings: list[str] = []
        try:
            rows = app.state.backtest_repository.fetch_signals(limit=100)
        except Exception as exc:
            ui_warnings.append(f"signals unavailable: {type(exc).__name__}")
        return templates.TemplateResponse(
            request,
            "signals.html",
            {
                "active_page": "signals",
                "signals": rows,
                "ui_warnings": ui_warnings,
            },
        )

    @app.get("/backtests")
    async def backtests(request: Request):
        recent_runs = []
        ui_warnings: list[str] = []
        try:
            recent_runs = app.state.backtest_repository.list_recent_runs(limit=20)
        except Exception as exc:
            ui_warnings.append(f"backtest runs unavailable: {type(exc).__name__}")
        return templates.TemplateResponse(
            request,
            "backtests.html",
            {
                "active_page": "backtests",
                "recent_runs": recent_runs,
                "ui_warnings": ui_warnings,
            },
        )

    @app.get("/backtests/{run_id}")
    async def backtest_detail(request: Request, run_id: str):
        trades = []
        equity_curve = []
        summary: dict[str, object] = {}
        ui_warnings: list[str] = []
        try:
            trades = app.state.backtest_repository.fetch_run_trades(run_id)
            equity_curve = app.state.backtest_repository.fetch_run_equity_curve(run_id)
            summary = app.state.backtest_repository.fetch_run_summary(run_id)
        except Exception as exc:
            ui_warnings.append(f"backtest detail unavailable: {type(exc).__name__}")
        total_pnl = _safe_float(summary.get("total_pnl")) if summary else sum(_safe_float(row.get("pnl")) for row in trades)
        report_summary = _build_report_summary(run_id, trades, equity_curve, summary)
        return templates.TemplateResponse(
            request,
            "backtest_detail.html",
            {
                "active_page": "backtests",
                "run_id": run_id,
                "trades": trades,
                "equity_curve": equity_curve,
                "total_pnl": round(total_pnl, 6),
                "summary": summary,
                "report_summary": report_summary,
                "ui_warnings": ui_warnings,
            },
        )

    return app


def _build_report_summary(
    run_id: str,
    trades: list[dict[str, object]],
    equity_curve: list[dict[str, object]],
    summary: dict[str, object],
) -> dict[str, object]:
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    config = summary.get("config") if isinstance(summary.get("config"), dict) else {}
    duplicate_counts: dict[tuple[object, ...], int] = {}
    exit_reasons: dict[str, int] = {}
    for trade in trades:
        details = trade.get("details") if isinstance(trade.get("details"), dict) else {}
        signal = details.get("signal") if isinstance(details.get("signal"), dict) else {}
        key = (
            trade.get("symbol"),
            signal.get("strategy") or details.get("strategy"),
            signal.get("signal_date"),
            signal.get("entry_price"),
            signal.get("stop_price"),
            signal.get("target_price"),
        )
        duplicate_counts[key] = duplicate_counts.get(key, 0) + 1
        reason = str(details.get("exit_reason") or "unknown")
        exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
    duplicates = [{"key": str(key), "count": count} for key, count in duplicate_counts.items() if count > 1]
    return {
        "run_id": run_id,
        "trade_count": summary.get("trade_count", len(trades)),
        "start_date": summary.get("start_date"),
        "end_date": summary.get("end_date"),
        "initial_equity": summary.get("initial_equity") or config.get("initial_equity"),
        "final_equity": summary.get("final_equity") or (equity_curve[-1].get("equity") if equity_curve else None),
        "total_pnl": summary.get("total_pnl") or metrics.get("total_pnl"),
        "total_return": summary.get("total_return") or metrics.get("total_return"),
        "max_drawdown": summary.get("max_drawdown") or metrics.get("max_drawdown"),
        "win_rate": summary.get("win_rate") or metrics.get("win_rate"),
        "profit_factor": summary.get("profit_factor") or metrics.get("profit_factor"),
        "rejection_count": summary.get("rejection_count") or metrics.get("rejection_count", 0),
        "symbol_contribution": metrics.get("symbol_contribution", {}),
        "strategy_contribution": metrics.get("strategy_contribution", {}),
        "exit_reasons": exit_reasons,
        "duplicates": duplicates,
        "config": config,
    }


def _safe_float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


app = create_app()
