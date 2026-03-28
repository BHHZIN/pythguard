"""
Risk API routes.

Supports any asset found in a wallet's real positions —
not just SOL, ETH, JitoSOL.
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
from app.protocols.marginfi_adapter import fetch_positions_for_wallet
from app.pyth.mcp_client import PythMCPClient

logger = structlog.get_logger(__name__)

risk_router  = APIRouter(prefix="/risk", tags=["Risk"])
_risk_engine = RiskEngine()
_pyth_client = PythMCPClient()


@risk_router.get(
    "/{wallet_address}",
    response_model=WalletRiskSummaryResponse,
    summary="Get full risk summary for a wallet",
)
async def get_wallet_risk_summary(
    wallet_address: str,
) -> WalletRiskSummaryResponse:
    """
    Returns risk scores for all open positions found for the wallet.
    Supports any asset — dynamically queries Pyth for whatever collateral
    the wallet is holding.
    """
    async with httpx.AsyncClient() as http_client:
        # Fetch real positions from Marginfi
        try:
            open_positions = await fetch_positions_for_wallet(
                wallet_address=wallet_address,
                http_client=http_client,
            )
        except Exception as position_error:
            logger.error("position_fetch_failed", error=str(position_error))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to fetch positions: {str(position_error)}",
            )

        if not open_positions:
            return WalletRiskSummaryResponse(
                wallet_address=wallet_address,
                overall_risk_level=RiskLevelSchema.LOW,
                highest_risk_score=0.0,
                position_count=0,
                positions=[],
                computed_at_timestamp=int(time.time()),
            )

        # Build the set of unique collateral symbols found in this wallet
        # e.g. could be SOL, BTC, BONK, PYTH, mSOL — whatever they hold
        unique_collateral_symbols = list({
            f"Crypto.{position['collateral_asset_symbol']}/USD"
            for position in open_positions
            if position.get("collateral_asset_symbol")
        })

        # Fetch live Pyth prices for all assets in one call
        try:
            latest_pyth_prices = _pyth_client.get_latest_prices(
                symbols=unique_collateral_symbols,
            )
            pyth_price_lookup = {
                price_data.symbol: price_data
                for price_data in latest_pyth_prices
            }
        except Exception as pyth_error:
            logger.warning(
                "pyth_price_fetch_failed",
                error=str(pyth_error),
                symbols=unique_collateral_symbols,
            )
            pyth_price_lookup = {}

        scored_positions: list[PositionRiskResponse] = []

        for open_position in open_positions:
            collateral_symbol = (
                f"Crypto.{open_position['collateral_asset_symbol']}/USD"
            )

            pyth_price_data = pyth_price_lookup.get(collateral_symbol)

            if pyth_price_data is None:
                logger.warning(
                    "no_pyth_data_for_asset",
                    asset=collateral_symbol,
                    wallet=wallet_address,
                )
                # Still score the position using collateral ratio only
                # (no confidence data available for this asset)
                confidence_ratio    = 0.0
                recent_conf_ratios  = []
            else:
                confidence_ratio = pyth_price_data.confidence_ratio

                # Fetch 30-min confidence trend for this asset
                try:
                    recent_candles = _pyth_client.get_recent_candlesticks_for_confidence_trend(
                        symbol=collateral_symbol,
                        lookback_minutes=30,
                    )
                    recent_conf_ratios = [
                        (candle.high_price - candle.low_price) / candle.close_price
                        for candle in recent_candles
                        if candle.close_price > 0
                    ]
                except Exception:
                    recent_conf_ratios = []

            position_risk = _risk_engine.compute_position_risk_score(
                wallet_address=wallet_address,
                protocol_name=open_position["protocol_name"],
                collateral_asset_symbol=open_position["collateral_asset_symbol"],
                borrowed_asset_symbol=open_position["borrowed_asset_symbol"],
                current_collateral_ratio=open_position["current_collateral_ratio"],
                liquidation_threshold_ratio=open_position[
                    "liquidation_threshold_ratio"
                ],
                current_confidence_ratio=confidence_ratio,
                recent_confidence_ratios=recent_conf_ratios,
            )

            scored_positions.append(PositionRiskResponse(
                wallet_address=wallet_address,
                protocol_name=position_risk.protocol_name,
                collateral_asset=position_risk.collateral_asset,
                borrowed_asset=position_risk.borrowed_asset,
                composite_risk_score=position_risk.composite_risk_score,
                collateral_ratio_score=position_risk.collateral_ratio_score,
                confidence_interval_score=position_risk.confidence_interval_score,
                volatility_trend_score=position_risk.volatility_trend_score,
                risk_level=RiskLevelSchema(position_risk.risk_level.value),
                estimated_liquidation_price_drop_percent=(
                    position_risk.estimated_liquidation_price_drop_percent
                ),
                current_confidence_ratio=position_risk.current_confidence_ratio,
                is_confidence_trending_upward=(
                    position_risk.is_confidence_trending_upward
                ),
                alert_message=position_risk.alert_message,
            ))

        highest_score = (
            max(p.composite_risk_score for p in scored_positions)
            if scored_positions else 0.0
        )

        overall_level = _determine_overall_risk_level(scored_positions)

        return WalletRiskSummaryResponse(
            wallet_address=wallet_address,
            overall_risk_level=overall_level,
            highest_risk_score=highest_score,
            position_count=len(scored_positions),
            positions=scored_positions,
            computed_at_timestamp=int(time.time()),
        )


def _determine_overall_risk_level(
    all_positions: list[PositionRiskResponse],
) -> RiskLevelSchema:
    if any(p.risk_level == RiskLevelSchema.HIGH for p in all_positions):
        return RiskLevelSchema.HIGH
    if any(p.risk_level == RiskLevelSchema.MEDIUM for p in all_positions):
        return RiskLevelSchema.MEDIUM
    return RiskLevelSchema.LOW
