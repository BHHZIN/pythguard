/// Marginfi protocol position reader.
///
/// Reads open lending/borrowing positions from Marginfi accounts
/// on Solana and converts them to PythGuard's LendingPosition type.
///
/// Marginfi docs: https://docs.marginfi.com
use anyhow::{Context, Result};
use solana_client::rpc_client::RpcClient;
use solana_sdk::pubkey::Pubkey;
use std::str::FromStr;
use tracing::info;

use crate::types::LendingPosition;

// ─────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────

/// Marginfi program ID on Solana Mainnet
const MARGINFI_PROGRAM_ID: &str = "MFv2hWf31Z9kbCa1snEPdcgewg9LFMrj9gGpDdP9Iqw";

/// Marginfi standard liquidation threshold (80% LTV)
const MARGINFI_LIQUIDATION_THRESHOLD_RATIO: f64 = 0.80;

// ─────────────────────────────────────────────────────────────
// MarginfiPositionReader
// ─────────────────────────────────────────────────────────────

/// Reads open Marginfi positions for a given wallet address.
pub struct MarginfiPositionReader {
    solana_rpc_client: RpcClient,
    marginfi_program_pubkey: Pubkey,
}

impl MarginfiPositionReader {
    pub fn new(solana_rpc_url: &str) -> Result<Self> {
        let marginfi_program_pubkey = Pubkey::from_str(MARGINFI_PROGRAM_ID)
            .context("Invalid Marginfi program ID")?;

        Ok(Self {
            solana_rpc_client: RpcClient::new(solana_rpc_url.to_string()),
            marginfi_program_pubkey,
        })
    }

    /// Fetches all open lending/borrowing positions for a wallet.
    ///
    /// Returns an empty Vec (not an error) if the wallet has no
    /// Marginfi positions — this is the expected case for new users.
    pub fn fetch_positions_for_wallet(
        &self,
        owner_wallet_address: &str,
    ) -> Result<Vec<LendingPosition>> {
        let owner_pubkey = Pubkey::from_str(owner_wallet_address)
            .context("Invalid wallet address")?;

        // Fetch all program accounts owned by the Marginfi program
        // that are associated with this wallet
        let program_accounts = self
            .solana_rpc_client
            .get_program_accounts(&self.marginfi_program_pubkey)
            .context("Failed to fetch Marginfi program accounts")?;

        let wallet_positions: Vec<LendingPosition> = program_accounts
            .into_iter()
            .filter_map(|(_account_pubkey, account_data)| {
                self.deserialize_marginfi_account(
                    owner_wallet_address,
                    &owner_pubkey,
                    &account_data.data,
                )
                .ok()
                .flatten()
            })
            .collect();

        info!(
            wallet  = owner_wallet_address,
            count   = wallet_positions.len(),
            "Marginfi positions fetched"
        );

        Ok(wallet_positions)
    }

    // ─────────────────────────────────────────────────
    // Private helpers
    // ─────────────────────────────────────────────────

    /// Attempts to deserialize a raw Marginfi account into a LendingPosition.
    /// Returns None if the account doesn't belong to the target wallet.
    fn deserialize_marginfi_account(
        &self,
        owner_wallet_address: &str,
        owner_pubkey: &Pubkey,
        raw_account_data: &[u8],
    ) -> Result<Option<LendingPosition>> {
        // NOTE: Full Marginfi account layout deserialization requires
        // the marginfi-client crate. This implementation uses the
        // account layout documented at https://docs.marginfi.com/dev
        //
        // For hackathon purposes, we decode the key fields:
        // - authority (first 32 bytes) = wallet that owns the account
        // - balance fields at known offsets per Marginfi's IDL

        if raw_account_data.len() < 32 {
            return Ok(None);
        }

        let account_authority = Pubkey::new_from_array(
            raw_account_data[0..32]
                .try_into()
                .context("Failed to read account authority bytes")?,
        );

        // Guard: skip accounts not owned by the target wallet
        if &account_authority != owner_pubkey {
            return Ok(None);
        }

        // Placeholder values — replace with real IDL deserialization
        // once marginfi-client crate is integrated
        let collateral_amount = Self::read_f64_at_offset(raw_account_data, 64)?;
        let borrowed_amount = Self::read_f64_at_offset(raw_account_data, 72)?;

        // Guard: skip empty positions (nothing deposited or borrowed)
        if collateral_amount <= 0.0 || borrowed_amount <= 0.0 {
            return Ok(None);
        }

        let current_collateral_ratio = collateral_amount / borrowed_amount;
        let margin_to_liquidation_percent = (current_collateral_ratio
            - MARGINFI_LIQUIDATION_THRESHOLD_RATIO)
            / MARGINFI_LIQUIDATION_THRESHOLD_RATIO
            * 100.0;

        Ok(Some(LendingPosition {
            owner_wallet_address: owner_wallet_address.to_string(),
            protocol_name: "marginfi".to_string(),
            collateral_asset_symbol: "SOL".to_string(),
            borrowed_asset_symbol: "USDC".to_string(),
            collateral_amount,
            borrowed_amount,
            liquidation_threshold_ratio: MARGINFI_LIQUIDATION_THRESHOLD_RATIO,
            current_collateral_ratio,
            margin_to_liquidation_percent,
        }))
    }

    /// Reads an f64 value from a byte slice at a given offset.
    fn read_f64_at_offset(data: &[u8], byte_offset: usize) -> Result<f64> {
        let end_offset = byte_offset + 8;
        if data.len() < end_offset {
            anyhow::bail!(
                "Account data too short to read f64 at offset {}",
                byte_offset
            );
        }
        let raw_bytes: [u8; 8] = data[byte_offset..end_offset]
            .try_into()
            .context("Failed to read 8 bytes for f64")?;
        Ok(f64::from_le_bytes(raw_bytes))
    }
}
