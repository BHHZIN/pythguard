"""
Position Adapter — Marginfi + Kamino.

Priority chain:
  1. Unified JS reader (port 8002) — both Marginfi + Kamino via official SDKs
  2. Rust reader (port 8001)       — Marginfi only via RPC
  3. Public REST APIs              — Marginfi v2/v1 + Kamino REST

The JS reader is the most reliable for Kamino since the REST API
doesn't have a simple public user-obligations endpoint.
"""
from __future__ import annotations
import os

import asyncio
import structlog
import httpx

from app.config import settings
from app.protocols.marginfi_public_api import fetch_marginfi_positions_for_wallet
from app.protocols.kamino_public_api import fetch_kamino_positions_for_wallet

logger = structlog.get_logger(__name__)
POSITION_READER_JS_URL = os.getenv(
    "POSITION_READER_URL", "http://localhost:8002")


async def fetch_positions_for_wallet(
    wallet_address: str,
    http_client: httpx.AsyncClient,
) -> list[dict]:
    """
    Fetches ALL open lending/borrowing positions for a wallet
    across Marginfi and Kamino.

    Tries the unified JS reader first (handles both protocols).
    Falls back to separate public API calls if JS reader unavailable.
    """
    # ── 1. Unified JS reader (Marginfi + Kamino via official SDKs) ──
    try:
        js_response = await http_client.get(
            f"{POSITION_READER_JS_URL}/positions/{wallet_address}",
            timeout=25.0,  # SDK calls take longer than REST
        )
        js_response.raise_for_status()
        payload = js_response.json()
        all_positions = payload.get("open_positions", [])

        logger.info(
            "positions_from_js_reader",
            wallet=wallet_address[:8],
            marginfi=payload.get("marginfi_count", 0),
            kamino=payload.get("kamino_count", 0),
            total=len(all_positions),
        )
        return all_positions

    except (httpx.ConnectError, httpx.TimeoutException):
        logger.info("js_reader_unavailable_using_public_apis",
                    wallet=wallet_address[:8])
    except httpx.HTTPStatusError as http_error:
        logger.warning("js_reader_http_error",
                       status=http_error.response.status_code)

    # ── 2. Rust reader fallback (Marginfi only) ─────────────────────
    try:
        rust_response = await http_client.get(
            f"{settings.rust_reader_base_url}/payload/{wallet_address}",
            timeout=settings.rust_reader_timeout_seconds,
        )
        rust_response.raise_for_status()
        rust_positions = rust_response.json().get("open_positions", [])

        if rust_positions:
            logger.info(
                "positions_from_rust_reader",
                wallet=wallet_address[:8],
                count=len(rust_positions),
            )
            # Still fetch Kamino separately since Rust only covers Marginfi
            kamino_positions = await fetch_kamino_positions_for_wallet(
                wallet_address=wallet_address,
                http_client=http_client,
            )
            return rust_positions + kamino_positions

    except (httpx.ConnectError, httpx.TimeoutException):
        logger.debug("rust_reader_unavailable", wallet=wallet_address[:8])
    except httpx.HTTPStatusError:
        logger.debug("rust_reader_http_error", wallet=wallet_address[:8])

    # ── 3. Public REST APIs (Marginfi + Kamino in parallel) ─────────
    logger.info("using_public_apis_fallback", wallet=wallet_address[:8])

    marginfi_task = fetch_marginfi_positions_for_wallet(
        wallet_address=wallet_address,
        http_client=http_client,
    )
    kamino_task = fetch_kamino_positions_for_wallet(
        wallet_address=wallet_address,
        http_client=http_client,
    )

    marginfi_result, kamino_result = await asyncio.gather(
        marginfi_task,
        kamino_task,
        return_exceptions=True,
    )

    marginfi_positions = marginfi_result if isinstance(
        marginfi_result, list) else []
    kamino_positions = kamino_result if isinstance(kamino_result, list) else []

    all_positions = marginfi_positions + kamino_positions

    logger.info(
        "positions_from_public_apis",
        wallet=wallet_address[:8],
        marginfi=len(marginfi_positions),
        kamino=len(kamino_positions),
        total=len(all_positions),
    )

    return all_positions
