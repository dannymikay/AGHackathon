"""
AgriMatch FastAPI application factory.

Startup sequence:
1. APScheduler (logistics timeout + GPS heartbeat monitors)
2. Demo data seed (if DB is empty)

All routers are mounted with /api/v1 prefix.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, bids, buyers, farmers, logistics, middlemen, orders, verify, webhooks, ws
from app.seed.demo_data import seed_if_empty
from app.tasks.timeout_monitor import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- Startup ----
    logger.info("Starting AgriMatch API...")
    start_scheduler()
    await seed_if_empty()
    logger.info("AgriMatch API ready.")
    yield
    # ---- Shutdown ----
    stop_scheduler()
    logger.info("AgriMatch API stopped.")


app = FastAPI(
    title="AgriMatch API",
    description=(
        "Three-sided agricultural marketplace (Farmer / Middleman / Buyer) "
        "with AI crop grading, PostGIS logistics matching, and Stripe escrow."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Register routers ----
_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=_PREFIX)
app.include_router(farmers.router, prefix=_PREFIX)
app.include_router(buyers.router, prefix=_PREFIX)
app.include_router(middlemen.router, prefix=_PREFIX)
app.include_router(orders.router, prefix=_PREFIX)
app.include_router(bids.router, prefix=_PREFIX)
app.include_router(logistics.router, prefix=_PREFIX)
app.include_router(verify.router, prefix=_PREFIX)
app.include_router(webhooks.router, prefix=_PREFIX)
app.include_router(ws.router)  # No /api/v1 prefix — WebSocket paths are top-level


@app.get("/health", tags=["admin"])
async def health_check():
    return {"status": "ok", "service": "agrimatch"}


@app.get("/", tags=["admin"])
async def root():
    return {
        "service": "AgriMatch API",
        "docs": "/docs",
        "version": "0.1.0",
    }
