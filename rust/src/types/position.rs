/// Core data types shared across the PythGuard reader.
///
/// These structs are serialized to JSON and consumed by the
/// Python Risk Engine via the internal HTTP bridge.
use serde::{Deserialize, Serialize};

// ─────────────────────────────────────────────────────────────
// Price Feed Snapshot
// ─────────────────────────────────────────────────────────────

/// A point-in-time snapshot of a Pyth price feed, including
/// the confidence interval — the metric central to PythGuard's
/// risk scoring logic.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PriceFeedSnapshot {
    /// Asset symbol, e.g. "SOL/USD"
    pub asset_symbol: String,

    /// Raw price value from Pyth (must be scaled by `price_exponent`)
    pub raw_price: i64,

    /// Confidence interval — how certain Pyth is about this price.
    /// Higher confidence = higher uncertainty = higher risk.
    pub raw_confidence: u64,

    /// Exponent to convert raw values: actual_price = raw_price * 10^exponent
    pub price_exponent: i32,

    /// Unix timestamp of when this price was last published on-chain
    pub publish_timestamp: i64,

    /// Human-readable price after applying exponent
    pub normalized_price: f64,

    /// Confidence ratio: confidence / |price| — PythGuard's core signal.
    /// - Below 0.001 (0.1%)  → LOW risk
    /// - 0.001 to 0.005      → MEDIUM risk
    /// - Above 0.005 (0.5%)  → HIGH risk
    pub confidence_ratio: f64,
}

// ─────────────────────────────────────────────────────────────
// Lending/Borrowing Position
// ─────────────────────────────────────────────────────────────

/// A single open lending/borrowing position from a Solana DeFi protocol.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LendingPosition {
    /// Solana wallet address of the position owner
    pub owner_wallet_address: String,

    /// Protocol this position belongs to (e.g. "marginfi", "kamino")
    pub protocol_name: String,

    /// Asset used as collateral (e.g. "SOL", "JitoSOL")
    pub collateral_asset_symbol: String,

    /// Asset borrowed against the collateral (e.g. "USDC", "USDT")
    pub borrowed_asset_symbol: String,

    /// Amount of collateral deposited (in human-readable units)
    pub collateral_amount: f64,

    /// Amount borrowed (in human-readable units)
    pub borrowed_amount: f64,

    /// Protocol's liquidation threshold (e.g. 0.80 = 80%)
    pub liquidation_threshold_ratio: f64,

    /// Current collateral / borrowed ratio
    pub current_collateral_ratio: f64,

    /// Margin to liquidation — how far the position is from being liquidated
    /// Positive = safe. Negative = already undercollateralized.
    pub margin_to_liquidation_percent: f64,
}

// ─────────────────────────────────────────────────────────────
// Bridge payload — sent from Rust to Python backend
// ─────────────────────────────────────────────────────────────

/// Full payload delivered to the Python Risk Engine on each polling cycle.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskInputPayload {
    /// Wallet address this payload belongs to
    pub wallet_address: String,

    /// All open positions found for this wallet
    pub open_positions: Vec<LendingPosition>,

    /// Latest Pyth snapshots for all assets referenced in open_positions
    pub price_feed_snapshots: Vec<PriceFeedSnapshot>,

    /// Unix timestamp when this payload was assembled
    pub assembled_at_timestamp: i64,
}
