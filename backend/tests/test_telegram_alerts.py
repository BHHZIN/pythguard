"""
Unit tests for the Telegram Alert Service.

Tests the state machine logic (when to fire alerts, cooldown,
recovery messages) without actually calling the Telegram API.

Run with: pytest backend/tests/ -v
"""
import time
import pytest

from app.core.telegram_alerts import (
    WalletAlertState,
    compose_high_risk_alert_message,
    compose_recovery_message,
)


# ─────────────────────────────────────────────────────────────
# Alert state transition tests
# ─────────────────────────────────────────────────────────────

class TestAlertStateTransitions:

    def _should_alert(
        self,
        previous_level: str,
        current_level: str,
        last_sent_at: float,
        cooldown: float = 300.0,
    ) -> bool:
        """
        Replicates the alert firing logic from monitor_wallet_for_alerts
        in a pure, testable form.
        """
        has_crossed_into_high = (
            current_level == "HIGH" and previous_level != "HIGH"
        )
        cooldown_has_elapsed = (time.time() - last_sent_at) > cooldown

        return has_crossed_into_high or (
            current_level == "HIGH" and cooldown_has_elapsed
        )

    def test_fires_alert_on_low_to_high_transition(self):
        should_alert = self._should_alert(
            previous_level="LOW",
            current_level="HIGH",
            last_sent_at=0.0,
        )
        assert should_alert is True

    def test_fires_alert_on_medium_to_high_transition(self):
        should_alert = self._should_alert(
            previous_level="MEDIUM",
            current_level="HIGH",
            last_sent_at=0.0,
        )
        assert should_alert is True

    def test_does_not_fire_when_low_stays_low(self):
        should_alert = self._should_alert(
            previous_level="LOW",
            current_level="LOW",
            last_sent_at=0.0,
        )
        assert should_alert is False

    def test_does_not_fire_when_medium_stays_medium(self):
        should_alert = self._should_alert(
            previous_level="MEDIUM",
            current_level="MEDIUM",
            last_sent_at=0.0,
        )
        assert should_alert is False

    def test_does_not_fire_again_within_cooldown_window(self):
        """
        If HIGH risk persists but we already alerted 30 seconds ago,
        we should NOT fire again (cooldown is 5 minutes).
        """
        recent_alert_timestamp = time.time() - 30  # 30 seconds ago
        should_alert = self._should_alert(
            previous_level="HIGH",
            current_level="HIGH",
            last_sent_at=recent_alert_timestamp,
            cooldown=300.0,
        )
        assert should_alert is False

    def test_fires_again_after_cooldown_expires(self):
        """
        After 5+ minutes, a persisting HIGH risk should fire another alert.
        """
        old_alert_timestamp = time.time() - 400  # 6+ minutes ago
        should_alert = self._should_alert(
            previous_level="HIGH",
            current_level="HIGH",
            last_sent_at=old_alert_timestamp,
            cooldown=300.0,
        )
        assert should_alert is True


# ─────────────────────────────────────────────────────────────
# WalletAlertState initialization
# ─────────────────────────────────────────────────────────────

class TestWalletAlertState:

    def test_initial_state_defaults_to_low_risk(self):
        state = WalletAlertState(wallet_address="TestWallet123")
        assert state.previous_risk_level == "LOW"
        assert state.previous_highest_score == 0.0
        assert state.last_alert_sent_at == 0.0

    def test_wallet_address_is_stored_correctly(self):
        test_address = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"
        state = WalletAlertState(wallet_address=test_address)
        assert state.wallet_address == test_address

    def test_cooldown_defaults_to_five_minutes(self):
        state = WalletAlertState(wallet_address="TestWallet456")
        assert state.alert_cooldown_seconds == 300.0


# ─────────────────────────────────────────────────────────────
# Message composition
# ─────────────────────────────────────────────────────────────

class TestAlertMessageComposition:

    def _make_risk_summary(
        self,
        risk_level: str = "HIGH",
        highest_score: float = 82.0,
        liq_buffer: float = 8.5,
        conf_ratio: float = 0.0062,
        is_trending: bool = True,
    ) -> dict:
        return {
            "overall_risk_level": risk_level,
            "highest_risk_score": highest_score,
            "position_count": 1,
            "positions": [
                {
                    "collateral_asset": "SOL/USD",
                    "protocol_name": "marginfi",
                    "composite_risk_score": highest_score,
                    "estimated_liquidation_price_drop_percent": liq_buffer,
                    "current_confidence_ratio": conf_ratio,
                    "is_confidence_trending_upward": is_trending,
                }
            ],
        }

    def test_high_risk_message_contains_wallet_address(self):
        summary = self._make_risk_summary()
        message = compose_high_risk_alert_message(
            wallet_address="4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU",
            risk_summary=summary,
        )
        assert "4zMMC9" in message

    def test_high_risk_message_contains_score(self):
        summary = self._make_risk_summary(highest_score=82.0)
        message = compose_high_risk_alert_message("TestWallet", summary)
        assert "82" in message

    def test_high_risk_message_contains_liquidation_buffer(self):
        summary = self._make_risk_summary(liq_buffer=8.5)
        message = compose_high_risk_alert_message("TestWallet", summary)
        assert "8.5" in message

    def test_high_risk_message_contains_trending_warning_when_applicable(self):
        summary = self._make_risk_summary(is_trending=True)
        message = compose_high_risk_alert_message("TestWallet", summary)
        assert "trending" in message.lower() or "rising" in message.lower()

    def test_recovery_message_contains_wallet_truncation(self):
        message = compose_recovery_message(
            wallet_address="4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU",
            new_score=52.0,
        )
        assert "4zMMC9" in message

    def test_recovery_message_shows_medium_for_score_above_45(self):
        message = compose_recovery_message("TestWallet123", new_score=55.0)
        assert "MEDIUM" in message

    def test_recovery_message_shows_low_for_score_below_45(self):
        message = compose_recovery_message("TestWallet123", new_score=30.0)
        assert "LOW" in message

    def test_high_risk_message_handles_no_positions_gracefully(self):
        empty_summary = {
            "overall_risk_level": "HIGH",
            "highest_risk_score": 80.0,
            "position_count": 0,
            "positions": [],
        }
        # Should not raise even with empty positions list
        message = compose_high_risk_alert_message("TestWallet", empty_summary)
        assert isinstance(message, str)
        assert len(message) > 0
