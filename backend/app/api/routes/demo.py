"""
Demo API routes.

Exposes live-updating demo data so judges and users without
a Solana wallet can see PythGuard in full action immediately.
No token, no wallet, no setup required.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.core.demo_data import (
    build_demo_confidence_history,
    build_demo_feed_statuses,
    build_demo_risk_summary,
    DEMO_WALLET_ADDRESS,
)

demo_router = APIRouter(prefix="/demo", tags=["Demo"])


@demo_router.get(
    "/risk",
    summary="Live demo risk summary (no wallet needed)",
    description=(
        "Returns a continuously updating demo risk summary with "
        "3 realistic positions across SOL, ETH, and JitoSOL. "
        "Values oscillate in real time to demonstrate the dashboard. "
        "Powered by simulated Pyth-style confidence intervals."
    ),
)
async def get_demo_risk_summary() -> dict:
    return build_demo_risk_summary()


@demo_router.get(
    "/feeds",
    summary="Live demo feed statuses",
)
async def get_demo_feed_statuses() -> list:
    return build_demo_feed_statuses()


@demo_router.get(
    "/confidence/{asset_ticker}",
    summary="Demo confidence ratio history for chart",
)
async def get_demo_confidence_history(asset_ticker: str) -> dict:
    history = build_demo_confidence_history(asset_ticker)
    return {
        "asset": asset_ticker.upper(),
        "wallet": DEMO_WALLET_ADDRESS,
        "history": history,
        "is_demo": True,
    }
