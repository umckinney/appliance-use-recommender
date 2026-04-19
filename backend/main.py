"""FlowShift — FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import create_tables
from backend.routers import account, appliances, forecast, onboard, recommend, status


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(onboard.router)
app.include_router(account.router)
app.include_router(recommend.router)
app.include_router(status.router)
app.include_router(forecast.router)
app.include_router(appliances.router)


@app.get("/", tags=["health"])
async def root():
    return {"service": "FlowShift", "status": "ok"}


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
