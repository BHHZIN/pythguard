"""
PythGuard API schemas.

Pydantic models used for request validation and response serialization
across all API endpoints.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator
import re


# ─────────────────────────────────────────────────────────────
# Shared enums
# ─────────────────────────────────────────────────────────────

class RiskLevelSchema(str, Enum):
    LOW    = "LOW"
    MEDIUM = "MEDIUM"
    HIGH   = "HIGH"


# ─────────────────────────────────────────────────────────────
# Price Feed schemas
# ─────────────────────────────────────────────────────────────

class PriceFeedStatusResponse(BaseModel):
    """Current status of a Pyth price feed."""
    asset_symbol: str
    normalized_price: float
    confidence_ratio: float
    risk_level_from_confidence: RiskLevelSchema
    publish_timestamp: int
    is_feed_fresh: bool = Field(
        description="False if the feed is older than 60 seconds"
    )


# ─────────────────────────────────────────────────────────────
# Position schemas
# ─────────────────────────────────────────────────────────────

class PositionRiskResponse(BaseModel):
    """Risk assessment for a single lending/borrowing position."""
    wallet_address: str
    protocol_name: str
    collateral_asset: str
    borrowed_asset: str
    composite_risk_score: float = Field(ge=0, le=100)
    collateral_ratio_score: float
    confidence_interval_score: float
    volatility_trend_score: float
    risk_level: RiskLevelSchema
    estimated_liquidation_price_drop_percent: float
    current_confidence_ratio: float
    is_confidence_trending_upward: bool
    alert_message: str


class WalletRiskSummaryResponse(BaseModel):
    """Full risk summary for all positions of a wallet."""
    wallet_address: str
    overall_risk_level: RiskLevelSchema
    highest_risk_score: float
    position_count: int
    positions: list[PositionRiskResponse]
    computed_at_timestamp: int


# ─────────────────────────────────────────────────────────────
# Candlestick schemas (for charts)
# ─────────────────────────────────────────────────────────────

class CandlestickResponse(BaseModel):
    """A single OHLC candle for the frontend chart."""
    timestamp: int
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: Optional[float] = None


class CandlestickDataResponse(BaseModel):
    """Response for the chart endpoint."""
    symbol: str
    resolution: str
    candles: list[CandlestickResponse]
    is_truncated: bool = False


# ─────────────────────────────────────────────────────────────
# Error schema
# ─────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """Standard error response shape for all 4xx/5xx responses."""
    error_code: str
    error_message: str
    details: Optional[str] = None
