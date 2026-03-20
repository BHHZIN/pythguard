"""
Marginfi Position Adapter.

Tries the real Marginfi JS reader (port 8002) first.
Falls back to the Rust reader (port 8001) if JS reader is unavailable.

This gives us the best of both worlds:
- Real positions via official @mrgnlabs/marginfi-client-v2 SDK (JS)
- Fast fallback via Rust reader on any Solana RPC
"""
from __future__ import annotations

import structlog
import httpx

from app.config import settings

logger = structlog.get_logger(__name__)

MARGINFI_JS_READER_URL = "http://localhost:8002"


async def fetch_positions_for_wallet(
    wallet_address: str,
    http_client: httpx.AsyncClient,
) -> list[dict]:
    """
    Fetches open Marginfi positions for a wallet.

    Tries the JS SDK reader first (most accurate), then
    falls back to the Rust reader if JS is not running.

    Args:
        wallet_address: Base58 Solana wallet address
        http_client:    Shared async HTTP client from the request context

    Returns:
        List of position dicts matching the LendingPosition schema
    """
    # ── Try JS SDK reader first ─────────────────────────────
    try:
        js_reader_response = await http_client.get(
            f"{MARGINFI_JS_READER_URL}/positions/{wallet_address}",
            timeout=8.0,
        )
        js_reader_response.raise_for_status()
        payload = js_reader_response.json()
        positions = payload.get("open_positions", [])
        logger.info("positions_from_js_reader", wallet=wallet_address, count=len(positions))
        return positions

    except (httpx.ConnectError, httpx.TimeoutException):
        logger.info("js_reader_unavailable_using_rust_fallback", wallet=wallet_address)

    except httpx.HTTPStatusError as http_error:
        logger.warning("js_reader_error", status=http_error.response.status_code)

    # ── Fallback: Rust reader ───────────────────────────────
    rust_response = await http_client.get(
        f"{settings.rust_reader_base_url}/payload/{wallet_address}",
        timeout=settings.rust_reader_timeout_seconds,
    )
    rust_response.raise_for_status()
    payload = rust_response.json()
    positions = payload.get("open_positions", [])
    logger.info("positions_from_rust_reader", wallet=wallet_address, count=len(positions))
    return positions
