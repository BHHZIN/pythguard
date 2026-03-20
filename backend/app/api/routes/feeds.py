"""
Feeds API routes.

Endpoints for fetching Pyth price feed status and chart data.
"""
from __future__ import annotations

import time
from typing import Optional

import structlog
from fastapi import APIRouter, Query

from app.api.schemas import (
    CandlestickDataResponse,
    CandlestickResponse,
    PriceFeedStatusResponse,
    RiskLevelSchema,
)
from app.config import settings
from app.pyth.mcp_client import PythMCPClient

logger = structlog.get_logger(__name__)

feeds_router = APIRouter(prefix="/feeds", tags=["Price Feeds"])

_pyth_mcp_client = PythMCPClient()

# All supported symbols with their Pyth Pro full names
SUPPORTED_CRYPTO_SYMBOLS: dict[str, str] = {
    "SOL":     "Crypto.SOL/USD",
    "BTC":     "Crypto.BTC/USD",
    "ETH":     "Crypto.ETH/USD",
    "USDC":    "Crypto.USDC/USD",
    "JITOSOL": "Crypto.JITOSOL/USD",
}

MAXIMUM_ACCEPTABLE_FEED_AGE_SECONDS = 60


# ─────────────────────────────────────────────────────────────
# GET /feeds/status
# ─────────────────────────────────────────────────────────────

@feeds_router.get(
    "/status",
    response_model=list[PriceFeedStatusResponse],
    summary="Get current status of all supported Pyth price feeds",
)
async def get_all_feed_statuses() -> list[PriceFeedStatusResponse]:
    """
    Returns current price and confidence ratio for all
    supported assets. Used by the dashboard's feed status panel.
    """
    latest_prices = _pyth_mcp_client.get_latest_prices(
        symbols=list(SUPPORTED_CRYPTO_SYMBOLS.values()),
    )

    current_timestamp = int(time.time())

    return [
        PriceFeedStatusResponse(
            asset_symbol=price_data.symbol,
            normalized_price=price_data.price,
            confidence_ratio=price_data.confidence_ratio,
            risk_level_from_confidence=_classify_confidence_risk(
                price_data.confidence_ratio
            ),
            publish_timestamp=price_data.publish_time,
            is_feed_fresh=(
                current_timestamp - price_data.publish_time
                < MAXIMUM_ACCEPTABLE_FEED_AGE_SECONDS
            ),
        )
        for price_data in latest_prices
    ]


# ─────────────────────────────────────────────────────────────
# GET /feeds/chart/{symbol}
# ─────────────────────────────────────────────────────────────

@feeds_router.get(
    "/chart/{asset_ticker}",
    response_model=CandlestickDataResponse,
    summary="Get OHLC candlestick data for a single asset",
)
async def get_candlestick_chart_data(
    asset_ticker: str,
    resolution: str = Query(default="5", description="Candle resolution in minutes"),
    lookback_hours: int = Query(default=24, ge=1, le=168),
) -> CandlestickDataResponse:
    """
    Returns OHLC candle data for the given asset, used to render
    the price chart in the PythGuard dashboard.

    Asset ticker examples: SOL, BTC, ETH
    """
    pyth_symbol = SUPPORTED_CRYPTO_SYMBOLS.get(asset_ticker.upper())

    if pyth_symbol is None:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unsupported asset: {asset_ticker}. "
                   f"Supported: {list(SUPPORTED_CRYPTO_SYMBOLS.keys())}",
        )

    current_timestamp = int(time.time())
    start_timestamp   = current_timestamp - (lookback_hours * 3600)

    raw_candles = _pyth_mcp_client.get_candlestick_data(
        symbol=pyth_symbol,
        resolution_minutes=resolution,
        from_timestamp=start_timestamp,
        to_timestamp=current_timestamp,
    )

    return CandlestickDataResponse(
        symbol=pyth_symbol,
        resolution=resolution,
        candles=[
            CandlestickResponse(
                timestamp=candle.timestamp,
                open_price=candle.open_price,
                high_price=candle.high_price,
                low_price=candle.low_price,
                close_price=candle.close_price,
                volume=candle.volume,
            )
            for candle in raw_candles
        ],
    )


# ─────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────

def _classify_confidence_risk(confidence_ratio: float) -> RiskLevelSchema:
    """Maps a confidence ratio to a RiskLevel for display purposes."""
    if confidence_ratio >= settings.confidence_ratio_high_risk_threshold:
        return RiskLevelSchema.HIGH
    if confidence_ratio >= settings.confidence_ratio_medium_risk_threshold:
        return RiskLevelSchema.MEDIUM
    return RiskLevelSchema.LOW
