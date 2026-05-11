"""FastAPI application for Swing runtime health."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from swing_trading_system import __version__
from swing_trading_system.repositories.shared_market import SharedMarketRepository


def create_app(repository: SharedMarketRepository | None = None) -> FastAPI:
    app = FastAPI(title="Swing Trading System", version=__version__)
    app.state.shared_market_repository = repository or SharedMarketRepository()

    @app.get("/healthz")
    async def healthz() -> JSONResponse:
        readiness = app.state.shared_market_repository.check_readiness()
        payload = {
            "status": "ok" if readiness.ok else "unavailable",
            **readiness.to_dict(),
        }
        return JSONResponse(payload, status_code=200 if readiness.ok else 503)

    return app


app = create_app()
