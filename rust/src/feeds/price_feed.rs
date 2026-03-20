/// Pyth price feed reader for Solana.
///
/// Reads price + confidence interval from Pyth on-chain accounts
/// and produces PriceFeedSnapshot structs for the Risk Engine.
///
/// The confidence interval is PythGuard's core differentiator —
/// most DeFi apps only read `price`. We also read `confidence`
/// to detect oracle uncertainty before it triggers liquidations.
use anyhow::{Context, Result};
use pyth_sdk_solana::state::SolanaPriceAccount;
use solana_client::rpc_client::RpcClient;
use solana_sdk::pubkey::Pubkey;
use std::str::FromStr;
use tracing::{info, warn};

use crate::types::PriceFeedSnapshot;

// ─────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────

/// Maximum age (in seconds) a Pyth price is considered valid.
/// Prices older than this are rejected to prevent stale-price attacks.
const MAXIMUM_ACCEPTABLE_PRICE_AGE_SECONDS: i64 = 60;

/// Pyth price feed IDs on Solana Mainnet.
/// Source: https://pyth.network/price-feeds
pub struct PythFeedAddresses;

impl PythFeedAddresses {
    pub const SOL_USD: &'static str =
        "H6ARHf6YXhGYeQfUzQNGk6rDNnLBQKrenN712K4AQJEG";
    pub const BTC_USD: &'static str =
        "GVXRSBjFk6e909asbz3XWBLBX9BQE7T8dkmHJkbRSbfK";
    pub const ETH_USD: &'static str =
        "JBu1AL4obBcCMqKBBxhpWCNUt136ijcuMZLFvTP7iWdB";
    pub const USDC_USD: &'static str =
        "Gnt27xtC473ZT2Mw5u8wZ68Z3gULkSTb5DuxJy7eJotD";
    pub const JITOSOL_USD: &'static str =
        "7yyaeuJ1GGtVBLT2z2xub5ZWYKaNhF28mj1RdV4VDFVk";
}

// ─────────────────────────────────────────────────────────────
// PythFeedReader
// ─────────────────────────────────────────────────────────────

/// Reads Pyth price feed accounts directly from Solana RPC.
pub struct PythFeedReader {
    solana_rpc_client: RpcClient,
}

impl PythFeedReader {
    /// Creates a new reader connected to the given Solana RPC endpoint.
    pub fn new(solana_rpc_url: &str) -> Self {
        Self {
            solana_rpc_client: RpcClient::new(solana_rpc_url.to_string()),
        }
    }

    /// Reads a single Pyth price feed by its on-chain account address.
    ///
    /// Returns an error if:
    /// - The account doesn't exist or isn't a valid Pyth account
    /// - The price is older than MAXIMUM_ACCEPTABLE_PRICE_AGE_SECONDS
    /// - The confidence is zero (oracle is reporting maximum uncertainty)
    pub fn read_price_feed(
        &self,
        asset_symbol: &str,
        feed_account_address: &str,
    ) -> Result<PriceFeedSnapshot> {
        let feed_pubkey = Pubkey::from_str(feed_account_address)
            .context("Invalid Pyth feed account address")?;

        let account_data = self
            .solana_rpc_client
            .get_account(&feed_pubkey)
            .context("Failed to fetch Pyth feed account from Solana RPC")?;

        // Deserialize the raw account bytes into a Pyth price account struct
        let pyth_price_account =
            SolanaPriceAccount::account_info_to_state(&account_data)
                .context("Failed to deserialize Pyth price account")?;

        let current_unix_timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs() as i64;

        let price_age_seconds =
            current_unix_timestamp - pyth_price_account.timestamp;

        // Guard: reject stale prices — a stale price is a security risk
        if price_age_seconds > MAXIMUM_ACCEPTABLE_PRICE_AGE_SECONDS {
            warn!(
                asset = asset_symbol,
                age_seconds = price_age_seconds,
                "Rejecting stale Pyth price feed"
            );
            anyhow::bail!(
                "Pyth price for {} is stale ({} seconds old)",
                asset_symbol,
                price_age_seconds
            );
        }

        // Guard: reject zero confidence — means oracle has no certainty
        if pyth_price_account.agg.conf == 0 {
            anyhow::bail!(
                "Pyth confidence for {} is zero — refusing to use this price",
                asset_symbol
            );
        }

        let normalized_price = Self::normalize_price(
            pyth_price_account.agg.price,
            pyth_price_account.expo,
        );

        let confidence_ratio = Self::calculate_confidence_ratio(
            pyth_price_account.agg.price,
            pyth_price_account.agg.conf,
        );

        info!(
            asset       = asset_symbol,
            price       = normalized_price,
            confidence  = confidence_ratio,
            "Price feed read successfully"
        );

        Ok(PriceFeedSnapshot {
            asset_symbol: asset_symbol.to_string(),
            raw_price: pyth_price_account.agg.price,
            raw_confidence: pyth_price_account.agg.conf,
            price_exponent: pyth_price_account.expo,
            publish_timestamp: pyth_price_account.timestamp,
            normalized_price,
            confidence_ratio,
        })
    }

    /// Reads all relevant feeds in a single pass.
    /// Feeds that fail (stale, zero confidence) are logged and skipped
    /// rather than crashing the entire read cycle.
    pub fn read_all_supported_feeds(&self) -> Vec<PriceFeedSnapshot> {
        let supported_feeds = vec![
            ("SOL/USD", PythFeedAddresses::SOL_USD),
            ("BTC/USD", PythFeedAddresses::BTC_USD),
            ("ETH/USD", PythFeedAddresses::ETH_USD),
            ("USDC/USD", PythFeedAddresses::USDC_USD),
            ("JitoSOL/USD", PythFeedAddresses::JITOSOL_USD),
        ];

        supported_feeds
            .into_iter()
            .filter_map(|(asset_symbol, feed_address)| {
                match self.read_price_feed(asset_symbol, feed_address) {
                    Ok(snapshot) => Some(snapshot),
                    Err(read_error) => {
                        warn!(
                            asset = asset_symbol,
                            error = %read_error,
                            "Skipping feed due to read error"
                        );
                        None
                    }
                }
            })
            .collect()
    }

    // ─────────────────────────────────────────────────
    // Private helpers
    // ─────────────────────────────────────────────────

    /// Converts raw Pyth price to human-readable float.
    /// Formula: actual_price = raw_price × 10^exponent
    fn normalize_price(raw_price: i64, price_exponent: i32) -> f64 {
        (raw_price as f64) * 10f64.powi(price_exponent)
    }

    /// Calculates confidence ratio: confidence / |price|.
    /// This is PythGuard's primary risk signal.
    fn calculate_confidence_ratio(raw_price: i64, raw_confidence: u64) -> f64 {
        if raw_price == 0 {
            return 1.0; // Maximum uncertainty when price is zero
        }
        (raw_confidence as f64) / (raw_price.abs() as f64)
    }
}

// ─────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn confidence_ratio_is_zero_when_confidence_is_zero() {
        let ratio = PythFeedReader::calculate_confidence_ratio(100_000, 0);
        assert_eq!(ratio, 0.0);
    }

    #[test]
    fn confidence_ratio_returns_one_when_price_is_zero() {
        let ratio = PythFeedReader::calculate_confidence_ratio(0, 500);
        assert_eq!(ratio, 1.0);
    }

    #[test]
    fn confidence_ratio_is_correct_for_typical_values() {
        // price = $100, confidence = $0.10 → ratio = 0.001
        let ratio = PythFeedReader::calculate_confidence_ratio(10_000_000, 10_000);
        let expected_ratio = 0.001;
        assert!((ratio - expected_ratio).abs() < 1e-9);
    }

    #[test]
    fn price_normalization_applies_negative_exponent_correctly() {
        // raw = 10_000_000, exponent = -5 → $100.00
        let normalized = PythFeedReader::normalize_price(10_000_000, -5);
        assert!((normalized - 100.0).abs() < 1e-6);
    }
}
