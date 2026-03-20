/**
 * PythGuard API client.
 *
 * Typed wrappers around every backend endpoint.
 * All components import from this file — never call fetch() directly.
 */
import axios from "axios";

const BACKEND_BASE_URL =
  import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

const pythGuardApiClient = axios.create({
  baseURL: `${BACKEND_BASE_URL}/api/v1`,
  timeout: 15_000,
  headers: { "Content-Type": "application/json" },
});

// ─────────────────────────────────────────────────────────────
// Type definitions (mirrors backend Pydantic schemas)
// ─────────────────────────────────────────────────────────────

/** @typedef {"LOW" | "MEDIUM" | "HIGH"} RiskLevel */

/**
 * @typedef {Object} PositionRisk
 * @property {string} wallet_address
 * @property {string} protocol_name
 * @property {string} collateral_asset
 * @property {string} borrowed_asset
 * @property {number} composite_risk_score
 * @property {number} collateral_ratio_score
 * @property {number} confidence_interval_score
 * @property {number} volatility_trend_score
 * @property {RiskLevel} risk_level
 * @property {number} estimated_liquidation_price_drop_percent
 * @property {number} current_confidence_ratio
 * @property {boolean} is_confidence_trending_upward
 * @property {string} alert_message
 */

/**
 * @typedef {Object} WalletRiskSummary
 * @property {string} wallet_address
 * @property {RiskLevel} overall_risk_level
 * @property {number} highest_risk_score
 * @property {number} position_count
 * @property {PositionRisk[]} positions
 * @property {number} computed_at_timestamp
 */

/**
 * @typedef {Object} FeedStatus
 * @property {string} asset_symbol
 * @property {number} normalized_price
 * @property {number} confidence_ratio
 * @property {RiskLevel} risk_level_from_confidence
 * @property {number} publish_timestamp
 * @property {boolean} is_feed_fresh
 */

/**
 * @typedef {Object} Candlestick
 * @property {number} timestamp
 * @property {number} open_price
 * @property {number} high_price
 * @property {number} low_price
 * @property {number} close_price
 * @property {number|null} volume
 */

// ─────────────────────────────────────────────────────────────
// API methods
// ─────────────────────────────────────────────────────────────

/**
 * Fetches full risk summary for a Solana wallet address.
 * @param {string} walletAddress
 * @returns {Promise<WalletRiskSummary>}
 */
export async function fetchWalletRiskSummary(walletAddress) {
  const response = await pythGuardApiClient.get(`/risk/${walletAddress}`);
  return response.data;
}

/**
 * Fetches current status of all supported Pyth price feeds.
 * @returns {Promise<FeedStatus[]>}
 */
export async function fetchAllFeedStatuses() {
  const response = await pythGuardApiClient.get("/feeds/status");
  return response.data;
}

/**
 * Fetches OHLC candle data for a single asset.
 * @param {string} assetTicker  e.g. "SOL", "BTC"
 * @param {string} resolution   e.g. "5" (minutes)
 * @param {number} lookbackHours
 * @returns {Promise<{symbol: string, candles: Candlestick[]}>}
 */
export async function fetchCandlestickChartData(
  assetTicker,
  resolution = "5",
  lookbackHours = 24
) {
  const response = await pythGuardApiClient.get(
    `/feeds/chart/${assetTicker}`,
    { params: { resolution, lookback_hours: lookbackHours } }
  );
  return response.data;
}

// ─────────────────────────────────────────────────────────────
// Demo endpoints (no wallet or token required)
// ─────────────────────────────────────────────────────────────

/**
 * Fetches the live demo risk summary (oscillating mock data).
 * @returns {Promise<WalletRiskSummary>}
 */
export async function fetchDemoRiskSummary() {
  const response = await pythGuardApiClient.get("/demo/risk");
  return response.data;
}

/**
 * Fetches demo feed statuses.
 * @returns {Promise<FeedStatus[]>}
 */
export async function fetchDemoFeedStatuses() {
  const response = await pythGuardApiClient.get("/demo/feeds");
  return response.data;
}

/**
 * Fetches demo confidence history for a given asset.
 * @param {string} assetTicker
 * @returns {Promise<{asset: string, history: Array}>}
 */
export async function fetchDemoConfidenceHistory(assetTicker) {
  const response = await pythGuardApiClient.get(
    `/demo/confidence/${assetTicker}`
  );
  return response.data;
}
