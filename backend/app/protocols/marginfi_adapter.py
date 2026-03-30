"""
Position Adapter — Marginfi + Kamino.

Fetches open lending/borrowing positions from BOTH protocols
for any Solana wallet, combining results into one list.

Priority chain per protocol:
  1. JS SDK reader (local, port 8002) — most accurate
  2. Rust reader (local, port 8001) — fast RPC
  3. Public REST API — works on Railway without local services

Kamino and Marginfi are fetched in parallel for speed.
"""
from __future__ import annotations

import asyncio
import structlog
import httpx

from app.config import settings
from app.protocols.marginfi_public_api import fetch_marginfi_positions_for_wallet
from app.protocols.kamino_public_api import fetch_kamino_positions_for_wallet

logger = structlog.get_logger(__name__)

MARGINFI_JS_READER_URL = "http://localhost:8002"


async def fetch_positions_for_wallet(
    wallet_address: str,
    http_client: httpx.AsyncClient,
) -> list[dict]:
    """
    Fetches ALL open positions for a wallet across Marginfi and Kamino.

    Runs both protocol fetches in parallel.
    Returns combined list sorted by risk (highest collateral ratio first).

    Args:
        wallet_address: Base58 Solana wallet address
        http_client:    Shared async HTTP client
    """
    # Run Marginfi and Kamino fetches in parallel
    marginfi_positions_task = _fetch_marginfi_with_fallback(
        wallet_address=wallet_address,
        http_client=http_client,
    )
    kamino_positions_task = fetch_kamino_positions_for_wallet(
        wallet_address=wallet_address,
        http_client=http_client,
    )

    marginfi_positions, kamino_positions = await asyncio.gather(
        marginfi_positions_task,
        kamino_positions_task,
        return_exceptions=True,
    )

    # Handle exceptions from either fetch gracefully
    if isinstance(marginfi_positions, Exception):
        logger.warning(
            "marginfi_fetch_exception",
            error=str(marginfi_positions),
            wallet=wallet_address[:8],
        )
        marginfi_positions = []

    if isinstance(kamino_positions, Exception):
        logger.warning(
            "kamino_fetch_exception",
            error=str(kamino_positions),
            wallet=wallet_address[:8],
        )
        kamino_positions = []

    all_positions = list(marginfi_positions) + list(kamino_positions)

    logger.info(
        "all_positions_fetched",
        wallet=wallet_address[:8],
        marginfi_count=len(marginfi_positions),
        kamino_count=len(kamino_positions),
        total=len(all_positions),
    )

    return all_positions


async def _fetch_marginfi_with_fallback(
    wallet_address: str,
    http_client: httpx.AsyncClient,
) -> list[dict]:
    """
    Fetches Marginfi positions with three-tier fallback:
      1. JS SDK reader (local)
      2. Rust reader (local)
      3. Marginfi public REST API
    """
    # ── 1. JS SDK reader ────────────────────────────────────
    try:
        js_response = await http_client.get(
            f"{MARGINFI_JS_READER_URL}/positions/{wallet_address}",
            timeout=6.0,
        )
        js_response.raise_for_status()
        positions = js_response.json().get("open_positions", [])
        logger.debug(
            "marginfi_from_js_reader",
            wallet=wallet_address[:8],
            count=len(positions),
        )
        return positions
    except (httpx.ConnectError, httpx.TimeoutException):
        pass
    except httpx.HTTPStatusError:
        pass

    # ── 2. Rust reader ───────────────────────────────────────
    try:
        rust_response = await http_client.get(
            f"{settings.rust_reader_base_url}/payload/{wallet_address}",
            timeout=settings.rust_reader_timeout_seconds,
        )
        rust_response.raise_for_status()
        positions = rust_response.json().get("open_positions", [])
        logger.debug(
            "marginfi_from_rust_reader",
            wallet=wallet_address[:8],
            count=len(positions),
        )
        return positions
    except (httpx.ConnectError, httpx.TimeoutException):
        pass
    except httpx.HTTPStatusError:
        pass

    # ── 3. Public REST API ───────────────────────────────────
    logger.debug("marginfi_using_public_api", wallet=wallet_address[:8])
    return await fetch_marginfi_positions_for_wallet(
        wallet_address=wallet_address,
        http_client=http_client,
    )
