"""
PythGuard Demo Data Service.

Provides realistic mock positions and Pyth-style price data
so judges and users without a Solana wallet can see the full
dashboard in action immediately — no wallet connection needed.

The mock confidence ratios are based on real historical Pyth
confidence intervals observed during volatile market periods.
"""
from __future__ import annotations

import time
import math
from dataclasses import dataclass


# ─────────────────────────────────────────────────────────────
# Demo wallet
# ─────────────────────────────────────────────────────────────

DEMO_WALLET_ADDRESS = "DEMO_pythguard_hackathon_2026"


# ─────────────────────────────────────────────────────────────
# Simulated market state (oscillates over time to feel alive)
# ─────────────────────────────────────────────────────────────

def _get_market_pulse() -> float:
    """
    Returns a value 0.0–1.0 that oscillates slowly over time.
    Used to make demo prices and confidence ratios feel live.
    Completes one full cycle every 90 seconds.
    """
    cycle_seconds = 90.0
    phase = (time.time() % cycle_seconds) / cycle_seconds
    return (math.sin(phase * 2 * math.pi) + 1.0) / 2.0


def build_demo_risk_summary() -> dict:
    """
    Builds a full WalletRiskSummary payload using simulated data.
    Values oscillate in real time so the dashboard feels live.

    Returns a dict matching the WalletRiskSummaryResponse schema.
    """
    market_pulse = _get_market_pulse()

    # ── Position 1: SOL/USDC — medium risk, confidence rising ──
    sol_price              = 136.40 + (market_pulse * 8.0)       # $136–$144
    sol_confidence_ratio   = 0.0018 + (market_pulse * 0.0032)    # 0.18%–0.50%
    sol_collateral_ratio   = 1.35 - (market_pulse * 0.25)        # 1.35 → 1.10
    sol_liq_buffer         = (1 - 0.80 / sol_collateral_ratio) * 100

    sol_conf_score  = min((sol_confidence_ratio - 0.001) / 0.004 * 100, 100)
    sol_coll_score  = max((1 - (sol_collateral_ratio - 0.80) / 0.80) * 100, 0)
    sol_trend_score = market_pulse * 65.0
    sol_composite   = (sol_coll_score * 0.40 + sol_conf_score * 0.40 + sol_trend_score * 0.20)
    sol_composite   = max(0.0, min(100.0, sol_composite))
    sol_risk_level  = "HIGH" if sol_composite >= 75 else ("MEDIUM" if sol_composite >= 45 else "LOW")

    # ── Position 2: ETH/USDC — low risk, stable ────────────────
    eth_confidence_ratio   = 0.0006 + (market_pulse * 0.0006)    # 0.06%–0.12%
    eth_collateral_ratio   = 1.80 - (market_pulse * 0.15)        # 1.80 → 1.65
    eth_liq_buffer         = (1 - 0.80 / eth_collateral_ratio) * 100

    eth_conf_score  = min((eth_confidence_ratio - 0.001) / 0.004 * 100, 100)
    eth_coll_score  = max((1 - (eth_collateral_ratio - 0.80) / 0.80) * 100, 0)
    eth_trend_score = market_pulse * 20.0
    eth_composite   = (eth_coll_score * 0.40 + eth_conf_score * 0.40 + eth_trend_score * 0.20)
    eth_composite   = max(0.0, min(100.0, eth_composite))
    eth_risk_level  = "HIGH" if eth_composite >= 75 else ("MEDIUM" if eth_composite >= 45 else "LOW")

    # ── Position 3: JitoSOL/USDC — high risk, near liquidation ──
    jito_confidence_ratio   = 0.0042 + (market_pulse * 0.0028)   # 0.42%–0.70%
    jito_collateral_ratio   = 0.92 - (market_pulse * 0.10)       # 0.92 → 0.82
    jito_liq_buffer         = max((1 - 0.80 / jito_collateral_ratio) * 100, 0)

    jito_conf_score  = min((jito_confidence_ratio - 0.001) / 0.004 * 100, 100)
    jito_coll_score  = max((1 - (jito_collateral_ratio - 0.80) / 0.80) * 100, 0)
    jito_trend_score = 60.0 + market_pulse * 40.0
    jito_composite   = (jito_coll_score * 0.40 + jito_conf_score * 0.40 + jito_trend_score * 0.20)
    jito_composite   = max(0.0, min(100.0, jito_composite))
    jito_risk_level  = "HIGH" if jito_composite >= 75 else ("MEDIUM" if jito_composite >= 45 else "LOW")

    def _alert(risk_level, asset, buffer, trending):
        trend_note = " Oracle confidence rising." if trending else ""
        if risk_level == "HIGH":
            return f"⚠️ HIGH RISK: {asset} is {buffer:.1f}% from liquidation.{trend_note} Add collateral immediately."
        if risk_level == "MEDIUM":
            return f"🟡 MEDIUM RISK: {asset} has {buffer:.1f}% buffer.{trend_note} Monitor closely."
        return f"✅ LOW RISK: {asset} is healthy ({buffer:.1f}% buffer).{trend_note}"

    positions = [
        {
            "wallet_address": DEMO_WALLET_ADDRESS,
            "protocol_name": "marginfi",
            "collateral_asset": "SOL/USD",
            "borrowed_asset": "USDC",
            "composite_risk_score": round(sol_composite, 2),
            "collateral_ratio_score": round(sol_coll_score, 2),
            "confidence_interval_score": round(sol_conf_score, 2),
            "volatility_trend_score": round(sol_trend_score, 2),
            "risk_level": sol_risk_level,
            "estimated_liquidation_price_drop_percent": round(sol_liq_buffer, 2),
            "current_confidence_ratio": round(sol_confidence_ratio, 6),
            "is_confidence_trending_upward": market_pulse > 0.4,
            "alert_message": _alert(sol_risk_level, "SOL/USD", sol_liq_buffer, market_pulse > 0.4),
        },
        {
            "wallet_address": DEMO_WALLET_ADDRESS,
            "protocol_name": "kamino",
            "collateral_asset": "ETH/USD",
            "borrowed_asset": "USDC",
            "composite_risk_score": round(eth_composite, 2),
            "collateral_ratio_score": round(eth_coll_score, 2),
            "confidence_interval_score": round(eth_conf_score, 2),
            "volatility_trend_score": round(eth_trend_score, 2),
            "risk_level": eth_risk_level,
            "estimated_liquidation_price_drop_percent": round(eth_liq_buffer, 2),
            "current_confidence_ratio": round(eth_confidence_ratio, 6),
            "is_confidence_trending_upward": market_pulse > 0.7,
            "alert_message": _alert(eth_risk_level, "ETH/USD", eth_liq_buffer, market_pulse > 0.7),
        },
        {
            "wallet_address": DEMO_WALLET_ADDRESS,
            "protocol_name": "marginfi",
            "collateral_asset": "JitoSOL/USD",
            "borrowed_asset": "USDC",
            "composite_risk_score": round(jito_composite, 2),
            "collateral_ratio_score": round(jito_coll_score, 2),
            "confidence_interval_score": round(jito_conf_score, 2),
            "volatility_trend_score": round(jito_trend_score, 2),
            "risk_level": jito_risk_level,
            "estimated_liquidation_price_drop_percent": round(jito_liq_buffer, 2),
            "current_confidence_ratio": round(jito_confidence_ratio, 6),
            "is_confidence_trending_upward": True,
            "alert_message": _alert(jito_risk_level, "JitoSOL/USD", jito_liq_buffer, True),
        },
    ]

    highest_score = max(p["composite_risk_score"] for p in positions)
    all_levels = [p["risk_level"] for p in positions]
    overall = "HIGH" if "HIGH" in all_levels else ("MEDIUM" if "MEDIUM" in all_levels else "LOW")

    return {
        "wallet_address": DEMO_WALLET_ADDRESS,
        "overall_risk_level": overall,
        "highest_risk_score": round(highest_score, 2),
        "position_count": len(positions),
        "positions": positions,
        "computed_at_timestamp": int(time.time()),
        "is_demo": True,
    }


def build_demo_feed_statuses() -> list[dict]:
    """Builds live-feeling Pyth feed status data for the demo."""
    pulse = _get_market_pulse()

    return [
        {
            "asset_symbol": "Crypto.SOL/USD",
            "normalized_price": round(136.40 + pulse * 8.0, 2),
            "confidence_ratio": round(0.0018 + pulse * 0.0032, 6),
            "risk_level_from_confidence": "MEDIUM" if pulse > 0.35 else "LOW",
            "publish_timestamp": int(time.time()),
            "is_feed_fresh": True,
        },
        {
            "asset_symbol": "Crypto.BTC/USD",
            "normalized_price": round(83210.0 + pulse * 1200.0, 2),
            "confidence_ratio": round(0.0004 + pulse * 0.0004, 6),
            "risk_level_from_confidence": "LOW",
            "publish_timestamp": int(time.time()),
            "is_feed_fresh": True,
        },
        {
            "asset_symbol": "Crypto.ETH/USD",
            "normalized_price": round(1842.0 + pulse * 95.0, 2),
            "confidence_ratio": round(0.0006 + pulse * 0.0006, 6),
            "risk_level_from_confidence": "LOW",
            "publish_timestamp": int(time.time()),
            "is_feed_fresh": True,
        },
        {
            "asset_symbol": "Crypto.JITOSOL/USD",
            "normalized_price": round(158.20 + pulse * 6.0, 2),
            "confidence_ratio": round(0.0042 + pulse * 0.0028, 6),
            "risk_level_from_confidence": "HIGH" if pulse > 0.6 else "MEDIUM",
            "publish_timestamp": int(time.time()),
            "is_feed_fresh": True,
        },
    ]


def build_demo_confidence_history(asset_ticker: str) -> list[dict]:
    """
    Builds 30-minute confidence ratio history for the chart.
    Simulates a realistic market event: calm → spike → partial recovery.
    """
    base_ratios = {
        "SOL":     0.0012,
        "BTC":     0.0004,
        "ETH":     0.0006,
        "JITOSOL": 0.0038,
    }
    base = base_ratios.get(asset_ticker.upper(), 0.0012)
    pulse = _get_market_pulse()
    now = int(time.time())

    history = []
    for minute_offset in range(30, 0, -1):
        timestamp = now - (minute_offset * 60)
        # Simulate a spike event at minute 15
        spike_factor = math.exp(-((minute_offset - 15) ** 2) / 20.0) * 3.5
        noise = math.sin(minute_offset * 1.3 + pulse * 5) * base * 0.2
        confidence_value = base + (spike_factor * base) + noise + (pulse * base * 1.5)
        history.append({
            "timestamp": timestamp,
            "confidence_ratio": round(max(confidence_value, base * 0.5), 6),
            "price": round(136.40 + math.sin(minute_offset * 0.4) * 3.0, 2),
        })

    return history
