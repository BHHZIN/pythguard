"""
PythGuard Risk Engine.

Calculates a 0–100 risk score for each open lending/borrowing position
using three signals sourced from Pyth:

  1. Collateral Ratio Component  (40% weight)
     How close the position is to the protocol's liquidation threshold.

  2. Confidence Interval Component  (40% weight)
     PythGuard's core differentiator — uses Pyth's confidence interval
     to detect oracle uncertainty. High confidence ratio = the market
     is uncertain about the true price = higher liquidation risk.

  3. Volatility Trend Component  (20% weight)
     Whether confidence has been rising over the last 30 minutes,
     indicating deteriorating market conditions ahead.

Score interpretation:
  0  – 44  → GREEN  (low risk)
  45 – 74  → YELLOW (medium risk — monitor closely)
  75 – 100 → RED    (high risk — act immediately)
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────
# Enums and result types
# ─────────────────────────────────────────────────────────────

class RiskLevel(str, Enum):
    LOW    = "LOW"
    MEDIUM = "MEDIUM"
    HIGH   = "HIGH"


@dataclass
class PositionRiskScore:
    """Full risk assessment for a single lending/borrowing position."""

    wallet_address: str
    protocol_name: str
    collateral_asset: str
    borrowed_asset: str

    # Final composite score 0–100
    composite_risk_score: float

    # Individual component scores (for transparency/debugging)
    collateral_ratio_score: float
    confidence_interval_score: float
    volatility_trend_score: float

    # Human-readable risk level
    risk_level: RiskLevel

    # Estimated price drop (%) needed to trigger liquidation
    estimated_liquidation_price_drop_percent: float

    # Current Pyth confidence ratio for the collateral asset
    current_confidence_ratio: float

    # Whether the confidence ratio has been rising over last 30 min
    is_confidence_trending_upward: bool

    # Alert message shown in the UI
    alert_message: str


# ─────────────────────────────────────────────────────────────
# Score weight constants
# ─────────────────────────────────────────────────────────────

COLLATERAL_RATIO_COMPONENT_WEIGHT   = 0.40
CONFIDENCE_INTERVAL_COMPONENT_WEIGHT = 0.40
VOLATILITY_TREND_COMPONENT_WEIGHT   = 0.20


# ─────────────────────────────────────────────────────────────
# RiskEngine
# ─────────────────────────────────────────────────────────────

class RiskEngine:
    """
    Computes composite risk scores for lending/borrowing positions.

    Inputs come from the Rust reader (on-chain data) and the
    Pyth MCP client (institutional price + confidence data).
    """

    # ── Public interface ──────────────────────────────────────

    def compute_position_risk_score(
        self,
        wallet_address: str,
        protocol_name: str,
        collateral_asset_symbol: str,
        borrowed_asset_symbol: str,
        current_collateral_ratio: float,
        liquidation_threshold_ratio: float,
        current_confidence_ratio: float,
        recent_confidence_ratios: list[float],
    ) -> PositionRiskScore:
        """
        Computes a full risk score for one open position.

        Args:
            wallet_address:              Owner's Solana wallet address
            protocol_name:               "marginfi", "kamino", etc.
            collateral_asset_symbol:     e.g. "SOL/USD"
            borrowed_asset_symbol:       e.g. "USDC/USD"
            current_collateral_ratio:    collateral_value / debt_value
            liquidation_threshold_ratio: Protocol's liquidation LTV (e.g. 0.80)
            current_confidence_ratio:    Pyth confidence / |price| (right now)
            recent_confidence_ratios:    List of confidence ratios over last 30 min

        Returns:
            PositionRiskScore with composite score and component breakdown
        """
        collateral_ratio_score = self._score_collateral_ratio(
            current_collateral_ratio=current_collateral_ratio,
            liquidation_threshold_ratio=liquidation_threshold_ratio,
        )

        confidence_interval_score = self._score_confidence_interval(
            confidence_ratio=current_confidence_ratio,
        )

        is_confidence_trending_upward = self._detect_upward_confidence_trend(
            recent_confidence_ratios=recent_confidence_ratios,
        )

        volatility_trend_score = self._score_volatility_trend(
            is_confidence_trending_upward=is_confidence_trending_upward,
            recent_confidence_ratios=recent_confidence_ratios,
        )

        composite_risk_score = (
            collateral_ratio_score   * COLLATERAL_RATIO_COMPONENT_WEIGHT
            + confidence_interval_score * CONFIDENCE_INTERVAL_COMPONENT_WEIGHT
            + volatility_trend_score    * VOLATILITY_TREND_COMPONENT_WEIGHT
        )

        # Clamp to [0, 100]
        composite_risk_score = max(0.0, min(100.0, composite_risk_score))

        risk_level = self._classify_risk_level(composite_risk_score)

        estimated_liquidation_price_drop_percent = (
            self._estimate_liquidation_price_drop_percent(
                current_collateral_ratio=current_collateral_ratio,
                liquidation_threshold_ratio=liquidation_threshold_ratio,
            )
        )

        alert_message = self._compose_alert_message(
            risk_level=risk_level,
            collateral_asset=collateral_asset_symbol,
            estimated_liquidation_drop=estimated_liquidation_price_drop_percent,
            is_confidence_trending_upward=is_confidence_trending_upward,
        )

        logger.info(
            "risk_score_computed",
            wallet=wallet_address,
            protocol=protocol_name,
            composite_score=composite_risk_score,
            risk_level=risk_level.value,
        )

        return PositionRiskScore(
            wallet_address=wallet_address,
            protocol_name=protocol_name,
            collateral_asset=collateral_asset_symbol,
            borrowed_asset=borrowed_asset_symbol,
            composite_risk_score=round(composite_risk_score, 2),
            collateral_ratio_score=round(collateral_ratio_score, 2),
            confidence_interval_score=round(confidence_interval_score, 2),
            volatility_trend_score=round(volatility_trend_score, 2),
            risk_level=risk_level,
            estimated_liquidation_price_drop_percent=round(
                estimated_liquidation_price_drop_percent, 2
            ),
            current_confidence_ratio=current_confidence_ratio,
            is_confidence_trending_upward=is_confidence_trending_upward,
            alert_message=alert_message,
        )

    # ── Component scorers ─────────────────────────────────────

    def _score_collateral_ratio(
        self,
        current_collateral_ratio: float,
        liquidation_threshold_ratio: float,
    ) -> float:
        """
        Scores how close a position is to liquidation.

        Returns 0 (safe) to 100 (at liquidation threshold).
        Positions below the threshold return 100 (already liquidatable).
        """
        # Guard: already undercollateralized
        if current_collateral_ratio <= liquidation_threshold_ratio:
            return 100.0

        # "Safety buffer" = how far above threshold the position is
        # A position at 2× the threshold has a 100% safety buffer
        maximum_safe_collateral_ratio = liquidation_threshold_ratio * 2.0
        safety_buffer = current_collateral_ratio - liquidation_threshold_ratio
        maximum_buffer = maximum_safe_collateral_ratio - liquidation_threshold_ratio

        # Guard: prevent division by zero on degenerate thresholds
        if maximum_buffer <= 0:
            return 100.0

        normalized_safety = safety_buffer / maximum_buffer
        collateral_score = (1.0 - min(normalized_safety, 1.0)) * 100.0

        return collateral_score

    def _score_confidence_interval(
        self,
        confidence_ratio: float,
    ) -> float:
        """
        Scores the current Pyth confidence ratio.

        This is PythGuard's core differentiator — high confidence ratio
        means the oracle is uncertain about the price, which increases
        the risk of unexpected liquidations.

        Thresholds (from config):
          < 0.001 (0.1%) → score near 0   (oracle is certain)
          > 0.005 (0.5%) → score near 100 (oracle is very uncertain)
        """
        low_threshold  = settings.confidence_ratio_medium_risk_threshold  # 0.001
        high_threshold = settings.confidence_ratio_high_risk_threshold     # 0.005

        # Guard: perfect certainty
        if confidence_ratio <= low_threshold:
            return 0.0

        # Guard: maximum uncertainty
        if confidence_ratio >= high_threshold:
            return 100.0

        # Linear interpolation between the two thresholds
        normalized_position = (
            (confidence_ratio - low_threshold)
            / (high_threshold - low_threshold)
        )
        return normalized_position * 100.0

    def _score_volatility_trend(
        self,
        is_confidence_trending_upward: bool,
        recent_confidence_ratios: list[float],
    ) -> float:
        """
        Scores the recent volatility trend.

        A rising confidence ratio trend over the last 30 minutes
        indicates the market is becoming less certain — a leading
        indicator of imminent price instability.
        """
        # Guard: not enough data for trend analysis
        if len(recent_confidence_ratios) < 3:
            return 0.0

        if not is_confidence_trending_upward:
            return 0.0

        # Magnitude of the trend: how fast confidence is rising
        recent_mean_confidence  = statistics.mean(recent_confidence_ratios[-5:])
        baseline_mean_confidence = statistics.mean(recent_confidence_ratios[:5])

        # Guard: no meaningful baseline
        if baseline_mean_confidence == 0:
            return 50.0

        trend_magnitude = (
            (recent_mean_confidence - baseline_mean_confidence)
            / baseline_mean_confidence
        )

        # Scale: 50% increase in confidence ratio → score of 100
        normalized_trend = min(trend_magnitude / 0.5, 1.0)
        return max(normalized_trend * 100.0, 0.0)

    # ── Helpers ───────────────────────────────────────────────

    def _detect_upward_confidence_trend(
        self,
        recent_confidence_ratios: list[float],
    ) -> bool:
        """
        Returns True if the confidence ratio has been rising
        over the last 30 minutes (more recent values are higher).
        """
        if len(recent_confidence_ratios) < 3:
            return False

        midpoint_index = len(recent_confidence_ratios) // 2
        earlier_half_mean = statistics.mean(
            recent_confidence_ratios[:midpoint_index]
        )
        recent_half_mean = statistics.mean(
            recent_confidence_ratios[midpoint_index:]
        )

        return recent_half_mean > earlier_half_mean

    def _classify_risk_level(self, composite_score: float) -> RiskLevel:
        """Maps a numeric score to a RiskLevel enum value."""
        if composite_score >= settings.high_risk_score_threshold:
            return RiskLevel.HIGH
        if composite_score >= settings.medium_risk_score_threshold:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _estimate_liquidation_price_drop_percent(
        self,
        current_collateral_ratio: float,
        liquidation_threshold_ratio: float,
    ) -> float:
        """
        Estimates how much the collateral price must drop (in %)
        before the position becomes liquidatable.

        Formula: drop% = 1 - (liquidation_threshold / collateral_ratio)
        """
        # Guard: already underwater
        if current_collateral_ratio <= liquidation_threshold_ratio:
            return 0.0

        required_drop = 1.0 - (
            liquidation_threshold_ratio / current_collateral_ratio
        )
        return required_drop * 100.0

    def _compose_alert_message(
        self,
        risk_level: RiskLevel,
        collateral_asset: str,
        estimated_liquidation_drop: float,
        is_confidence_trending_upward: bool,
    ) -> str:
        """Generates a human-readable alert message for the UI."""
        trend_note = (
            " Oracle confidence is rising — market uncertainty increasing."
            if is_confidence_trending_upward
            else ""
        )

        if risk_level == RiskLevel.HIGH:
            return (
                f"⚠️ HIGH RISK: Your {collateral_asset} position is "
                f"{estimated_liquidation_drop:.1f}% from liquidation.{trend_note} "
                f"Consider adding collateral or reducing debt immediately."
            )

        if risk_level == RiskLevel.MEDIUM:
            return (
                f"🟡 MEDIUM RISK: {collateral_asset} position has "
                f"{estimated_liquidation_drop:.1f}% buffer before liquidation.{trend_note} "
                f"Monitor closely."
            )

        return (
            f"✅ LOW RISK: {collateral_asset} position is healthy "
            f"({estimated_liquidation_drop:.1f}% buffer).{trend_note}"
        )
