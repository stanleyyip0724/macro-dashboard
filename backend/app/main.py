from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import scheduler
from .config import get_settings
from .markets import MarketsService
from .routers import markets, series, summary
from .service import MacroService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    # httpx logs every request line at INFO, including the full query string --
    # and FRED takes its API key as a query parameter, so at INFO level the key
    # lands in the application log on every single call. Our own logging runs
    # URLs through _safe_url(); the library's does not, so silence it.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    log = logging.getLogger("startup")

    svc = MacroService(settings)
    app.state.service = svc
    # Markets data is fetched lazily on first request: its upstreams are public
    # endpoints with no SLA, and blocking boot on them would make a Yahoo
    # outage look like a failed deploy.
    app.state.markets = MarketsService(settings)

    # Warm the cache on boot so the first request is not a cold 48-series fetch.
    #
    # Deliberately NOT awaited: on a container platform the startup probe waits
    # for the port to accept connections, and awaiting ~48 FRED calls here can
    # push that past the deadline -- which reads as a failed deploy even though
    # the app is healthy. Warming in the background means the server listens
    # immediately and early requests serve from the SQLite cache.
    async def _warm() -> None:
        try:
            errors = await svc.refresh()
            if errors:
                log.warning("Startup refresh completed with %d errors", len(errors))
            else:
                log.info("Startup refresh complete")
        except Exception:  # noqa: BLE001
            log.exception("Startup refresh failed; serving from cache if available")

    warm = asyncio.create_task(_warm(), name="startup-warm")

    tasks = scheduler.start(svc)
    try:
        yield
    finally:
        warm.cancel()
        await asyncio.gather(warm, return_exceptions=True)
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
app.include_router(markets.router, prefix="/api")


@app.get("/")
async def root() -> dict:
    return {
        "service": "US Macro Health Dashboard",
        "docs": "/docs",
        "endpoints": [
            "/api/summary", "/api/cycle", "/api/risk", "/api/alerts",
            "/api/series", "/api/series/{series_id}",
            "/api/markets", "/api/markets/curve", "/api/markets/fear-greed",
            "/api/markets/news",
            "/api/health", "/api/refresh",
        ],
    }
