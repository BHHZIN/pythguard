"""
Marginfi Public API Client.

Fetches real open lending/borrowing positions for any Solana wallet
using Marginfi's public REST API.

Correct endpoint (verified from Marginfi docs):
  GET https://marginfi.com/api/v2/marginfi-accounts?authority={wallet}

Falls back to the v1 endpoint if v2 is unavailable.
"""
from __future__ import annotations

import structlog
import httpx

logger = structlog.get_logger(__name__)

MARGINFI_API_V2_URL              = "https://marginfi.com/api/v2"
MARGINFI_API_V1_URL              = "https://marginfi.com/api"
MARGINFI_REQUEST_TIMEOUT_SECONDS = 12.0
MARGINFI_DEFAULT_LIQUIDATION_THRESHOLD = 0.80


async def fetch_marginfi_positions_for_wallet(
    wallet_address: str,
    http_client: httpx.AsyncClient,
) -> list[dict]:
    """
    Fetches open Marginfi positions for a wallet.
    Tries v2 API first, falls back to v1.

    Args:
        wallet_address: Base58 Solana wallet address
        http_client:    Shared async HTTP client

    Returns:
        List of position dicts, or empty list if none found.
    """
    # Try v2 first
    positions = await _fetch_from_marginfi_api(
        base_url=MARGINFI_API_V2_URL,
        wallet_address=wallet_address,
        http_client=http_client,
    )

    if positions is not None:
        return positions

    # Fallback to v1
    logger.debug("marginfi_v2_failed_trying_v1", wallet=wallet_address[:8])
    positions = await _fetch_from_marginfi_api(
        base_url=MARGINFI_API_V1_URL,
        wallet_address=wallet_address,
        http_client=http_client,
    )

    return positions or []


async def _fetch_from_marginfi_api(
    base_url: str,
    wallet_address: str,
    http_client: httpx.AsyncClient,
) -> list[dict] | None:
    """
    Attempts to fetch Marginfi accounts from a given API base URL.
    Returns None if the request fails (so caller can try fallback).
    """
    try:
        api_response = await http_client.get(
            f"{base_url}/marginfi-accounts",
            params={"authority": wallet_address},
            timeout=MARGINFI_REQUEST_TIMEOUT_SECONDS,
        )

        if api_response.status_code == 404:
            return []

        api_response.raise_for_status()
        response_data = api_response.json()

    except httpx.TimeoutException:
        logger.warning("marginfi_api_timeout", wallet=wallet_address[:8])
        return None
    except httpx.HTTPStatusError as http_error:
        logger.debug(
            "marginfi_api_http_error",
            status=http_error.response.status_code,
        )
        return None
    except Exception as unexpected_error:
        logger.error("marginfi_api_error", error=str(unexpected_error))
        return None

    raw_accounts = response_data if isinstance(response_data, list) else []

    if not raw_accounts:
        return []

    all_positions: list[dict] = []
    for raw_account in raw_accounts:
        positions = _extract_positions_from_marginfi_account(
            raw_account=raw_account,
            wallet_address=wallet_address,
        )
        all_positions.extend(positions)

    logger.info(
        "marginfi_positions_fetched",
        wallet=wallet_address[:8],
        count=len(all_positions),
    )
    return all_positions


def _extract_positions_from_marginfi_account(
    raw_account: dict,
    wallet_address: str,
) -> list[dict]:
    """
    Extracts positions from a Marginfi account API response.
    Handles both v1 and v2 response shapes.
    """
    balances = raw_account.get("balances", [])
    if not balances:
        return []

    deposit_balances = [
        b for b in balances
        if b.get("active") and b.get("side") in ("assets", "deposit", "supply")
    ]
    borrow_balances = [
        b for b in balances
        if b.get("active") and b.get("side") in ("liabilities", "borrow")
        and float(b.get("amount", b.get("usdValue", 0))) > 0
    ]

    if not borrow_balances:
        return []

    total_collateral_usd = sum(
        float(b.get("usdValue", b.get("marketValue", 0)))
        for b in deposit_balances
    )
    total_debt_usd = sum(
        float(b.get("usdValue", b.get("marketValue", 0)))
        for b in borrow_balances
    )

    if total_debt_usd <= 0:
        return []

    current_collateral_ratio = total_collateral_usd / total_debt_usd
    margin_to_liquidation = (
        (current_collateral_ratio - MARGINFI_DEFAULT_LIQUIDATION_THRESHOLD)
        / MARGINFI_DEFAULT_LIQUIDATION_THRESHOLD * 100.0
    )

    primary_collateral = max(
        deposit_balances,
        key=lambda b: float(b.get("usdValue", b.get("marketValue", 0))),
        default=None,
    )

    if primary_collateral is None:
        return []

    collateral_symbol = primary_collateral.get(
        "bankLabel",
        primary_collateral.get("mintSymbol", "UNKNOWN"),
    )
    collateral_amount = float(primary_collateral.get("amount", 0))

    positions = []
    for borrow in borrow_balances:
        borrowed_symbol = borrow.get(
            "bankLabel",
            borrow.get("mintSymbol", "UNKNOWN"),
        )
        borrowed_amount = float(borrow.get("amount", 0))

        positions.append({
            "owner_wallet_address":          wallet_address,
            "protocol_name":                 "marginfi",
            "collateral_asset_symbol":       collateral_symbol,
            "borrowed_asset_symbol":         borrowed_symbol,
            "collateral_amount":             collateral_amount,
            "borrowed_amount":               borrowed_amount,
            "liquidation_threshold_ratio":   MARGINFI_DEFAULT_LIQUIDATION_THRESHOLD,
            "current_collateral_ratio":      current_collateral_ratio,
            "margin_to_liquidation_percent": margin_to_liquidation,
        })

    return positions
