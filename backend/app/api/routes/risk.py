"""
Risk API routes.

Endpoints for fetching risk scores for a wallet's lending positions.
"""
from __future__ import annotations

import time

import httpx
import structlog
from fastapi import APIRouter, HTTPException, status

from app.api.schemas import (
    PositionRiskResponse,
    RiskLevelSchema,
    WalletRiskSummaryResponse,
)
from app.config import settings
from app.core.risk_engine import RiskEngine, RiskLevel
from app.pyth.mcp_client import PythMCPClient

logger = structlog.get_logger(__name__)

risk_router = APIRouter(prefix="/risk", tags=["Risk"])

_risk_engine   = RiskEngine()
_pyth_mcp_client = PythMCPClient()

# ─────────────────────────────────────────────────────────────
# GET /risk/{wallet_address}
# ─────────────────────────────────────────────────────────────

@risk_router.get(
    "/{wallet_address}",
    response_model=WalletRiskSummaryResponse,
    summary="Get full risk summary for a wallet",
    description=(
        "Returns risk scores for all open lending/borrowing positions "
        "found for the given Solana wallet address. "
        "Scores are computed using Pyth price feeds, confidence intervals, "
        "and historical volatility trends via Pyth Pro."
    ),
)
async def get_wallet_risk_summary(wallet_address: str) -> WalletRiskSummaryResponse:
    """
    Main endpoint — fetches positions from the Rust reader,
    enriches them with Pyth Pro data, and returns risk scores.
    """
    risk_input_payload = await _fetch_risk_payload_from_rust_reader(
        wallet_address=wallet_address,
    )

    if not risk_input_payload.get("open_positions"):
        return WalletRiskSummaryResponse(
            wallet_address=wallet_address,
            overall_risk_level=RiskLevelSchema.LOW,
            highest_risk_score=0.0,
            position_count=0,
            positions=[],
            computed_at_timestamp=int(time.time()),
        )

    # Collect all unique asset symbols from open positions
    unique_collateral_symbols = list({
        f"Crypto.{position['collateral_asset_symbol']}/USD"
        for position in risk_input_payload["open_positions"]
    })

    # Fetch latest prices + confidence from Pyth Pro for all assets at once
    latest_pyth_prices = _pyth_mcp_client.get_latest_prices(
        symbols=unique_collateral_symbols,
    )

    # Build a lookup map: symbol → PythLatestPrice
    pyth_price_lookup = {
        price_data.symbol: price_data
        for price_data in latest_pyth_prices
    }

    scored_positions: list[PositionRiskResponse] = []

    for open_position in risk_input_payload["open_positions"]:
        collateral_symbol = (
            f"Crypto.{open_position['collateral_asset_symbol']}/USD"
        )

        pyth_price_data = pyth_price_lookup.get(collateral_symbol)

        # Guard: skip position if we couldn't get Pyth data for it
        if pyth_price_data is None:
            logger.warning(
                "no_pyth_data_for_asset",
                asset=collateral_symbol,
                wallet=wallet_address,
            )
            continue

        # Fetch 30-minute confidence history for trend analysis
        recent_candles = _pyth_mcp_client.get_recent_candlesticks_for_confidence_trend(
            symbol=collateral_symbol,
            lookback_minutes=30,
        )

        # Approximate confidence ratio history from candle price range
        # (high - low) / close is a proxy for oracle uncertainty per candle
        recent_confidence_ratios = [
            (candle.high_price - candle.low_price) / candle.close_price
            for candle in recent_candles
            if candle.close_price > 0
        ]

        position_risk_score = _risk_engine.compute_position_risk_score(
            wallet_address=wallet_address,
            protocol_name=open_position["protocol_name"],
            collateral_asset_symbol=open_position["collateral_asset_symbol"],
            borrowed_asset_symbol=open_position["borrowed_asset_symbol"],
            current_collateral_ratio=open_position["current_collateral_ratio"],
            liquidation_threshold_ratio=open_position[
                "liquidation_threshold_ratio"
            ],
            current_confidence_ratio=pyth_price_data.confidence_ratio,
            recent_confidence_ratios=recent_confidence_ratios,
        )

        scored_positions.append(PositionRiskResponse(
            wallet_address=wallet_address,
            protocol_name=position_risk_score.protocol_name,
            collateral_asset=position_risk_score.collateral_asset,
            borrowed_asset=position_risk_score.borrowed_asset,
            composite_risk_score=position_risk_score.composite_risk_score,
            collateral_ratio_score=position_risk_score.collateral_ratio_score,
            confidence_interval_score=(
                position_risk_score.confidence_interval_score
            ),
            volatility_trend_score=position_risk_score.volatility_trend_score,
            risk_level=RiskLevelSchema(position_risk_score.risk_level.value),
            estimated_liquidation_price_drop_percent=(
                position_risk_score.estimated_liquidation_price_drop_percent
            ),
            current_confidence_ratio=position_risk_score.current_confidence_ratio,
            is_confidence_trending_upward=(
                position_risk_score.is_confidence_trending_upward
            ),
            alert_message=position_risk_score.alert_message,
        ))

    highest_risk_score = (
        max(position.composite_risk_score for position in scored_positions)
        if scored_positions
        else 0.0
    )

    overall_risk_level = _determine_overall_risk_level(
        all_positions=scored_positions,
    )

    return WalletRiskSummaryResponse(
        wallet_address=wallet_address,
        overall_risk_level=overall_risk_level,
        highest_risk_score=highest_risk_score,
        position_count=len(scored_positions),
        positions=scored_positions,
        computed_at_timestamp=int(time.time()),
    )


# ─────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────

async def _fetch_risk_payload_from_rust_reader(wallet_address: str) -> dict:
    """
    Calls the Rust reader's /payload/{wallet} endpoint to get
    on-chain position data and raw Pyth feed snapshots.
    """
    rust_reader_url = (
        f"{settings.rust_reader_base_url}/payload/{wallet_address}"
    )

    async with httpx.AsyncClient(
        timeout=settings.rust_reader_timeout_seconds
    ) as http_client:
        try:
            rust_response = await http_client.get(rust_reader_url)
            rust_response.raise_for_status()
            return rust_response.json()

        except httpx.TimeoutException:
            logger.error("rust_reader_timeout", wallet=wallet_address)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Rust reader timed out — Solana RPC may be slow",
            )
        except httpx.HTTPStatusError as http_error:
            logger.error(
                "rust_reader_http_error",
                status=http_error.response.status_code,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to fetch on-chain data from Rust reader",
            )


def _determine_overall_risk_level(
    all_positions: list[PositionRiskResponse],
) -> RiskLevelSchema:
    """
    Returns the worst risk level across all positions.
    If any position is HIGH, the overall level is HIGH.
    """
    if any(position.risk_level == RiskLevelSchema.HIGH for position in all_positions):
        return RiskLevelSchema.HIGH
    if any(position.risk_level == RiskLevelSchema.MEDIUM for position in all_positions):
        return RiskLevelSchema.MEDIUM
    return RiskLevelSchema.LOW
