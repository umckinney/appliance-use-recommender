"""FlowShift — FastAPI application entry point."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.config import settings
from backend.database import create_tables
from backend.limiter import limiter
from backend.routers import (
    account,
    appliances,
    auth,
    data_sources,
    forecast,
    onboard,
    recommend,
    shortcuts,
    status,
    utilities,
)

_log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await create_tables()
    except Exception as exc:
        _log.error("DB startup error (will retry on first request): %s", exc)

    if not os.environ.get("EIA_API_KEY"):
        _log.warning(
            "EIA_API_KEY not set — carbon intensity data will be unavailable. "
            "Get a free key at https://api.eia.gov/"
        )
    yield


app = FastAPI(
    title="FlowShift",
    description=(
        "Recommends the best time to run high-energy appliances "
        "based on real-time grid carbon intensity, utility pricing, "
        "and personal solar generation."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(onboard.router)
app.include_router(account.router)
app.include_router(recommend.router)
app.include_router(shortcuts.router)
app.include_router(status.router)
app.include_router(forecast.router)
app.include_router(appliances.router)
app.include_router(utilities.router)
app.include_router(data_sources.router)
app.include_router(auth.router)


@app.get("/", tags=["health"])
async def root():
    return {"service": "FlowShift", "status": "ok"}


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
