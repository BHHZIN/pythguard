/**
 * PythGuard — Marginfi Position Fetcher
 *
 * Uses the official @mrgnlabs/marginfi-client-v2 SDK to fetch
 * real open lending/borrowing positions for any Solana wallet.
 *
 * This replaces the placeholder account-byte-parsing in the Rust reader.
 * Run as a standalone Node.js service on port 8002, or import directly.
 *
 * Usage:
 *   npm install
 *   SOLANA_RPC_URL=https://api.mainnet-beta.solana.com node marginfi_reader.js
 *
 * Exposes: GET /positions/:walletAddress
 */

import express from "express";
import {
  MarginfiClient,
  getConfig,
  Environment,
} from "@mrgnlabs/marginfi-client-v2";
import { Connection, PublicKey } from "@solana/web3.js";

const SOLANA_RPC_URL = process.env.SOLANA_RPC_URL || "https://api.mainnet-beta.solana.com";
const SERVER_PORT    = parseInt(process.env.MARGINFI_READER_PORT || "8002");

// ─────────────────────────────────────────────────────────────
// Marginfi client singleton
// ─────────────────────────────────────────────────────────────

let marginfiClientInstance = null;

/**
 * Lazily initializes and caches the Marginfi client.
 * Read-only connection — no wallet signing needed.
 *
 * @returns {Promise<MarginfiClient>}
 */
async function getMarginfiClient() {
  if (marginfiClientInstance) return marginfiClientInstance;

  const solanaConnection = new Connection(SOLANA_RPC_URL, "confirmed");
  const marginfiConfig   = getConfig(Environment.PRODUCTION);

  // Read-only mode: no wallet required for fetching positions
  marginfiClientInstance = await MarginfiClient.fetch(
    marginfiConfig,
    null, // no wallet — read-only
    solanaConnection,
  );

  console.log("[marginfi] Client initialized");
  return marginfiClientInstance;
}

// ─────────────────────────────────────────────────────────────
// Position fetcher
// ─────────────────────────────────────────────────────────────

/**
 * Fetches all open Marginfi lending/borrowing positions for a wallet.
 *
 * @param {string} walletAddressString  Base58 Solana wallet address
 * @returns {Promise<Array>}            Array of LendingPosition-shaped objects
 */
async function fetchMarginfiPositions(walletAddressString) {
  const marginfiClient = await getMarginfiClient();
  const ownerPublicKey = new PublicKey(walletAddressString);

  // Fetch all Marginfi accounts owned by this wallet
  const marginfiAccounts = await marginfiClient.getMarginfiAccountsForAuthority(
    ownerPublicKey
  );

  if (marginfiAccounts.length === 0) {
    return [];
  }

  const openPositions = [];

  for (const marginfiAccount of marginfiAccounts) {
    for (const activeBalance of marginfiAccount.activeBalances) {
      // Skip empty balances
      if (!activeBalance || activeBalance.active === false) continue;

      const bankMetadata   = marginfiClient.getBankByPk(activeBalance.bankPk);
      if (!bankMetadata) continue;

      const assetSymbol    = bankMetadata.tokenSymbol || "UNKNOWN";
      const isLendPosition = activeBalance.isLendingPosition();
      const isBorrowPosition = activeBalance.isBorrowingPosition();

      // We only care about borrow positions (the ones at liquidation risk)
      if (!isBorrowPosition) continue;

      const borrowedAmountUi  = activeBalance.getQuantityUi(bankMetadata).borrow.toNumber();
      const depositedAmountUi = marginfiAccount.computeHealthComponentsWithoutBias(
        "Maint"
      ).assets.toNumber();

      const liquidationThreshold = bankMetadata.config.assetWeightMaint.toNumber();

      // Current collateral-to-debt ratio across the whole account
      const healthComponents = marginfiAccount.computeHealthComponents("Maint");
      const currentCollateralRatio =
        healthComponents.liabilities.isZero()
          ? 999
          : healthComponents.assets.div(healthComponents.liabilities).toNumber();

      const marginToLiquidation =
        ((currentCollateralRatio - liquidationThreshold) / liquidationThreshold) * 100;

      openPositions.push({
        owner_wallet_address:          walletAddressString,
        protocol_name:                 "marginfi",
        collateral_asset_symbol:       assetSymbol,
        borrowed_asset_symbol:         "USDC",  // Most borrows are against stablecoins
        collateral_amount:             depositedAmountUi,
        borrowed_amount:               borrowedAmountUi,
        liquidation_threshold_ratio:   liquidationThreshold,
        current_collateral_ratio:      currentCollateralRatio,
        margin_to_liquidation_percent: marginToLiquidation,
      });
    }
  }

  return openPositions;
}

// ─────────────────────────────────────────────────────────────
// Express HTTP server
// ─────────────────────────────────────────────────────────────

const expressApp = express();
expressApp.use(express.json());

/** GET /positions/:walletAddress */
expressApp.get("/positions/:walletAddress", async (req, res) => {
  const { walletAddress } = req.params;

  // Guard: validate base58 wallet address length
  if (!walletAddress || walletAddress.length < 32 || walletAddress.length > 44) {
    return res.status(400).json({ error: "Invalid wallet address" });
  }

  try {
    const openPositions = await fetchMarginfiPositions(walletAddress);
    return res.json({
      wallet_address:  walletAddress,
      open_positions:  openPositions,
      fetched_at:      Math.floor(Date.now() / 1000),
    });
  } catch (fetchError) {
    console.error("[marginfi] Fetch error:", fetchError.message);
    return res.status(500).json({ error: fetchError.message });
  }
});

/** GET /health */
expressApp.get("/health", (_req, res) => res.json({ status: "ok" }));

expressApp.listen(SERVER_PORT, () => {
  console.log(`[marginfi-reader] Listening on port ${SERVER_PORT}`);
  console.log(`[marginfi-reader] RPC: ${SOLANA_RPC_URL}`);
});
