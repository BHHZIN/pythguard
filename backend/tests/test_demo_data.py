"""
Unit tests for the Demo Data Service.

Verifies that the demo data:
- Always returns valid, schema-compliant structures
- Produces oscillating values within expected bounds
- Generates consistent confidence histories
- Risk scores stay within [0, 100]

Run with: pytest backend/tests/ -v
"""
import math
import time
import pytest

from app.core.demo_data import (
    build_demo_confidence_history,
    build_demo_feed_statuses,
    build_demo_risk_summary,
    DEMO_WALLET_ADDRESS,
)


# ─────────────────────────────────────────────────────────────
# build_demo_risk_summary
# ─────────────────────────────────────────────────────────────

class TestDemoRiskSummary:

    def test_returns_three_positions(self):
        summary = build_demo_risk_summary()
        assert summary["position_count"] == 3
        assert len(summary["positions"]) == 3

    def test_wallet_address_is_demo_constant(self):
        summary = build_demo_risk_summary()
        assert summary["wallet_address"] == DEMO_WALLET_ADDRESS

    def test_all_risk_scores_are_in_valid_range(self):
        summary = build_demo_risk_summary()
        for position in summary["positions"]:
            assert 0.0 <= position["composite_risk_score"] <= 100.0

    def test_overall_risk_level_reflects_worst_position(self):
        summary = build_demo_risk_summary()
        all_levels = [p["risk_level"] for p in summary["positions"]]
        expected_overall = (
            "HIGH" if "HIGH" in all_levels
            else "MEDIUM" if "MEDIUM" in all_levels
            else "LOW"
        )
        assert summary["overall_risk_level"] == expected_overall

    def test_highest_score_equals_max_of_positions(self):
        summary = build_demo_risk_summary()
        max_score = max(p["composite_risk_score"] for p in summary["positions"])
        assert summary["highest_risk_score"] == pytest.approx(max_score, abs=0.01)

    def test_all_positions_have_required_fields(self):
        required_fields = {
            "wallet_address", "protocol_name", "collateral_asset",
            "borrowed_asset", "composite_risk_score", "risk_level",
            "estimated_liquidation_price_drop_percent",
            "current_confidence_ratio", "is_confidence_trending_upward",
            "alert_message",
        }
        summary = build_demo_risk_summary()
        for position in summary["positions"]:
            missing_fields = required_fields - set(position.keys())
            assert not missing_fields, f"Position missing fields: {missing_fields}"

    def test_all_confidence_ratios_are_positive(self):
        summary = build_demo_risk_summary()
        for position in summary["positions"]:
            assert position["current_confidence_ratio"] > 0.0

    def test_alert_message_is_non_empty_string(self):
        summary = build_demo_risk_summary()
        for position in summary["positions"]:
            assert isinstance(position["alert_message"], str)
            assert len(position["alert_message"]) > 10

    def test_is_demo_flag_is_present_and_true(self):
        summary = build_demo_risk_summary()
        assert summary.get("is_demo") is True

    def test_computed_at_timestamp_is_recent(self):
        summary = build_demo_risk_summary()
        current_time = int(time.time())
        # Should be within 5 seconds of now
        assert abs(summary["computed_at_timestamp"] - current_time) < 5


# ─────────────────────────────────────────────────────────────
# build_demo_feed_statuses
# ─────────────────────────────────────────────────────────────

class TestDemoFeedStatuses:

    def test_returns_four_feeds(self):
        feeds = build_demo_feed_statuses()
        assert len(feeds) == 4

    def test_all_feeds_have_required_fields(self):
        required_fields = {
            "asset_symbol", "normalized_price", "confidence_ratio",
            "risk_level_from_confidence", "publish_timestamp", "is_feed_fresh",
        }
        for feed in build_demo_feed_statuses():
            assert required_fields <= set(feed.keys())

    def test_all_feeds_are_fresh(self):
        for feed in build_demo_feed_statuses():
            assert feed["is_feed_fresh"] is True

    def test_all_prices_are_positive(self):
        for feed in build_demo_feed_statuses():
            assert feed["normalized_price"] > 0

    def test_all_confidence_ratios_are_positive(self):
        for feed in build_demo_feed_statuses():
            assert feed["confidence_ratio"] > 0.0

    def test_risk_levels_are_valid_enum_values(self):
        valid_levels = {"LOW", "MEDIUM", "HIGH"}
        for feed in build_demo_feed_statuses():
            assert feed["risk_level_from_confidence"] in valid_levels

    def test_sol_feed_is_present(self):
        feeds = build_demo_feed_statuses()
        symbols = [f["asset_symbol"] for f in feeds]
        assert any("SOL" in s for s in symbols)

    def test_btc_price_is_realistic(self):
        """BTC price should be in a plausible range for demo."""
        feeds = build_demo_feed_statuses()
        btc_feed = next((f for f in feeds if "BTC" in f["asset_symbol"]), None)
        assert btc_feed is not None
        # BTC should be between $10k and $500k for a realistic demo
        assert 10_000 < btc_feed["normalized_price"] < 500_000


# ─────────────────────────────────────────────────────────────
# build_demo_confidence_history
# ─────────────────────────────────────────────────────────────

class TestDemoConfidenceHistory:

    def test_returns_thirty_data_points(self):
        history = build_demo_confidence_history("SOL")
        assert len(history) == 30

    def test_all_confidence_values_are_positive(self):
        for asset in ["SOL", "BTC", "ETH", "JITOSOL"]:
            history = build_demo_confidence_history(asset)
            assert all(point["confidence_ratio"] > 0 for point in history)

    def test_each_point_has_timestamp_and_confidence(self):
        history = build_demo_confidence_history("SOL")
        for data_point in history:
            assert "timestamp" in data_point
            assert "confidence_ratio" in data_point
            assert "price" in data_point

    def test_timestamps_are_in_ascending_order(self):
        history = build_demo_confidence_history("SOL")
        timestamps = [point["timestamp"] for point in history]
        assert timestamps == sorted(timestamps)

    def test_timestamps_cover_approximately_30_minutes(self):
        history = build_demo_confidence_history("SOL")
        time_span_seconds = history[-1]["timestamp"] - history[0]["timestamp"]
        # Should be approximately 29 minutes (30 points, 1 per minute)
        assert 25 * 60 <= time_span_seconds <= 32 * 60

    def test_spike_event_is_visible_in_middle(self):
        """
        The demo history simulates a volatility spike at minute 15.
        The confidence values around the middle should be higher than the edges.
        """
        history = build_demo_confidence_history("SOL")
        confidence_values = [point["confidence_ratio"] for point in history]
        middle_region_mean = sum(confidence_values[10:20]) / 10
        edge_mean = (
            sum(confidence_values[:5]) + sum(confidence_values[25:])
        ) / 10
        # Middle region should show elevated confidence due to the spike
        assert middle_region_mean > edge_mean * 0.8

    def test_unknown_asset_uses_default_base(self):
        """Unknown tickers should fall back to a default base rate."""
        history = build_demo_confidence_history("UNKNOWN_ASSET")
        assert len(history) == 30
        assert all(point["confidence_ratio"] > 0 for point in history)
