"""
PythGuard Telegram Alert Service.

Sends real-time Telegram DMs when a monitored wallet's risk score
crosses the HIGH threshold (75+), giving users time to act before
liquidation happens.

Setup:
  1. Create a Telegram bot via @BotFather → get TELEGRAM_BOT_TOKEN
  2. Start a chat with your bot → get your TELEGRAM_CHAT_ID
  3. Set both in .env
  4. Run: python -m app.core.telegram_alerts

The service polls the PythGuard backend every 30 seconds for each
registered wallet and sends an alert when score transitions into HIGH.
It tracks previous states to avoid spamming repeated alerts.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx
import structlog

logger = structlog.get_logger(__name__)

# ─────────────────────────────────────────────────────────────
# Configuration (loaded from environment)
# ─────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID      = os.getenv("TELEGRAM_CHAT_ID", "")
PYTHGUARD_API_BASE    = os.getenv("PYTHGUARD_API_URL", "http://localhost:8000/api/v1")
ALERT_POLLING_SECONDS = int(os.getenv("ALERT_POLLING_SECONDS", "30"))
HIGH_RISK_THRESHOLD   = float(os.getenv("HIGH_RISK_SCORE_THRESHOLD", "75.0"))

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


# ─────────────────────────────────────────────────────────────
# State tracking
# ─────────────────────────────────────────────────────────────

@dataclass
class WalletAlertState:
    """
    Tracks the previous risk state for a wallet so we only
    send alerts on state *transitions* (e.g. MEDIUM → HIGH),
    not on every polling cycle.
    """
    wallet_address: str
    previous_risk_level: str = "LOW"
    previous_highest_score: float = 0.0
    last_alert_sent_at: float = 0.0
    alert_cooldown_seconds: float = 300.0  # 5 min between repeated HIGH alerts


# ─────────────────────────────────────────────────────────────
# Telegram message sender
# ─────────────────────────────────────────────────────────────

async def send_telegram_alert(
    http_client: httpx.AsyncClient,
    message_text: str,
) -> bool:
    """
    Sends a formatted message to the configured Telegram chat.

    Returns True if the message was sent successfully.
    Telegram uses MarkdownV2 formatting — special chars must be escaped.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning(
            "telegram_not_configured",
            hint="Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env",
        )
        return False

    try:
        telegram_response = await http_client.post(
            f"{TELEGRAM_API_BASE}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message_text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10.0,
        )
        telegram_response.raise_for_status()
        logger.info("telegram_alert_sent", chat_id=TELEGRAM_CHAT_ID)
        return True

    except httpx.HTTPError as telegram_error:
        logger.error("telegram_send_failed", error=str(telegram_error))
        return False


def compose_high_risk_alert_message(
    wallet_address: str,
    risk_summary: dict,
) -> str:
    """
    Composes a formatted HTML Telegram message for a HIGH risk alert.
    Includes the highest-risk position details and a direct action prompt.
    """
    truncated_wallet = f"{wallet_address[:6]}…{wallet_address[-4:]}"
    highest_score    = risk_summary.get("highest_risk_score", 0)

    # Find the highest-risk position for detail
    all_positions = risk_summary.get("positions", [])
    riskiest_position = max(
        all_positions,
        key=lambda position_data: position_data.get("composite_risk_score", 0),
        default=None,
    )

    position_detail = ""
    if riskiest_position:
        liquidation_buffer = riskiest_position.get(
            "estimated_liquidation_price_drop_percent", 0
        )
        confidence_ratio = riskiest_position.get("current_confidence_ratio", 0)
        is_trending = riskiest_position.get("is_confidence_trending_upward", False)

        position_detail = (
            f"\n\n<b>Highest Risk Position:</b>"
            f"\n• Asset: <code>{riskiest_position.get('collateral_asset')}</code>"
            f"\n• Protocol: {riskiest_position.get('protocol_name')}"
            f"\n• Liquidation buffer: <b>{liquidation_buffer:.1f}%</b>"
            f"\n• Oracle confidence ratio: {confidence_ratio:.4%}"
            f"\n• Confidence trending up: {'⚠️ Yes' if is_trending else 'No'}"
        )

    return (
        f"🚨 <b>PythGuard HIGH RISK ALERT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Wallet: <code>{truncated_wallet}</code>\n"
        f"Risk Score: <b>{highest_score:.1f}/100</b> 🔴\n"
        f"Open positions: {risk_summary.get('position_count', 0)}"
        f"{position_detail}\n\n"
        f"⚡ <b>Action required:</b> Add collateral or reduce your debt to avoid liquidation.\n\n"
        f"<i>Powered by Pyth confidence intervals · PythGuard</i>"
    )


def compose_recovery_message(wallet_address: str, new_score: float) -> str:
    """Sends a follow-up message when risk drops back to MEDIUM/LOW."""
    truncated_wallet = f"{wallet_address[:6]}…{wallet_address[-4:]}"
    return (
        f"✅ <b>PythGuard: Risk Reduced</b>\n"
        f"Wallet <code>{truncated_wallet}</code> is back to "
        f"{'MEDIUM 🟡' if new_score >= 45 else 'LOW 🟢'} risk "
        f"(score: {new_score:.1f}/100)"
    )


# ─────────────────────────────────────────────────────────────
# Alert monitor loop
# ─────────────────────────────────────────────────────────────

async def monitor_wallet_for_alerts(
    http_client: httpx.AsyncClient,
    wallet_alert_state: WalletAlertState,
) -> None:
    """
    Polls the PythGuard API for one wallet and sends a Telegram
    alert if the risk level transitions to HIGH.
    """
    wallet_address = wallet_alert_state.wallet_address

    try:
        risk_response = await http_client.get(
            f"{PYTHGUARD_API_BASE}/risk/{wallet_address}",
            timeout=15.0,
        )
        risk_response.raise_for_status()
        risk_summary = risk_response.json()

    except httpx.HTTPError as api_error:
        logger.warning("risk_api_unreachable", wallet=wallet_address, error=str(api_error))
        return

    current_risk_level  = risk_summary.get("overall_risk_level", "LOW")
    current_highest_score = risk_summary.get("highest_risk_score", 0.0)
    current_timestamp   = time.time()

    has_crossed_into_high_risk = (
        current_risk_level == "HIGH"
        and wallet_alert_state.previous_risk_level != "HIGH"
    )

    cooldown_elapsed = (
        current_timestamp - wallet_alert_state.last_alert_sent_at
        > wallet_alert_state.alert_cooldown_seconds
    )

    should_send_high_alert = has_crossed_into_high_risk or (
        current_risk_level == "HIGH" and cooldown_elapsed
    )

    if should_send_high_alert:
        alert_message = compose_high_risk_alert_message(
            wallet_address=wallet_address,
            risk_summary=risk_summary,
        )
        alert_was_sent = await send_telegram_alert(
            http_client=http_client,
            message_text=alert_message,
        )
        if alert_was_sent:
            wallet_alert_state.last_alert_sent_at = current_timestamp

    # Send recovery message when risk drops from HIGH to MEDIUM/LOW
    elif (
        wallet_alert_state.previous_risk_level == "HIGH"
        and current_risk_level != "HIGH"
    ):
        recovery_message = compose_recovery_message(
            wallet_address=wallet_address,
            new_score=current_highest_score,
        )
        await send_telegram_alert(
            http_client=http_client,
            message_text=recovery_message,
        )

    wallet_alert_state.previous_risk_level    = current_risk_level
    wallet_alert_state.previous_highest_score = current_highest_score


async def run_alert_monitor(monitored_wallet_addresses: list[str]) -> None:
    """
    Main alert monitor loop.
    Polls all monitored wallets every ALERT_POLLING_SECONDS seconds.

    Args:
        monitored_wallet_addresses: List of Solana wallet addresses to monitor
    """
    wallet_states = [
        WalletAlertState(wallet_address=wallet_address)
        for wallet_address in monitored_wallet_addresses
    ]

    logger.info(
        "alert_monitor_started",
        wallets=len(wallet_states),
        polling_seconds=ALERT_POLLING_SECONDS,
    )

    async with httpx.AsyncClient() as http_client:
        while True:
            for wallet_alert_state in wallet_states:
                await monitor_wallet_for_alerts(
                    http_client=http_client,
                    wallet_alert_state=wallet_alert_state,
                )
            await asyncio.sleep(ALERT_POLLING_SECONDS)


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    wallets_to_monitor_env = os.getenv("MONITORED_WALLETS", "")

    if not wallets_to_monitor_env:
        print("Set MONITORED_WALLETS=wallet1,wallet2 in your .env file")
        raise SystemExit(1)

    wallets_to_monitor = [
        wallet.strip()
        for wallet in wallets_to_monitor_env.split(",")
        if wallet.strip()
    ]

    asyncio.run(run_alert_monitor(wallets_to_monitor))
