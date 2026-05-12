"""FastAPI application for Swing runtime health and v1 UI."""

from __future__ import annotations

from html import escape
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from swing_trading_system import __version__
from swing_trading_system.backtest.repository import BacktestRepository
from swing_trading_system.repositories.shared_market import SharedMarketRepository


def create_app(
    repository: SharedMarketRepository | None = None,
    backtest_repository: BacktestRepository | None = None,
) -> FastAPI:
    app = FastAPI(title="Swing Trading System", version=__version__)
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

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        readiness = app.state.shared_market_repository.check_readiness()
        repo = app.state.backtest_repository
        try:
            signal_count = repo.count_signals()
            recent_runs = repo.list_recent_runs(limit=5)
            latest_trade_date = app.state.shared_market_repository.fetch_latest_trade_date()
            body = _page(
                "Swing Trading System",
                f"""
                <h1>Swing Trading System</h1>
                <p>Readiness: <strong>{escape(readiness.code)}</strong></p>
                <p>Latest shared trade date: {escape(str(latest_trade_date))}</p>
                <p>Signal count: {signal_count}</p>
                <nav><a href='/signals'>Signals</a> | <a href='/backtests'>Backtests</a></nav>
                <h2>Recent Backtest Runs</h2>
                {_runs_table(recent_runs)}
                """,
            )
        except Exception as exc:  # pragma: no cover - defensive UI fallback.
            body = _page("Swing Trading System", f"<h1>Swing Trading System</h1><p>Error: {escape(str(exc))}</p>")
        return HTMLResponse(body)

    @app.get("/signals", response_class=HTMLResponse)
    async def signals() -> HTMLResponse:
        rows = app.state.backtest_repository.fetch_signals(limit=100)
        html_rows = "".join(
            "<tr>"
            f"<td>{signal.id}</td><td>{escape(signal.symbol)}</td><td>{escape(signal.strategy)}</td>"
            f"<td>{signal.signal_date}</td><td>{signal.entry_price:.2f}</td><td>{signal.stop_price:.2f}</td><td>{signal.target_price:.2f}</td>"
            "</tr>"
            for signal in rows
        )
        return HTMLResponse(
            _page(
                "Signals",
                """
                <h1>Signals</h1>
                <table><thead><tr><th>ID</th><th>Symbol</th><th>Strategy</th><th>Date</th><th>Entry</th><th>Stop</th><th>Target</th></tr></thead>
                <tbody>{rows}</tbody></table>
                <p><a href='/'>Home</a></p>
                """.format(rows=html_rows),
            )
        )

    @app.get("/backtests", response_class=HTMLResponse)
    async def backtests() -> HTMLResponse:
        runs = app.state.backtest_repository.list_recent_runs(limit=20)
        return HTMLResponse(_page("Backtests", f"<h1>Backtests</h1>{_runs_table(runs)}<p><a href='/'>Home</a></p>"))

    @app.get("/backtests/{run_id}", response_class=HTMLResponse)
    async def backtest_detail(run_id: str) -> HTMLResponse:
        trades = app.state.backtest_repository.fetch_run_trades(run_id)
        equity = app.state.backtest_repository.fetch_run_equity_curve(run_id)
        return HTMLResponse(
            _page(
                f"Backtest {escape(run_id)}",
                f"<h1>Backtest {escape(run_id)}</h1><h2>Trades</h2>{_dict_table(trades)}<h2>Equity Curve</h2>{_dict_table(equity)}<p><a href='/backtests'>Backtests</a></p>",
            )
        )

    return app


def _page(title: str, body: str) -> str:
    return f"""
    <!doctype html>
    <html><head><title>{escape(title)}</title>
    <style>body{{font-family:system-ui,sans-serif;margin:2rem}}table{{border-collapse:collapse}}td,th{{border:1px solid #ddd;padding:.35rem .5rem}}</style>
    </head><body>{body}</body></html>
    """


def _runs_table(runs: list[dict[str, Any]]) -> str:
    if not runs:
        return "<p>No backtest runs.</p>"
    rows = "".join(
        "<tr>"
        f"<td><a href='/backtests/{escape(str(row['run_id']))}'>{escape(str(row['run_id']))}</a></td>"
        f"<td>{row.get('trade_count', 0)}</td><td>{escape(str(row.get('total_pnl')))}</td>"
        f"<td>{escape(str(row.get('start_date')))}</td><td>{escape(str(row.get('end_date')))}</td>"
        "</tr>"
        for row in runs
    )
    return "<table><thead><tr><th>Run ID</th><th>Trades</th><th>Total PnL</th><th>Start</th><th>End</th></tr></thead><tbody>" + rows + "</tbody></table>"


def _dict_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p>No rows.</p>"
    keys = list(rows[0].keys())
    header = "".join(f"<th>{escape(str(key))}</th>" for key in keys)
    body = "".join("<tr>" + "".join(f"<td>{escape(str(row.get(key)))}</td>" for key in keys) + "</tr>" for row in rows)
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


app = create_app()
