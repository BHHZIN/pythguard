"""
PythGuard Backend — FastAPI entry point.

Mounts all routers, configures CORS, and exposes the health check.
Start with: uvicorn app.main:application --reload --port 8000
"""
from __future__ import annotations

import time

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.demo import demo_router
from app.api.routes.feeds import feeds_router
from app.api.routes.risk import risk_router
from app.config import settings

logger = structlog.get_logger(__name__)

# ─────────────────────────────────────────────────────────────
# Application factory
# ─────────────────────────────────────────────────────────────

application = FastAPI(
    title="PythGuard API",
    description=(
        "DeFi risk monitoring for Solana lending/borrowing positions. "
        "Powered by Pyth Price Feeds and Pyth Pro confidence intervals."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─────────────────────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────────────────────

application.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────

application.include_router(demo_router,  prefix="/api/v1")
application.include_router(risk_router,  prefix="/api/v1")
application.include_router(feeds_router, prefix="/api/v1")

# ─────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────

@application.get("/health", tags=["System"])
async def handle_health_check() -> dict:
    """
    Returns 200 OK when the backend is running.
    Used by Docker Compose and monitoring tools.
    """
    return {
        "status": "ok",
        "service": "pythguard-backend",
        "timestamp": int(time.time()),
    }


@application.get("/", tags=["System"])
async def handle_root() -> dict:
    return {
        "name": "PythGuard API",
        "version": "1.0.0",
        "docs": "/docs",
    }
