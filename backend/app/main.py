from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import scheduler
from .config import get_settings
from .routers import series, summary
from .service import MacroService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    log = logging.getLogger("startup")

    svc = MacroService(settings)
    app.state.service = svc

    # Warm the cache on boot so the first request is not a cold 30-series fetch.
    # Failures here are non-fatal: the dashboard degrades to whatever is cached.
    try:
        errors = await svc.refresh()
        if errors:
            log.warning("Startup refresh completed with %d errors", len(errors))
    except Exception:  # noqa: BLE001
        log.exception("Startup refresh failed; serving from cache if available")

    tasks = scheduler.start(svc)
    try:
        yield
    finally:
        await scheduler.stop(tasks)
        await svc.aclose()


settings = get_settings()

app = FastAPI(
    title="US Macro Health Dashboard",
    version="1.0.0",
    description=(
        "Aggregates ~48 FRED series into business-cycle phase classification, "
        "a composite systemic-risk index, and a threshold alert engine."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(summary.router, prefix="/api")
app.include_router(series.router, prefix="/api")


@app.get("/")
async def root() -> dict:
    return {
        "service": "US Macro Health Dashboard",
        "docs": "/docs",
        "endpoints": [
            "/api/summary", "/api/cycle", "/api/risk", "/api/alerts",
            "/api/series", "/api/series/{series_id}",
            "/api/health", "/api/refresh",
        ],
    }
