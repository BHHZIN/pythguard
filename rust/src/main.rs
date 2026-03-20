/// PythGuard Rust Reader — entry point.
///
/// Starts a lightweight HTTP server that the Python Risk Engine
/// calls to fetch fresh on-chain data (price feeds + positions).
///
/// Architecture:
///   Python Backend → GET /payload/{wallet} → Rust Reader
///                                           → Solana RPC
///                                           → Pyth on-chain accounts
///                                           → Returns RiskInputPayload JSON
mod feeds;
mod protocols;
mod types;

use anyhow::Result;
use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::Json,
    routing::get,
    Router,
};
use std::sync::Arc;
use tracing::{error, info};
use tracing_subscriber::EnvFilter;

use feeds::PythFeedReader;
use protocols::MarginfiPositionReader;
use types::RiskInputPayload;

// ─────────────────────────────────────────────────────────────
// Application state
// ─────────────────────────────────────────────────────────────

/// Shared application state injected into every HTTP handler.
struct ApplicationState {
    pyth_feed_reader: PythFeedReader,
    marginfi_position_reader: MarginfiPositionReader,
}

// ─────────────────────────────────────────────────────────────
// HTTP Handlers
// ─────────────────────────────────────────────────────────────

/// GET /payload/{wallet_address}
///
/// Assembles a full RiskInputPayload for the given wallet:
/// - Reads all supported Pyth price feeds
/// - Reads open Marginfi positions for the wallet
/// - Returns combined payload as JSON
async fn handle_get_risk_payload(
    Path(wallet_address): Path<String>,
    State(application_state): State<Arc<ApplicationState>>,
) -> Result<Json<RiskInputPayload>, StatusCode> {
    info!(wallet = %wallet_address, "Assembling risk payload");

    let price_feed_snapshots = application_state
        .pyth_feed_reader
        .read_all_supported_feeds();

    let open_positions = application_state
        .marginfi_position_reader
        .fetch_positions_for_wallet(&wallet_address)
        .map_err(|position_read_error| {
            error!(error = %position_read_error, "Failed to fetch positions");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let assembled_at_timestamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_secs() as i64;

    let risk_input_payload = RiskInputPayload {
        wallet_address,
        open_positions,
        price_feed_snapshots,
        assembled_at_timestamp,
    };

    Ok(Json(risk_input_payload))
}

/// GET /health
///
/// Simple health check for the Python backend to verify the
/// Rust reader is alive before requesting payloads.
async fn handle_health_check() -> &'static str {
    "ok"
}

// ─────────────────────────────────────────────────────────────
// Main
// ─────────────────────────────────────────────────────────────

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env())
        .init();

    let solana_rpc_url = std::env::var("SOLANA_RPC_URL")
        .unwrap_or_else(|_| "https://api.mainnet-beta.solana.com".to_string());

    let listener_address = std::env::var("RUST_READER_ADDR")
        .unwrap_or_else(|_| "0.0.0.0:8001".to_string());

    info!(rpc = %solana_rpc_url, addr = %listener_address, "Starting PythGuard Rust Reader");

    let application_state = Arc::new(ApplicationState {
        pyth_feed_reader: PythFeedReader::new(&solana_rpc_url),
        marginfi_position_reader: MarginfiPositionReader::new(&solana_rpc_url)?,
    });

    let router = Router::new()
        .route("/payload/:wallet_address", get(handle_get_risk_payload))
        .route("/health", get(handle_health_check))
        .with_state(application_state);

    let tcp_listener = tokio::net::TcpListener::bind(&listener_address).await?;
    info!("Rust Reader listening on {}", listener_address);

    axum::serve(tcp_listener, router).await?;

    Ok(())
}
