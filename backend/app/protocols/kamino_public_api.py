"""
Kamino Public API Client.

Fetches real open lending/borrowing obligations for any Solana wallet
using Kamino's official public REST API — no SDK or RPC required.

API docs: https://api.kamino.finance/documentation
Endpoint: GET /kamino-market/{market}/users/{wallet}/obligations

Kamino main markets on Solana Mainnet:
  - Main market:  7u3HeHxYDLhnCoErrtycNokbQYbWGzLs6JSDqGAv5PfF
  - JLP market:   DxXdAyU3kCjnyggvHmY5nAwg5cRbbmdyX3npfDMjjMek
  - Altcoin:      ByYiZxp8QrdN9qbdtaAiePN8AAr3qvTPppNJDpf5DVJ5
"""
from __future__ import annotations

import structlog
import httpx

logger = structlog.get_logger(__name__)

KAMINO_API_BASE_URL             = "https://api.kamino.finance"
KAMINO_REQUEST_TIMEOUT_SECONDS  = 12.0

# All known Kamino lending markets on Solana Mainnet
# We query all of them to find any position a wallet might have
KAMINO_LENDING_MARKETS = [
    "7u3HeHxYDLhnCoErrtycNokbQYbWGzLs6JSDqGAv5PfF",  # Main market
    "DxXdAyU3kCjnyggvHmY5nAwg5cRbbmdyX3npfDMjjMek",  # JLP market
    "ByYiZxp8QrdN9qbdtaAiePN8AAr3qvTPppNJDpf5DVJ5",  # Altcoin market
]

# Kamino standard liquidation LTV by market (approximate)
KAMINO_DEFAULT_LIQUIDATION_THRESHOLD = 0.80


async def fetch_kamino_positions_for_wallet(
    wallet_address: str,
    http_client: httpx.AsyncClient,
) -> list[dict]:
    """
    Fetches open Kamino lending/borrowing positions for a wallet
    across all known Kamino markets.

    Args:
        wallet_address: Base58 Solana wallet address
        http_client:    Shared async HTTP client

    Returns:
        List of position dicts matching the LendingPosition schema.
        Empty list if the wallet has no Kamino positions.
    """
    all_positions: list[dict] = []

    for market_address in KAMINO_LENDING_MARKETS:
        market_positions = await _fetch_positions_for_market(
            wallet_address=wallet_address,
            market_address=market_address,
            http_client=http_client,
        )
        all_positions.extend(market_positions)

    logger.info(
        "kamino_positions_fetched",
        wallet=wallet_address,
        total_count=len(all_positions),
    )
    return all_positions


async def _fetch_positions_for_market(
    wallet_address: str,
    market_address: str,
    http_client: httpx.AsyncClient,
) -> list[dict]:
    """
    Fetches obligations for a wallet in a single Kamino market.
    Returns empty list on any error so other markets are still checked.
    """
    endpoint_url = (
        f"{KAMINO_API_BASE_URL}/kamino-market"
        f"/{market_address}/users/{wallet_address}/obligations"
    )

    try:
        api_response = await http_client.get(
            endpoint_url,
            timeout=KAMINO_REQUEST_TIMEOUT_SECONDS,
        )

        # 404 means wallet has no position in this market — not an error
        if api_response.status_code == 404:
            return []

        api_response.raise_for_status()
        obligations_data = api_response.json()

    except httpx.TimeoutException:
        logger.warning(
            "kamino_api_timeout",
            market=market_address[:8],
            wallet=wallet_address[:8],
        )
        return []
    except httpx.HTTPStatusError as http_error:
        logger.debug(
            "kamino_api_http_error",
            status=http_error.response.status_code,
            market=market_address[:8],
        )
        return []
    except Exception as unexpected_error:
        logger.error(
            "kamino_api_unexpected_error",
            error=str(unexpected_error),
            market=market_address[:8],
        )
        return []

    # Kamino returns a list of obligation objects
    raw_obligations = obligations_data if isinstance(obligations_data, list) else []

    if not raw_obligations:
        return []

    extracted_positions: list[dict] = []

    for raw_obligation in raw_obligations:
        positions = _extract_positions_from_obligation(
            raw_obligation=raw_obligation,
            wallet_address=wallet_address,
        )
        extracted_positions.extend(positions)

    return extracted_positions


def _extract_positions_from_obligation(
    raw_obligation: dict,
    wallet_address: str,
) -> list[dict]:
    """
    Extracts lending/borrowing positions from a Kamino obligation object.

    Kamino obligation structure:
    {
      "deposits": [{"mintSymbol": "SOL", "amount": "10.5", "marketValueRefreshed": "1450.0"}],
      "borrows":  [{"mintSymbol": "USDC", "amount": "800.0", "marketValueRefreshed": "800.0"}],
      "loanToValue": "0.55",
      "maxLtvPct": "0.65"
    }
    """
    deposits = raw_obligation.get("deposits", [])
    borrows  = raw_obligation.get("borrows", [])

    # Skip obligations with no borrows — deposit-only is not at liquidation risk
    active_borrows = [
        borrow for borrow in borrows
        if float(borrow.get("amount", 0)) > 0
    ]

    if not active_borrows:
        return []

    # Total values in USD
    total_collateral_usd = sum(
        float(deposit.get("marketValueRefreshed", deposit.get("marketValue", 0)))
        for deposit in deposits
    )
    total_debt_usd = sum(
        float(borrow.get("marketValueRefreshed", borrow.get("marketValue", 0)))
        for borrow in active_borrows
    )

    if total_debt_usd <= 0:
        return []

    current_collateral_ratio = total_collateral_usd / total_debt_usd

    # Use Kamino's reported max LTV as the liquidation threshold
    liquidation_threshold = float(
        raw_obligation.get("maxLtvPct", KAMINO_DEFAULT_LIQUIDATION_THRESHOLD)
    )
    # Kamino sometimes returns this as a percentage (65) instead of decimal (0.65)
    if liquidation_threshold > 1.0:
        liquidation_threshold = liquidation_threshold / 100.0

    margin_to_liquidation = (
        (current_collateral_ratio - liquidation_threshold)
        / liquidation_threshold * 100.0
    )

    # Find the largest deposit as primary collateral
    primary_collateral = max(
        deposits,
        key=lambda deposit: float(
            deposit.get("marketValueRefreshed", deposit.get("marketValue", 0))
        ),
        default=None,
    )

    if primary_collateral is None:
        return []

    collateral_symbol = primary_collateral.get("mintSymbol", "UNKNOWN")
    collateral_amount = float(primary_collateral.get("amount", 0))

    extracted_positions = []

    for borrow in active_borrows:
        borrowed_symbol = borrow.get("mintSymbol", "UNKNOWN")
        borrowed_amount = float(borrow.get("amount", 0))

        extracted_positions.append({
            "owner_wallet_address":          wallet_address,
            "protocol_name":                 "kamino",
            "collateral_asset_symbol":       collateral_symbol,
            "borrowed_asset_symbol":         borrowed_symbol,
            "collateral_amount":             collateral_amount,
            "borrowed_amount":               borrowed_amount,
            "liquidation_threshold_ratio":   liquidation_threshold,
            "current_collateral_ratio":      current_collateral_ratio,
            "margin_to_liquidation_percent": margin_to_liquidation,
        })

    return extracted_positions
