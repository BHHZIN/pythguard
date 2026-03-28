"""
Marginfi Position Adapter.

Priority order for fetching real positions:
  1. Marginfi JS reader (port 8002) — official SDK, most accurate
  2. Rust reader (port 8001) — fast on-chain RPC reader
  3. Marginfi Public REST API — works anywhere, no local services needed

This ensures the app always returns real positions in Watch/Live mode,
even when deployed on Railway without the Rust or JS readers running.
"""
from __future__ import annotations

import structlog
import httpx

from app.config import settings
from app.protocols.marginfi_public_api import (
    fetch_marginfi_positions_for_wallet,
)

logger = structlog.get_logger(__name__)

MARGINFI_JS_READER_URL = "http://localhost:8002"


async def fetch_positions_for_wallet(
    wallet_address: str,
    http_client: httpx.AsyncClient,
) -> list[dict]:
    """
    Fetches open Marginfi positions for a wallet.

    Tries three sources in order, returning the first that succeeds.

    Args:
        wallet_address: Base58 Solana wallet address
        http_client:    Shared async HTTP client

    Returns:
        List of position dicts, or empty list if wallet has no positions
    """
    # ── 1. Try JS SDK reader (most accurate) ────────────────
    try:
        js_response = await http_client.get(
            f"{MARGINFI_JS_READER_URL}/positions/{wallet_address}",
            timeout=6.0,
        )
        js_response.raise_for_status()
        positions = js_response.json().get("open_positions", [])
        logger.info("positions_from_js_reader", wallet=wallet_address, count=len(positions))
        return positions
    except (httpx.ConnectError, httpx.TimeoutException):
        logger.debug("js_reader_unavailable", wallet=wallet_address)
    except httpx.HTTPStatusError:
        logger.debug("js_reader_http_error", wallet=wallet_address)

    # ── 2. Try Rust reader ───────────────────────────────────
    try:
        rust_response = await http_client.get(
            f"{settings.rust_reader_base_url}/payload/{wallet_address}",
            timeout=settings.rust_reader_timeout_seconds,
        )
        rust_response.raise_for_status()
        positions = rust_response.json().get("open_positions", [])
        logger.info("positions_from_rust_reader", wallet=wallet_address, count=len(positions))
        return positions
    except (httpx.ConnectError, httpx.TimeoutException):
        logger.debug("rust_reader_unavailable", wallet=wallet_address)
    except httpx.HTTPStatusError:
        logger.debug("rust_reader_http_error", wallet=wallet_address)

    # ── 3. Fallback: Marginfi public REST API ────────────────
    logger.info("using_marginfi_public_api_fallback", wallet=wallet_address)
    positions = await fetch_marginfi_positions_for_wallet(
        wallet_address=wallet_address,
        http_client=http_client,
    )
    return positions
