/**
 * PythGuard — Main application page.
 *
 * Demo mode is the default state — always populated with live-feeling data.
 * Connecting a wallet switches to Live Mode (real on-chain data).
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
  const [showJudgeNotice, setShowJudgeNotice]               = useState(true);

  const {
    riskSummary,
    isLoadingRiskData,
    riskDataError,
    isDemoMode,
    refreshRiskData,
  } = useRiskScore(connectedWalletAddress);

  // Pre-fetch confidence histories for demo positions
  useEffect(() => {
    if (!isDemoMode || !riskSummary) return;
    riskSummary.positions.forEach(async (position) => {
      const ticker = position.collateral_asset.replace("/USD", "");
      if (confidenceHistories[ticker]) return;
      try {
        const historyData = await fetchDemoConfidenceHistory(ticker);
        setConfidenceHistories(prev => ({ ...prev, [ticker]: historyData.history }));
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
          {/* DEMO / LIVE mode indicator */}
          <div style={modeIndicatorStyle(isDemoMode)}>
            <div style={{
              width: "7px", height: "7px", borderRadius: "50%",
              background: isDemoMode ? "#f59e0b" : "#22c55e",
              boxShadow: isDemoMode ? "0 0 6px #f59e0b" : "0 0 6px #22c55e",
            }} />
            <span style={{ fontSize: "11px", fontWeight: 600, letterSpacing: "1px" }}>
              {isDemoMode ? "DEMO MODE" : "LIVE MODE"}
            </span>
          </div>
          <ConnectWallet onWalletConnected={setConnectedWalletAddress} />
        </div>
      </header>

      {/* ── Judge Notice Banner ─────────────────────────── */}
      {showJudgeNotice && (
        <div style={judgeBannerStyle}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}>
            <span style={{ fontSize: "16px", flexShrink: 0 }}>ℹ️</span>
            <div>
              <span style={{ color: "#93c5fd", fontWeight: 600, fontSize: "13px" }}>
                For judges & reviewers:{" "}
              </span>
              <span style={{ color: "#94a3b8", fontSize: "13px" }}>
                <strong style={{ color: "#e2e8f0" }}>Demo Mode</strong> is active by default — no wallet needed.
                It showcases all features with simulated Pyth-style confidence intervals that update in real time.{" "}
                <strong style={{ color: "#e2e8f0" }}>Live Mode</strong> activates when you connect a Phantom wallet
                that has active lending or borrowing positions on{" "}
                <strong style={{ color: "#e2e8f0" }}>Marginfi</strong> or{" "}
                <strong style={{ color: "#e2e8f0" }}>Kamino</strong>.
                Without open positions, the app correctly shows "No positions found".
              </span>
            </div>
          </div>
          <button
            onClick={() => setShowJudgeNotice(false)}
            style={{ background: "transparent", border: "none", color: "#475569", cursor: "pointer", fontSize: "18px", flexShrink: 0, padding: "0 4px" }}
          >
            ×
          </button>
        </div>
      )}

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
          <EmptyState
            title="Loading risk data…"
            description="Fetching Pyth price feeds and confidence intervals."
          />
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
                  label="MODE"
                  value={isDemoMode ? "DEMO" : "LIVE"}
                  color={isDemoMode ? "#f59e0b" : "#22c55e"}
                />
                <SummaryMetric
                  label="WALLET"
                  value={isDemoMode
                    ? "Not connected"
                    : `${connectedWalletAddress.slice(0,6)}…${connectedWalletAddress.slice(-4)}`}
                  mono
                />
                <SummaryMetric
                  label="LAST UPDATED"
                  value={new Date(riskSummary.computed_at_timestamp * 1000).toLocaleTimeString()}
                />
              </div>
              <button onClick={refreshRiskData} style={refreshBtnStyle}>↻ Refresh</button>
            </div>

            {/* No positions — with context for live mode */}
            {riskSummary.position_count === 0 && (
              <div style={noPositionsBoxStyle}>
                <div style={{ fontSize: "32px", marginBottom: "12px" }}>🔍</div>
                <h2 style={{ color: "#e2e8f0", margin: "0 0 10px", fontSize: "18px" }}>
                  No open positions found
                </h2>
                <p style={{ color: "#64748b", maxWidth: "500px", margin: "0 auto 16px", lineHeight: 1.6, fontSize: "14px" }}>
                  No active lending or borrowing positions were detected for this wallet
                  on Marginfi or Kamino.
                </p>
                {!isDemoMode && (
                  <div style={liveHintStyle}>
                    <strong style={{ color: "#93c5fd" }}>Live Mode tip:</strong>
                    <span style={{ color: "#64748b" }}>
                      {" "}To see real risk scores, use a wallet with open positions on{" "}
                      <a href="https://app.marginfi.com" target="_blank" rel="noopener noreferrer" style={{ color: "#6366f1" }}>Marginfi</a>
                      {" "}or{" "}
                      <a href="https://app.kamino.finance" target="_blank" rel="noopener noreferrer" style={{ color: "#6366f1" }}>Kamino</a>.
                      {" "}Or disconnect your wallet to use Demo Mode.
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Position cards */}
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
          </>
        )}
      </main>

      {/* ── Footer ─────────────────────────────────────── */}
      <footer style={footerStyle}>
        <span>PythGuard · Apache 2.0 · Pyth Community Hackathon 2026</span>
        <a
          href="https://github.com/BHHZIN/pythguard"
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: "#6366f1" }}
        >
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

function SummaryMetric({ label, value, mono = false, color = "#e2e8f0" }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ color: "#475569", fontSize: "10px", letterSpacing: "1px", marginBottom: "4px" }}>{label}</div>
      <div style={{ color, fontSize: "14px", fontWeight: 600, fontFamily: mono ? "monospace" : "inherit" }}>{value}</div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Styles
// ─────────────────────────────────────────────────────────────

const pageStyle       = { minHeight: "100vh", background: "#020817", color: "#e2e8f0", fontFamily: "'Inter', system-ui, sans-serif" };
const headerStyle     = { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "14px 24px", borderBottom: "1px solid #1e293b", background: "#020817" };
const mainContentStyle = { maxWidth: "900px", margin: "0 auto", padding: "28px 24px" };
const summaryRowStyle  = { display: "flex", alignItems: "center", justifyContent: "space-between", background: "#0f172a", border: "1px solid #1e293b", borderRadius: "16px", padding: "18px 28px", marginBottom: "24px", flexWrap: "wrap", gap: "16px" };
const footerStyle     = { display: "flex", justifyContent: "space-between", padding: "18px 24px", borderTop: "1px solid #1e293b", color: "#334155", fontSize: "12px" };
const errorBannerStyle = { background: "rgba(239,68,68,.08)", border: "1px solid rgba(239,68,68,.3)", borderRadius: "8px", padding: "12px 16px", color: "#fca5a5", fontSize: "13px", display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" };
const retryBtnStyle   = { background: "transparent", border: "1px solid #ef4444", color: "#ef4444", padding: "4px 12px", borderRadius: "6px", cursor: "pointer", fontSize: "12px" };
const refreshBtnStyle  = { background: "transparent", border: "1px solid #1e293b", color: "#94a3b8", padding: "7px 14px", borderRadius: "8px", cursor: "pointer", fontSize: "12px" };
const judgeBannerStyle = { display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "12px", padding: "12px 24px", background: "rgba(99,102,241,0.06)", borderBottom: "1px solid rgba(99,102,241,0.15)" };
const noPositionsBoxStyle = { textAlign: "center", padding: "48px 24px", background: "#0f172a", border: "1px solid #1e293b", borderRadius: "16px", marginBottom: "20px" };
const liveHintStyle   = { display: "inline-block", background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.2)", borderRadius: "8px", padding: "10px 16px", fontSize: "13px", maxWidth: "520px", lineHeight: 1.6 };

const modeIndicatorStyle = (isDemo) => ({
  display: "flex", alignItems: "center", gap: "6px",
  background: isDemo ? "rgba(245,158,11,0.08)" : "rgba(34,197,94,0.08)",
  border: `1px solid ${isDemo ? "rgba(245,158,11,0.25)" : "rgba(34,197,94,0.25)"}`,
  color: isDemo ? "#f59e0b" : "#22c55e",
  padding: "5px 12px", borderRadius: "20px",
});
