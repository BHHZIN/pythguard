"""
Unit tests for the PythGuard Risk Engine.

Tests each scoring component in isolation and verifies the
composite score produces the correct RiskLevel output.

Run with: pytest backend/tests/ -v --cov=app/core
"""
import pytest
from app.core.risk_engine import RiskEngine, RiskLevel, PositionRiskScore


@pytest.fixture
def risk_engine_instance() -> RiskEngine:
    """Provides a fresh RiskEngine instance for each test."""
    return RiskEngine()


# ─────────────────────────────────────────────────────────────
# Collateral ratio scorer
# ─────────────────────────────────────────────────────────────

class TestCollateralRatioScorer:

    def test_returns_zero_when_position_is_far_from_liquidation(
        self, risk_engine_instance
    ):
        # Collateral is 2× the liquidation threshold — maximum safety
        score = risk_engine_instance._score_collateral_ratio(
            current_collateral_ratio=1.60,
            liquidation_threshold_ratio=0.80,
        )
        assert score == pytest.approx(0.0, abs=1.0)

    def test_returns_one_hundred_when_at_liquidation_threshold(
        self, risk_engine_instance
    ):
        score = risk_engine_instance._score_collateral_ratio(
            current_collateral_ratio=0.80,
            liquidation_threshold_ratio=0.80,
        )
        assert score == 100.0

    def test_returns_one_hundred_when_below_liquidation_threshold(
        self, risk_engine_instance
    ):
        # Already undercollateralized — should be max risk
        score = risk_engine_instance._score_collateral_ratio(
            current_collateral_ratio=0.70,
            liquidation_threshold_ratio=0.80,
        )
        assert score == 100.0

    def test_returns_fifty_when_halfway_to_liquidation(
        self, risk_engine_instance
    ):
        # Threshold = 0.80, max_safe = 1.60, halfway = 1.20
        score = risk_engine_instance._score_collateral_ratio(
            current_collateral_ratio=1.20,
            liquidation_threshold_ratio=0.80,
        )
        assert score == pytest.approx(50.0, abs=2.0)


# ─────────────────────────────────────────────────────────────
# Confidence interval scorer
# ─────────────────────────────────────────────────────────────

class TestConfidenceIntervalScorer:

    def test_returns_zero_for_very_low_confidence_ratio(
        self, risk_engine_instance
    ):
        # Ratio well below low threshold (0.001) — oracle is certain
        score = risk_engine_instance._score_confidence_interval(
            confidence_ratio=0.0001
        )
        assert score == 0.0

    def test_returns_one_hundred_for_very_high_confidence_ratio(
        self, risk_engine_instance
    ):
        # Ratio above high threshold (0.005) — oracle is uncertain
        score = risk_engine_instance._score_confidence_interval(
            confidence_ratio=0.01
        )
        assert score == 100.0

    def test_returns_fifty_at_midpoint_between_thresholds(
        self, risk_engine_instance
    ):
        midpoint_confidence_ratio = (0.001 + 0.005) / 2  # 0.003
        score = risk_engine_instance._score_confidence_interval(
            confidence_ratio=midpoint_confidence_ratio
        )
        assert score == pytest.approx(50.0, abs=1.0)

    def test_returns_zero_for_exactly_zero_confidence_ratio(
        self, risk_engine_instance
    ):
        score = risk_engine_instance._score_confidence_interval(
            confidence_ratio=0.0
        )
        assert score == 0.0


# ─────────────────────────────────────────────────────────────
# Confidence trend detector
# ─────────────────────────────────────────────────────────────

class TestConfidenceTrendDetector:

    def test_detects_upward_trend_correctly(self, risk_engine_instance):
        # Confidence ratios clearly rising over time
        rising_confidence_history = [0.001, 0.0012, 0.0015, 0.002, 0.003, 0.004]
        is_trending_upward = risk_engine_instance._detect_upward_confidence_trend(
            recent_confidence_ratios=rising_confidence_history
        )
        assert is_trending_upward is True

    def test_detects_stable_or_falling_trend_correctly(
        self, risk_engine_instance
    ):
        falling_confidence_history = [0.004, 0.003, 0.002, 0.0015, 0.001, 0.0008]
        is_trending_upward = risk_engine_instance._detect_upward_confidence_trend(
            recent_confidence_ratios=falling_confidence_history
        )
        assert is_trending_upward is False

    def test_returns_false_when_insufficient_data_points(
        self, risk_engine_instance
    ):
        is_trending_upward = risk_engine_instance._detect_upward_confidence_trend(
            recent_confidence_ratios=[0.001, 0.002]
        )
        assert is_trending_upward is False


# ─────────────────────────────────────────────────────────────
# Liquidation price drop estimator
# ─────────────────────────────────────────────────────────────

class TestLiquidationPriceDropEstimator:

    def test_estimates_correct_drop_for_healthy_position(
        self, risk_engine_instance
    ):
        # Collateral = 1.60, threshold = 0.80
        # Price must drop 50% before liquidation: 1 - (0.80/1.60) = 0.50
        estimated_drop = risk_engine_instance._estimate_liquidation_price_drop_percent(
            current_collateral_ratio=1.60,
            liquidation_threshold_ratio=0.80,
        )
        assert estimated_drop == pytest.approx(50.0, abs=0.1)

    def test_returns_zero_when_already_at_liquidation_threshold(
        self, risk_engine_instance
    ):
        estimated_drop = risk_engine_instance._estimate_liquidation_price_drop_percent(
            current_collateral_ratio=0.80,
            liquidation_threshold_ratio=0.80,
        )
        assert estimated_drop == 0.0


# ─────────────────────────────────────────────────────────────
# Full composite score + risk level
# ─────────────────────────────────────────────────────────────

class TestCompositeRiskScore:

    def test_healthy_position_produces_low_risk_level(
        self, risk_engine_instance
    ):
        position_risk = risk_engine_instance.compute_position_risk_score(
            wallet_address="TestWallet123",
            protocol_name="marginfi",
            collateral_asset_symbol="SOL/USD",
            borrowed_asset_symbol="USDC/USD",
            current_collateral_ratio=1.50,       # healthy
            liquidation_threshold_ratio=0.80,
            current_confidence_ratio=0.0005,      # very low — oracle is certain
            recent_confidence_ratios=[0.0005] * 10,
        )
        assert position_risk.risk_level == RiskLevel.LOW
        assert position_risk.composite_risk_score < 45.0

    def test_near_liquidation_produces_high_risk_level(
        self, risk_engine_instance
    ):
        position_risk = risk_engine_instance.compute_position_risk_score(
            wallet_address="TestWallet456",
            protocol_name="marginfi",
            collateral_asset_symbol="SOL/USD",
            borrowed_asset_symbol="USDC/USD",
            current_collateral_ratio=0.85,        # near liquidation threshold
            liquidation_threshold_ratio=0.80,
            current_confidence_ratio=0.008,        # high — oracle is uncertain
            recent_confidence_ratios=[0.004, 0.005, 0.006, 0.007, 0.008],
        )
        assert position_risk.risk_level == RiskLevel.HIGH
        assert position_risk.composite_risk_score >= 75.0

    def test_score_is_clamped_between_zero_and_one_hundred(
        self, risk_engine_instance
    ):
        position_risk = risk_engine_instance.compute_position_risk_score(
            wallet_address="TestWallet789",
            protocol_name="kamino",
            collateral_asset_symbol="ETH/USD",
            borrowed_asset_symbol="USDC/USD",
            current_collateral_ratio=0.50,         # severely undercollateralized
            liquidation_threshold_ratio=0.80,
            current_confidence_ratio=0.10,          # extreme uncertainty
            recent_confidence_ratios=[0.05, 0.08, 0.10, 0.10, 0.10],
        )
        assert 0.0 <= position_risk.composite_risk_score <= 100.0

    def test_alert_message_is_non_empty_string(self, risk_engine_instance):
        position_risk = risk_engine_instance.compute_position_risk_score(
            wallet_address="TestWalletABC",
            protocol_name="marginfi",
            collateral_asset_symbol="SOL/USD",
            borrowed_asset_symbol="USDC/USD",
            current_collateral_ratio=1.20,
            liquidation_threshold_ratio=0.80,
            current_confidence_ratio=0.002,
            recent_confidence_ratios=[0.002] * 5,
        )
        assert isinstance(position_risk.alert_message, str)
        assert len(position_risk.alert_message) > 0
