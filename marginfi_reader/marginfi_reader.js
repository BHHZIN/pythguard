/**
 * PythGuard Position Reader — Marginfi + Kamino
 *
 * Fixed for:
 *   - Marginfi SDK v6: getConfig("production") string, not Environment.PRODUCTION
 *   - Kamino klend-sdk v1: uses @solana/web3.js v1 Connection (not v2 RPC)
 */

import express from "express";
import { Connection, PublicKey } from "@solana/web3.js";

const SOLANA_RPC_URL = process.env.SOLANA_RPC_URL || "https://api.mainnet-beta.solana.com";
const SERVER_PORT    = parseInt(process.env.PORT || "8002");

const KAMINO_LENDING_MARKETS = [
  "7u3HeHxYDLhnCoErrtycNokbQYbWGzLs6JSDqGAv5PfF",
  "DxXdAyU3kCjnyggvHmY5nAwg5cRbbmdyX3npfDMjjMek",
  "ByYiZxp8QrdN9qbdtaAiePN8AAr3qvTPppNJDpf5DVJ5",
];

// ─────────────────────────────────────────────────────────────
// Kamino (klend-sdk v1 — uses web3.js v1 Connection)
// ─────────────────────────────────────────────────────────────

async function fetchKaminoPositions(walletAddressString) {
  const allPositions = [];

  let KaminoMarket, VanillaObligation;
  try {
    const sdk = await import("@kamino-finance/klend-sdk");
    KaminoMarket      = sdk.KaminoMarket;
    VanillaObligation = sdk.VanillaObligation;
  } catch (err) {
    console.error("[kamino] SDK import failed:", err.message);
    return [];
  }

  // klend-sdk v1 uses the standard web3.js v1 Connection
  const connection   = new Connection(SOLANA_RPC_URL, "confirmed");
  const walletPubkey = new PublicKey(walletAddressString);

  const marketPromises = KAMINO_LENDING_MARKETS.map(async (marketAddress) => {
    try {
      const market = await KaminoMarket.load(
        connection,
        new PublicKey(marketAddress),
        400
      );

      if (!market) return [];

      // VanillaObligation is the standard borrow/lend obligation type
      const obligationClass = VanillaObligation
        ? new VanillaObligation(market.programId)
        : null;

      const obligation = obligationClass
        ? await market.getObligationByWallet(walletPubkey, obligationClass)
        : await market.getObligationByWallet(walletPubkey);

      if (!obligation) return [];

      const deposits = [];
      const borrows  = [];

      // Extract deposits
      for (const [reservePk, deposit] of (obligation.deposits || new Map())) {
        const reserve    = market.getReserveByAddress(reservePk);
        const symbol     = reserve?.stats?.symbol || "UNKNOWN";
        const amount     = typeof deposit.toNumber === "function"
          ? deposit.toNumber()
          : Number(deposit);
        const usdValue   = amount * (reserve?.stats?.lastPrice || 1);
        deposits.push({ symbol, amount, usdValue });
      }

      // Extract borrows
      for (const [reservePk, borrow] of (obligation.borrows || new Map())) {
        const reserve  = market.getReserveByAddress(reservePk);
        const symbol   = reserve?.stats?.symbol || "UNKNOWN";
        const amount   = typeof borrow.toNumber === "function"
          ? borrow.toNumber()
          : Number(borrow);
        const usdValue = amount * (reserve?.stats?.lastPrice || 1);
        borrows.push({ symbol, amount, usdValue });
      }

      if (borrows.length === 0) return [];

      const totalCollateralUsd = deposits.reduce((s, d) => s + d.usdValue, 0);
      const totalDebtUsd       = borrows.reduce((s, b)  => s + b.usdValue, 0);

      if (totalDebtUsd <= 0) return [];

      const collateralRatio = totalCollateralUsd / totalDebtUsd;
      const liquidationLtv  = parseFloat(
        obligation.stats?.liquidationLtv || "0.80"
      );
      const marginToLiquidation = ((collateralRatio - liquidationLtv) / liquidationLtv) * 100;

      const primaryCollateral = [...deposits].sort((a, b) => b.usdValue - a.usdValue)[0];

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

    } catch (err) {
      if (!err.message?.includes("null") && !err.message?.includes("not found")) {
        console.error(`[kamino] Market ${marketAddress.slice(0, 8)} error:`, err.message);
      }
      return [];
    }
  });

  const results = await Promise.allSettled(marketPromises);
  for (const r of results) {
    if (r.status === "fulfilled" && Array.isArray(r.value)) {
      allPositions.push(...r.value);
    }
  }

  console.log(`[kamino] Found ${allPositions.length} positions for ${walletAddressString.slice(0, 8)}…`);
  return allPositions;
}

// ─────────────────────────────────────────────────────────────
// Marginfi (SDK v6 — getConfig("production") string)
// ─────────────────────────────────────────────────────────────

async function fetchMarginfiPositions(walletAddressString) {
  let MarginfiClient, getConfig;
  try {
    const sdk  = await import("@mrgnlabs/marginfi-client-v2");
    MarginfiClient = sdk.MarginfiClient;
    getConfig      = sdk.getConfig;
  } catch (err) {
    console.error("[marginfi] SDK import failed:", err.message);
    return [];
  }

  try {
    const connection = new Connection(SOLANA_RPC_URL, "confirmed");

    // SDK v6: pass "production" as string, not Environment.PRODUCTION
    const config = getConfig("production");
    const client = await MarginfiClient.fetch(config, null, connection);

    const ownerPubkey = new PublicKey(walletAddressString);
    const accounts    = await client.getMarginfiAccountsForAuthority(ownerPubkey);

    if (!accounts || accounts.length === 0) return [];

    const allPositions = [];

    for (const account of accounts) {
      const balances       = account.activeBalances || [];
      const borrowBalances = balances.filter((b) => b.isBorrowingPosition?.() === true);

      if (borrowBalances.length === 0) continue;

      const health = account.computeHealthComponents?.("Maint");
      const totalCollateralUsd = health?.assets?.toNumber?.()      || 0;
      const totalDebtUsd       = health?.liabilities?.toNumber?.() || 0;

      if (totalDebtUsd <= 0) continue;

      const collateralRatio      = totalCollateralUsd / totalDebtUsd;
      const liquidationThreshold = 0.80;
      const marginToLiquidation  = ((collateralRatio - liquidationThreshold) / liquidationThreshold) * 100;

      const depositBalances = balances.filter((b) => b.isLendingPosition?.() === true);
      const primaryDeposit  = depositBalances.sort((a, b) => {
        const aAmt = a.getQuantityUi?.()?.assets?.toNumber?.() || 0;
        const bAmt = b.getQuantityUi?.()?.assets?.toNumber?.() || 0;
        return bAmt - aAmt;
      })[0];

      const collateralSymbol = primaryDeposit
        ? (client.getBankByPk?.(primaryDeposit.bankPk)?.tokenSymbol || "UNKNOWN")
        : "UNKNOWN";
      const collateralAmount = primaryDeposit
        ? (primaryDeposit.getQuantityUi?.()?.assets?.toNumber?.() || 0)
        : 0;

      for (const borrow of borrowBalances) {
        const bank         = client.getBankByPk?.(borrow.bankPk);
        const borrowSymbol = bank?.tokenSymbol || "UNKNOWN";
        const borrowAmount = borrow.getQuantityUi?.()?.liabilities?.toNumber?.() || 0;

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

  } catch (err) {
    console.error("[marginfi] Fetch error:", err.message);
    return [];
  }
}

// ─────────────────────────────────────────────────────────────
// Express server
// ─────────────────────────────────────────────────────────────

const app = express();
app.use(express.json());

app.get("/positions/:walletAddress", async (req, res) => {
  const { walletAddress } = req.params;

  if (!walletAddress || walletAddress.length < 32 || walletAddress.length > 44) {
    return res.status(400).json({ error: "Invalid Solana wallet address" });
  }

  const [marginfiResult, kaminoResult] = await Promise.allSettled([
    fetchMarginfiPositions(walletAddress),
    fetchKaminoPositions(walletAddress),
  ]);

  const marginfiPositions = marginfiResult.status === "fulfilled" ? marginfiResult.value : [];
  const kaminoPositions   = kaminoResult.status  === "fulfilled" ? kaminoResult.value  : [];
  const allPositions      = [...marginfiPositions, ...kaminoPositions];

  return res.json({
    wallet_address:  walletAddress,
    open_positions:  allPositions,
    marginfi_count:  marginfiPositions.length,
    kamino_count:    kaminoPositions.length,
    fetched_at:      Math.floor(Date.now() / 1000),
  });
});

app.get("/health", (_req, res) => res.json({ status: "ok", service: "position-reader" }));

app.listen(SERVER_PORT, () => {
  console.log(`[position-reader] Listening on port ${SERVER_PORT}`);
  console.log(`[position-reader] RPC: ${SOLANA_RPC_URL}`);
  console.log(`[position-reader] Protocols: Marginfi + Kamino (${KAMINO_LENDING_MARKETS.length} markets)`);
});
