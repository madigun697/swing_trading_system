from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from swing_trading_system.backtest.service import BacktestService
from swing_trading_system.execution.service import PaperExecutionService
from swing_trading_system.monitoring.service import MonitoringService
from swing_trading_system.pipeline.orchestrator import SwingOrchestrator
from swing_trading_system.repositories.shared_market import SharedMarketRepository
from swing_trading_system.repositories.swing_repository import SwingRepository
from swing_trading_system.screening.service import ScreeningService
from swing_trading_system.web.routes import build_router

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


@dataclass
class AppServices:
    shared_repository: SharedMarketRepository
    swing_repository: SwingRepository
    orchestrator: SwingOrchestrator
    execution_service: PaperExecutionService


def default_services() -> AppServices:
    shared_repository = SharedMarketRepository()
    swing_repository = SwingRepository()
    screening_service = ScreeningService(shared_repository)
    backtest_service = BacktestService(shared_repository=shared_repository, swing_repository=swing_repository)
    monitoring_service = MonitoringService(shared_repository=shared_repository, swing_repository=swing_repository)
    orchestrator = SwingOrchestrator(
        screening_service=screening_service,
        swing_repository=swing_repository,
        backtest_service=backtest_service,
        monitoring_service=monitoring_service,
    )
    execution_service = PaperExecutionService(swing_repository=swing_repository)
    return AppServices(shared_repository, swing_repository, orchestrator, execution_service)


def create_app(services: AppServices | None = None) -> FastAPI:
    services = services or default_services()
    app = FastAPI(title="Swing Trading System", version="0.1.0")
    templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.state.services = services

    def shared_repo_factory(request: Request) -> SharedMarketRepository:
        return request.app.state.services.shared_repository

    def swing_repo_factory(request: Request) -> SwingRepository:
        return request.app.state.services.swing_repository

    def orchestrator_factory(request: Request) -> SwingOrchestrator:
        return request.app.state.services.orchestrator

    def execution_factory(request: Request) -> PaperExecutionService:
        return request.app.state.services.execution_service

    app.include_router(build_router(templates, shared_repo_factory, swing_repo_factory, orchestrator_factory, execution_factory))
    return app


app = create_app()
