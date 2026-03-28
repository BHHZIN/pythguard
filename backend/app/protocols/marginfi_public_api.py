"""
Marginfi Public API Client.

Fetches real open lending/borrowing positions for any Solana wallet
using Marginfi's public REST API — no Rust reader required.

This is the primary fallback when the Rust reader and JS reader
are not running, which is the case in the hosted Railway deployment.

Marginfi public API: https://marginfi.com/api/marginfi-accounts
"""
from __future__ import annotations

import structlog
import httpx

logger = structlog.get_logger(__name__)

MARGINFI_API_BASE_URL        = "https://marginfi.com/api"
MARGINFI_REQUEST_TIMEOUT_SECONDS = 12.0

# Marginfi standard liquidation threshold
MARGINFI_DEFAULT_LIQUIDATION_THRESHOLD = 0.80


async def fetch_marginfi_positions_for_wallet(
    wallet_address: str,
    http_client: httpx.AsyncClient,
) -> list[dict]:
    """
    Fetches open Marginfi positions for a wallet via the public REST API.

    Returns a list of position dicts matching the LendingPosition schema.
    Returns an empty list if the wallet has no Marginfi positions.

    Args:
        wallet_address: Base58 Solana wallet address
        http_client:    Shared async HTTP client
    """
    try:
        api_response = await http_client.get(
            f"{MARGINFI_API_BASE_URL}/marginfi-accounts",
            params={"authority": wallet_address},
            timeout=MARGINFI_REQUEST_TIMEOUT_SECONDS,
        )
        api_response.raise_for_status()
        response_data = api_response.json()

    except httpx.TimeoutException:
        logger.warning("marginfi_api_timeout", wallet=wallet_address)
        return []
    except httpx.HTTPStatusError as http_error:
        logger.warning(
            "marginfi_api_error",
            status=http_error.response.status_code,
            wallet=wallet_address,
        )
        return []
    except Exception as unexpected_error:
        logger.error(
            "marginfi_api_unexpected_error",
            error=str(unexpected_error),
            wallet=wallet_address,
        )
        return []

    raw_accounts = response_data if isinstance(response_data, list) else []

    if not raw_accounts:
        logger.info("no_marginfi_accounts", wallet=wallet_address)
        return []

    open_positions: list[dict] = []

    for raw_account in raw_accounts:
        positions_from_account = _extract_positions_from_account(
            raw_account=raw_account,
            wallet_address=wallet_address,
        )
        open_positions.extend(positions_from_account)

    logger.info(
        "marginfi_positions_fetched",
        wallet=wallet_address,
        count=len(open_positions),
    )
    return open_positions


def _extract_positions_from_account(
    raw_account: dict,
    wallet_address: str,
) -> list[dict]:
    """
    Extracts lending/borrowing positions from a raw Marginfi account object.
    Handles the nested structure of the Marginfi API response.
    """
    extracted_positions: list[dict] = []

    balances = raw_account.get("balances", [])
    if not balances:
        return []

    # Separate deposit (collateral) and borrow balances
    deposit_balances = [
        balance for balance in balances
        if balance.get("active") and balance.get("side") == "assets"
    ]
    borrow_balances = [
        balance for balance in balances
        if balance.get("active") and balance.get("side") == "liabilities"
    ]

    # Guard: need at least one borrow to be at liquidation risk
    if not borrow_balances:
        return []

    # Compute total collateral and debt values in USD
    total_collateral_usd = sum(
        float(balance.get("usdValue", 0)) for balance in deposit_balances
    )
    total_debt_usd = sum(
        float(balance.get("usdValue", 0)) for balance in borrow_balances
    )

    # Guard: avoid division by zero
    if total_debt_usd <= 0:
        return []

    current_collateral_ratio = total_collateral_usd / total_debt_usd
    margin_to_liquidation = (
        (current_collateral_ratio - MARGINFI_DEFAULT_LIQUIDATION_THRESHOLD)
        / MARGINFI_DEFAULT_LIQUIDATION_THRESHOLD
        * 100.0
    )

    # Build one position per borrow balance (each is a separate risk event)
    for borrow_balance in borrow_balances:
        borrowed_asset_symbol = borrow_balance.get("bankLabel", "UNKNOWN")
        borrowed_amount       = float(borrow_balance.get("amount", 0))

        # Find the matching collateral for this borrow
        # (use the largest deposit as the primary collateral)
        primary_collateral = max(
            deposit_balances,
            key=lambda deposit: float(deposit.get("usdValue", 0)),
            default=None,
        )

        if primary_collateral is None:
            continue

        collateral_asset_symbol = primary_collateral.get("bankLabel", "UNKNOWN")
        collateral_amount       = float(primary_collateral.get("amount", 0))

        extracted_positions.append({
            "owner_wallet_address":          wallet_address,
            "protocol_name":                 "marginfi",
            "collateral_asset_symbol":       collateral_asset_symbol,
            "borrowed_asset_symbol":         borrowed_asset_symbol,
            "collateral_amount":             collateral_amount,
            "borrowed_amount":               borrowed_amount,
            "liquidation_threshold_ratio":   MARGINFI_DEFAULT_LIQUIDATION_THRESHOLD,
            "current_collateral_ratio":      current_collateral_ratio,
            "margin_to_liquidation_percent": margin_to_liquidation,
        })

    return extracted_positions
