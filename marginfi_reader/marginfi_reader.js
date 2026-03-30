/**
 * PythGuard Position Reader — Marginfi + Kamino
 *
 * Reads open lending/borrowing positions from both protocols
 * for any Solana wallet. Exposes a single unified endpoint:
 *
 *   GET /positions/:walletAddress
 *
 * Uses official SDKs:
 *   - @mrgnlabs/marginfi-client-v2  for Marginfi
 *   - @kamino-finance/klend-sdk     for Kamino
 *
 * Port: 8002 (configured via POSITION_READER_PORT env var)
 */

import express from "express";
import { Connection, PublicKey } from "@solana/web3.js";

const SOLANA_RPC_URL   = process.env.SOLANA_RPC_URL || "https://api.mainnet-beta.solana.com";
const SERVER_PORT      = parseInt(process.env.POSITION_READER_PORT || process.env.PORT || "8002");
const REQUEST_TIMEOUT  = 20_000;

// Kamino main lending markets on Solana Mainnet
const KAMINO_LENDING_MARKETS = [
  "7u3HeHxYDLhnCoErrtycNokbQYbWGzLs6JSDqGAv5PfF", // Main market
  "DxXdAyU3kCjnyggvHmY5nAwg5cRbbmdyX3npfDMjjMek", // JLP market
  "ByYiZxp8QrdN9qbdtaAiePN8AAr3qvTPppNJDpf5DVJ5", // Altcoin market
];

const KAMINO_DEFAULT_LIQUIDATION_THRESHOLD = 0.80;
const MARGINFI_DEFAULT_LIQUIDATION_THRESHOLD = 0.80;

// ─────────────────────────────────────────────────────────────
// Kamino positions reader
// ─────────────────────────────────────────────────────────────

/**
 * Fetches Kamino lending/borrowing positions for a wallet
 * across all known markets using the official klend-sdk.
 *
 * @param {string} walletAddressString
 * @returns {Promise<Array>}
 */
async function fetchKaminoPositions(walletAddressString) {
  const allPositions = [];

  // Dynamically import klend-sdk (handles ESM/CJS quirks)
  let KaminoMarket, VanillaObligation, PROGRAM_ID;
  try {
    const klendSdk = await import("@kamino-finance/klend-sdk");
    KaminoMarket     = klendSdk.KaminoMarket;
    VanillaObligation = klendSdk.VanillaObligation;
    PROGRAM_ID       = klendSdk.PROGRAM_ID;
  } catch (importError) {
    console.error("[kamino] SDK import failed:", importError.message);
    return [];
  }

  const connection   = new Connection(SOLANA_RPC_URL, "confirmed");
  const walletPubkey = new PublicKey(walletAddressString);

  // Query each market in parallel
  const marketPromises = KAMINO_LENDING_MARKETS.map(async (marketAddress) => {
    try {
      const market = await KaminoMarket.load(
        connection,
        new PublicKey(marketAddress),
        400 // recent slot duration ms
      );

      const obligation = await market.getObligationByWallet(
        walletPubkey,
        new VanillaObligation(PROGRAM_ID)
      );

      if (!obligation) return [];

      // Extract borrows and deposits from the obligation
      const deposits = [];
      const borrows  = [];

      for (const [reservePubkey, depositAmount] of obligation.deposits) {
        const reserve = market.getReserveByAddress(reservePubkey);
        if (!reserve) continue;
        const symbol   = reserve.stats?.symbol || reserve.config?.tokenInfo?.symbol || "UNKNOWN";
        const usdValue = depositAmount.toNumber() * (reserve.stats?.lastPrice || 0);
        deposits.push({ symbol, amount: depositAmount.toNumber(), usdValue });
      }

      for (const [reservePubkey, borrowAmount] of obligation.borrows) {
        const reserve = market.getReserveByAddress(reservePubkey);
        if (!reserve) continue;
        const symbol   = reserve.stats?.symbol || reserve.config?.tokenInfo?.symbol || "UNKNOWN";
        const usdValue = borrowAmount.toNumber() * (reserve.stats?.lastPrice || 0);
        borrows.push({ symbol, amount: borrowAmount.toNumber(), usdValue });
      }

      // Skip deposit-only positions (no liquidation risk)
      if (borrows.length === 0) return [];

      const totalCollateralUsd = deposits.reduce((sum, d) => sum + d.usdValue, 0);
      const totalDebtUsd       = borrows.reduce((sum, b) => sum + b.usdValue, 0);

      if (totalDebtUsd <= 0) return [];

      const collateralRatio     = totalCollateralUsd / totalDebtUsd;
      const liquidationLtv      = parseFloat(obligation.stats?.liquidationLtv || KAMINO_DEFAULT_LIQUIDATION_THRESHOLD);
      const marginToLiquidation = ((collateralRatio - liquidationLtv) / liquidationLtv) * 100;

      // Find largest collateral asset
      const primaryCollateral = deposits.sort((depA, depB) => depB.usdValue - depA.usdValue)[0];

      // One position entry per borrow
      return borrows.map((borrow) => ({
        owner_wallet_address:          walletAddressString,
        protocol_name:                 "kamino",
        collateral_asset_symbol:       primaryCollateral.symbol,
        borrowed_asset_symbol:         borrow.symbol,
        collateral_amount:             primaryCollateral.amount,
        borrowed_amount:               borrow.amount,
        liquidation_threshold_ratio:   liquidationLtv,
        current_collateral_ratio:      collateralRatio,
        margin_to_liquidation_percent: marginToLiquidation,
      }));

    } catch (marketError) {
      // No position in this market — expected for most wallets
      if (!marketError.message?.includes("null") && !marketError.message?.includes("not found")) {
        console.error(`[kamino] Market ${marketAddress.slice(0, 8)} error:`, marketError.message);
      }
      return [];
    }
  });

  const marketResults = await Promise.allSettled(marketPromises);

  for (const result of marketResults) {
    if (result.status === "fulfilled" && Array.isArray(result.value)) {
      allPositions.push(...result.value);
    }
  }

  console.log(`[kamino] Found ${allPositions.length} positions for ${walletAddressString.slice(0, 8)}…`);
  return allPositions;
}

// ─────────────────────────────────────────────────────────────
// Marginfi positions reader
// ─────────────────────────────────────────────────────────────

/**
 * Fetches Marginfi lending/borrowing positions for a wallet
 * using the official marginfi-client-v2 SDK.
 *
 * @param {string} walletAddressString
 * @returns {Promise<Array>}
 */
async function fetchMarginfiPositions(walletAddressString) {
  let MarginfiClient, getConfig, Environment;
  try {
    const marginfiSdk = await import("@mrgnlabs/marginfi-client-v2");
    MarginfiClient = marginfiSdk.MarginfiClient;
    getConfig      = marginfiSdk.getConfig;
    Environment    = marginfiSdk.Environment;
  } catch (importError) {
    console.error("[marginfi] SDK import failed:", importError.message);
    return [];
  }

  try {
    const connection     = new Connection(SOLANA_RPC_URL, "confirmed");
    const marginfiConfig = getConfig(Environment.PRODUCTION);
    const marginfiClient = await MarginfiClient.fetch(marginfiConfig, null, connection);
    const ownerPubkey    = new PublicKey(walletAddressString);

    const marginfiAccounts = await marginfiClient.getMarginfiAccountsForAuthority(ownerPubkey);

    if (!marginfiAccounts || marginfiAccounts.length === 0) {
      return [];
    }

    const allPositions = [];

    for (const account of marginfiAccounts) {
      const activeBalances = account.activeBalances || [];
      const borrowBalances = activeBalances.filter((b) => b.isBorrowingPosition?.());

      if (borrowBalances.length === 0) continue;

      const healthComponents    = account.computeHealthComponents?.("Maint");
      const totalCollateralUsd  = healthComponents?.assets?.toNumber() || 0;
      const totalDebtUsd        = healthComponents?.liabilities?.toNumber() || 0;

      if (totalDebtUsd <= 0) continue;

      const collateralRatio     = totalCollateralUsd / totalDebtUsd;
      const liquidationThreshold = MARGINFI_DEFAULT_LIQUIDATION_THRESHOLD;
      const marginToLiquidation  = ((collateralRatio - liquidationThreshold) / liquidationThreshold) * 100;

      // Find primary collateral (largest deposit)
      const depositBalances = activeBalances.filter((b) => b.isLendingPosition?.());
      const primaryDeposit  = depositBalances.sort((depA, depB) => {
        const aValue = depA.getQuantityUi?.()?.assets?.toNumber() || 0;
        const bValue = depB.getQuantityUi?.()?.assets?.toNumber() || 0;
        return bValue - aValue;
      })[0];

      const collateralSymbol = primaryDeposit
        ? (account.client?.getBankByPk(primaryDeposit.bankPk)?.tokenSymbol || "UNKNOWN")
        : "UNKNOWN";
      const collateralAmount = primaryDeposit
        ? (primaryDeposit.getQuantityUi?.()?.assets?.toNumber() || 0)
        : 0;

      for (const borrowBalance of borrowBalances) {
        const bank          = account.client?.getBankByPk(borrowBalance.bankPk);
        const borrowSymbol  = bank?.tokenSymbol || "UNKNOWN";
        const borrowAmount  = borrowBalance.getQuantityUi?.()?.liabilities?.toNumber() || 0;

        allPositions.push({
          owner_wallet_address:          walletAddressString,
          protocol_name:                 "marginfi",
          collateral_asset_symbol:       collateralSymbol,
          borrowed_asset_symbol:         borrowSymbol,
          collateral_amount:             collateralAmount,
          borrowed_amount:               borrowAmount,
          liquidation_threshold_ratio:   liquidationThreshold,
          current_collateral_ratio:      collateralRatio,
          margin_to_liquidation_percent: marginToLiquidation,
        });
      }
    }

    console.log(`[marginfi] Found ${allPositions.length} positions for ${walletAddressString.slice(0, 8)}…`);
    return allPositions;

  } catch (fetchError) {
    console.error("[marginfi] Fetch error:", fetchError.message);
    return [];
  }
}

// ─────────────────────────────────────────────────────────────
// Express HTTP server
// ─────────────────────────────────────────────────────────────

const expressApp = express();
expressApp.use(express.json());

/**
 * GET /positions/:walletAddress
 *
 * Returns all open lending/borrowing positions for a wallet
 * across Marginfi and Kamino, combined into one array.
 */
expressApp.get("/positions/:walletAddress", async (req, res) => {
  const { walletAddress } = req.params;

  if (!walletAddress || walletAddress.length < 32 || walletAddress.length > 44) {
    return res.status(400).json({ error: "Invalid Solana wallet address" });
  }

  try {
    // Fetch from both protocols in parallel
    const [marginfiPositions, kaminoPositions] = await Promise.allSettled([
      fetchMarginfiPositions(walletAddress),
      fetchKaminoPositions(walletAddress),
    ]);

    const allPositions = [
      ...(marginfiPositions.status === "fulfilled" ? marginfiPositions.value : []),
      ...(kaminoPositions.status  === "fulfilled" ? kaminoPositions.value  : []),
    ];

    return res.json({
      wallet_address:  walletAddress,
      open_positions:  allPositions,
      marginfi_count:  marginfiPositions.status === "fulfilled" ? marginfiPositions.value.length : 0,
      kamino_count:    kaminoPositions.status   === "fulfilled" ? kaminoPositions.value.length   : 0,
      fetched_at:      Math.floor(Date.now() / 1000),
    });

  } catch (unexpectedError) {
    console.error("[reader] Unexpected error:", unexpectedError.message);
    return res.status(500).json({ error: unexpectedError.message });
  }
});

/** GET /health */
expressApp.get("/health", (_req, res) => res.json({ status: "ok", service: "position-reader" }));

expressApp.listen(SERVER_PORT, () => {
  console.log(`[position-reader] Listening on port ${SERVER_PORT}`);
  console.log(`[position-reader] RPC: ${SOLANA_RPC_URL}`);
  console.log(`[position-reader] Protocols: Marginfi + Kamino (${KAMINO_LENDING_MARKETS.length} markets)`);
});
