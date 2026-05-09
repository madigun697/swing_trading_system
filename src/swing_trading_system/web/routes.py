from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from swing_trading_system.pipeline.orchestrator import SwingOrchestrator
from swing_trading_system.repositories.shared_market import SharedMarketRepository
from swing_trading_system.repositories.swing_repository import SwingRepository
from swing_trading_system.execution.service import PaperExecutionService


def build_router(
    templates: Jinja2Templates,
    shared_repo_factory: Callable[[Request], SharedMarketRepository],
    swing_repo_factory: Callable[[Request], SwingRepository],
    orchestrator_factory: Callable[[Request], SwingOrchestrator],
    execution_factory: Callable[[Request], PaperExecutionService],
) -> APIRouter:
    router = APIRouter()

    @router.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/dashboard", status_code=302)

    @router.get("/healthz")
    async def healthz(request: Request) -> JSONResponse:
        readiness = shared_repo_factory(request).check_readiness()
        return JSONResponse(readiness.__dict__, status_code=200 if readiness.ok else 503)

    @router.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(request: Request) -> HTMLResponse:
        shared_repo = shared_repo_factory(request)
        swing_repo = swing_repo_factory(request)
        context = {
            "request": request,
            "readiness": shared_repo.check_readiness(),
            "latest_candidates": swing_repo.list_latest_candidates(limit=10),
            "latest_backtests": swing_repo.list_latest_backtests(limit=5),
            "recent_alerts": swing_repo.list_recent_alerts(limit=10),
            "ready_trade_plans": swing_repo.list_ready_trade_plans(limit=10),
        }
        return templates.TemplateResponse(request, "dashboard.html", context)

    @router.get("/candidates", response_class=HTMLResponse)
    async def candidates_page(request: Request, strategy_id: str = "breakout") -> HTMLResponse:
        context = {
            "request": request,
            "strategy_id": strategy_id,
            "latest_candidates": swing_repo_factory(request).list_latest_candidates(strategy_id=strategy_id, limit=25),
        }
        return templates.TemplateResponse(request, "candidates.html", context)

    @router.post("/candidates/run", response_class=HTMLResponse)
    async def run_candidates(request: Request, strategy_id: str = Form(...), signal_date: str = Form(...)) -> HTMLResponse:
        result = orchestrator_factory(request).run_screen(strategy_id=strategy_id, as_of_date=date.fromisoformat(signal_date), save=True)
        context = {
            "request": request,
            "strategy_id": strategy_id,
            "latest_candidates": swing_repo_factory(request).list_latest_candidates(strategy_id=strategy_id, limit=25),
            "run_result": result,
        }
        return templates.TemplateResponse(request, "candidates.html", context)

    @router.get("/backtest", response_class=HTMLResponse)
    async def backtest_page(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, "backtest.html", {"request": request, "result": None})

    @router.post("/backtest", response_class=HTMLResponse)
    async def run_backtest(
        request: Request,
        strategy_id: str = Form(...),
        start_date: str = Form(...),
        end_date: str = Form(...),
        initial_capital: str = Form("100000"),
        save: bool = Form(False),
    ) -> HTMLResponse:
        result = orchestrator_factory(request).run_backtest(
            strategy_id=strategy_id,
            start_date=date.fromisoformat(start_date),
            end_date=date.fromisoformat(end_date),
            initial_capital=Decimal(initial_capital),
            save=save,
        )
        return templates.TemplateResponse(request, "backtest.html", {"request": request, "result": result})

    @router.get("/trade-plans", response_class=HTMLResponse)
    async def trade_plans_page(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "trade_plans.html",
            {"request": request, "trade_plans": swing_repo_factory(request).list_ready_trade_plans(limit=25), "execution_result": None},
        )

    @router.post("/trade-plans/execute", response_class=HTMLResponse)
    async def execute_trade_plans(request: Request, submit: bool = Form(False)) -> HTMLResponse:
        execution_result = execution_factory(request).execute(submit=submit, limit=25)
        return templates.TemplateResponse(
            request,
            "trade_plans.html",
            {"request": request, "trade_plans": swing_repo_factory(request).list_ready_trade_plans(limit=25), "execution_result": execution_result},
        )

    @router.get("/positions", response_class=HTMLResponse)
    async def positions_page(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "positions.html",
            {"request": request, "positions": swing_repo_factory(request).list_open_positions(), "alerts": swing_repo_factory(request).list_recent_alerts(limit=25)},
        )

    return router
