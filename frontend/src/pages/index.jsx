/**
 * PythGuard — Main application page.
 *
 * Demo mode is the default state — the dashboard is always
 * populated with live-feeling data, even without a wallet.
 * Connecting a wallet switches to real on-chain data.
 */
import { useState, useEffect } from "react";
import {
  ConnectionProvider,
  WalletProvider,
} from "@solana/wallet-adapter-react";
import { WalletModalProvider } from "@solana/wallet-adapter-react-ui";
import { PhantomWalletAdapter } from "@solana/wallet-adapter-phantom";
import "@solana/wallet-adapter-react-ui/styles.css";

import { ConnectWallet } from "../components/Wallet/ConnectWallet";
import { FeedStatusBar } from "../components/Dashboard/FeedStatusBar";
import { PositionCard } from "../components/Dashboard/PositionCard";
import { RiskMeter } from "../components/Dashboard/RiskMeter";
import { useRiskScore } from "../hooks/useRiskScore";
import { fetchDemoConfidenceHistory } from "../api";

const SOLANA_MAINNET_RPC = "https://api.mainnet-beta.solana.com";
const SUPPORTED_WALLETS  = [new PhantomWalletAdapter()];

export default function App() {
  return (
    <ConnectionProvider endpoint={SOLANA_MAINNET_RPC}>
      <WalletProvider wallets={SUPPORTED_WALLETS} autoConnect>
        <WalletModalProvider>
          <PythGuardDashboard />
        </WalletModalProvider>
      </WalletProvider>
    </ConnectionProvider>
  );
}

function PythGuardDashboard() {
  const [connectedWalletAddress, setConnectedWalletAddress] = useState(null);
  const [confidenceHistories, setConfidenceHistories]       = useState({});

  const {
    riskSummary,
    isLoadingRiskData,
    riskDataError,
    isDemoMode,
    refreshRiskData,
  } = useRiskScore(connectedWalletAddress);

  // Pre-fetch confidence histories for all positions when demo data loads
  useEffect(() => {
    if (!isDemoMode || !riskSummary) return;
    riskSummary.positions.forEach(async (position) => {
      const ticker = position.collateral_asset.replace("/USD", "");
      if (confidenceHistories[ticker]) return;
      try {
        const historyData = await fetchDemoConfidenceHistory(ticker);
        setConfidenceHistories(prev => ({
          ...prev,
          [ticker]: historyData.history,
        }));
      } catch { /* silently skip */ }
    });
  }, [riskSummary, isDemoMode]);

  return (
    <div style={pageStyle}>
      {/* ── Header ─────────────────────────────────────── */}
      <header style={headerStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <svg width="22" height="22" viewBox="0 0 20 20" fill="none">
            <path d="M10 2L3 7v6l7 5 7-5V7L10 2z" stroke="#6366f1" strokeWidth="1.5" fill="rgba(99,102,241,.15)"/>
            <path d="M10 8v4M8 10h4" stroke="#6366f1" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <span style={{ color: "#f1f5f9", fontSize: "18px", fontWeight: 700, letterSpacing: "-0.5px" }}>
            PythGuard
          </span>
          <span style={{ color: "#475569", fontSize: "12px" }}>
            DeFi Risk Monitor · Solana · Powered by Pyth
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          {isDemoMode && (
            <span style={demoBadgeStyle}>
              DEMO — connect wallet for live data
            </span>
          )}
          <ConnectWallet onWalletConnected={setConnectedWalletAddress} />
        </div>
      </header>

      {/* ── Live Pyth feed bar ──────────────────────────── */}
      <FeedStatusBar isDemoMode={isDemoMode} />

      {/* ── Main content ───────────────────────────────── */}
      <main style={mainContentStyle}>

        {/* Error banner */}
        {riskDataError && (
          <div style={errorBannerStyle}>
            ⚠️ {riskDataError}
            <button onClick={refreshRiskData} style={retryBtnStyle}>Retry</button>
          </div>
        )}

        {/* Loading */}
        {isLoadingRiskData && !riskSummary && (
          <EmptyState title="Loading risk data…" description="Fetching Pyth price feeds and confidence intervals." />
        )}

        {/* Summary + positions */}
        {riskSummary && (
          <>
            {/* Overall summary row */}
            <div style={summaryRowStyle}>
              <RiskMeter
                riskScore={riskSummary.highest_risk_score}
                riskLevel={riskSummary.overall_risk_level}
                label="Overall Risk"
              />
              <div style={{ display: "flex", gap: "28px", alignItems: "center", flexWrap: "wrap" }}>
                <SummaryMetric label="OPEN POSITIONS" value={riskSummary.position_count} />
                <SummaryMetric
                  label="WALLET"
                  value={isDemoMode ? "DEMO" : `${connectedWalletAddress.slice(0,6)}…${connectedWalletAddress.slice(-4)}`}
                  mono
                />
                <SummaryMetric
                  label="LAST UPDATED"
                  value={new Date(riskSummary.computed_at_timestamp * 1000).toLocaleTimeString()}
                />
              </div>
              <button onClick={refreshRiskData} style={refreshBtnStyle}>
                ↻ Refresh
              </button>
            </div>

            {/* Position cards */}
            {riskSummary.position_count === 0 ? (
              <EmptyState
                title="No open positions found"
                description="No active lending or borrowing positions detected on Marginfi or Kamino for this wallet."
              />
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
                {riskSummary.positions.map((position, idx) => {
                  const ticker = position.collateral_asset.replace("/USD", "");
                  return (
                    <PositionCard
                      key={`${position.protocol_name}-${idx}`}
                      position={position}
                      confidenceHistory={confidenceHistories[ticker] || []}
                      isDemo={isDemoMode}
                    />
                  );
                })}
              </div>
            )}
          </>
        )}
      </main>

      {/* ── Footer ─────────────────────────────────────── */}
      <footer style={footerStyle}>
        <span>PythGuard · Apache 2.0 · Pyth Community Hackathon 2026</span>
        <a href="https://github.com/your-handle/pythguard" target="_blank" rel="noopener noreferrer" style={{ color: "#6366f1" }}>
          GitHub →
        </a>
      </footer>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Small components
// ─────────────────────────────────────────────────────────────

function EmptyState({ title, description }) {
  return (
    <div style={{ textAlign: "center", padding: "60px 24px" }}>
      <h2 style={{ color: "#e2e8f0", margin: "0 0 12px", fontSize: "20px" }}>{title}</h2>
      <p style={{ color: "#64748b", maxWidth: "480px", margin: "0 auto", lineHeight: 1.6 }}>{description}</p>
    </div>
  );
}

function SummaryMetric({ label, value, mono = false }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ color: "#475569", fontSize: "10px", letterSpacing: "1px", marginBottom: "4px" }}>{label}</div>
      <div style={{ color: "#e2e8f0", fontSize: "14px", fontWeight: 600, fontFamily: mono ? "monospace" : "inherit" }}>{value}</div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Styles
// ─────────────────────────────────────────────────────────────

const pageStyle      = { minHeight: "100vh", background: "#020817", color: "#e2e8f0", fontFamily: "'Inter', system-ui, sans-serif" };
const headerStyle    = { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "14px 24px", borderBottom: "1px solid #1e293b", background: "#020817" };
const mainContentStyle = { maxWidth: "900px", margin: "0 auto", padding: "28px 24px" };
const summaryRowStyle  = { display: "flex", alignItems: "center", justifyContent: "space-between", background: "#0f172a", border: "1px solid #1e293b", borderRadius: "16px", padding: "18px 28px", marginBottom: "24px", flexWrap: "wrap", gap: "16px" };
const footerStyle    = { display: "flex", justifyContent: "space-between", padding: "18px 24px", borderTop: "1px solid #1e293b", color: "#334155", fontSize: "12px" };
const errorBannerStyle = { background: "rgba(239,68,68,.08)", border: "1px solid rgba(239,68,68,.3)", borderRadius: "8px", padding: "12px 16px", color: "#fca5a5", fontSize: "13px", display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" };
const retryBtnStyle  = { background: "transparent", border: "1px solid #ef4444", color: "#ef4444", padding: "4px 12px", borderRadius: "6px", cursor: "pointer", fontSize: "12px" };
const refreshBtnStyle = { background: "transparent", border: "1px solid #1e293b", color: "#94a3b8", padding: "7px 14px", borderRadius: "8px", cursor: "pointer", fontSize: "12px", transition: "border-color .2s" };
const demoBadgeStyle  = { background: "#1e293b", border: "1px solid #334155", color: "#64748b", padding: "4px 10px", borderRadius: "20px", fontSize: "11px", letterSpacing: "0.5px" };
