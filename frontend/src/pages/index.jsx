/**
 * PythGuard — Main application page.
 *
 * Three modes:
 *   🟡 DEMO    — default, simulated data, no wallet needed
 *   🔵 WATCH   — enter any wallet address, view real positions (read-only)
 *   🟢 LIVE    — connect your own Phantom wallet
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
import { WatchWallet } from "../components/Wallet/WatchWallet";
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
  const [watchedWalletAddress, setWatchedWalletAddress]     = useState(null);
  const [confidenceHistories, setConfidenceHistories]       = useState({});
  const [showJudgeNotice, setShowJudgeNotice]               = useState(true);
  const [showWatchInput, setShowWatchInput]                  = useState(false);

  const {
    riskSummary,
    isLoadingRiskData,
    riskDataError,
    isDemoMode,
    isWatchMode,
    isLiveMode,
    refreshRiskData,
  } = useRiskScore(connectedWalletAddress, watchedWalletAddress);

  // Determine mode label and color
  const modeLabel = isLiveMode ? "LIVE MODE" : isWatchMode ? "WATCHING" : "DEMO MODE";
  const modeColor = isLiveMode ? "#22c55e" : isWatchMode ? "#60a5fa" : "#f59e0b";

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

  // Clear watch when own wallet connects
  useEffect(() => {
    if (connectedWalletAddress) {
      setWatchedWalletAddress(null);
      setShowWatchInput(false);
    }
  }, [connectedWalletAddress]);

  function handleWatch(address) {
    setWatchedWalletAddress(address);
    setShowWatchInput(false);
  }

  function handleClearWatch() {
    setWatchedWalletAddress(null);
  }

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

        <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap", justifyContent: "flex-end" }}>

          {/* Mode indicator */}
          <div style={modeIndicatorStyle(modeColor)}>
            <div style={{ width: "7px", height: "7px", borderRadius: "50%", background: modeColor, boxShadow: `0 0 6px ${modeColor}` }} />
            <span style={{ fontSize: "11px", fontWeight: 600, letterSpacing: "1px" }}>
              {modeLabel}
            </span>
          </div>

          {/* Watch wallet toggle */}
          {!isLiveMode && !isWatchMode && (
            <button
              onClick={() => setShowWatchInput(prev => !prev)}
              style={watchToggleButtonStyle}
              title="Watch any wallet address"
            >
              👁 Watch wallet
            </button>
          )}

          {/* Watch wallet input or active state */}
          {(showWatchInput || isWatchMode) && !isLiveMode && (
            <WatchWallet
              onWatch={handleWatch}
              onClear={handleClearWatch}
              currentWatchedAddress={watchedWalletAddress}
            />
          )}

          {/* Connect own wallet */}
          <ConnectWallet onWalletConnected={setConnectedWalletAddress} />
        </div>
      </header>

      {/* ── Judge Notice Banner ─────────────────────────── */}
      {showJudgeNotice && (
        <div style={judgeBannerStyle}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}>
            <span style={{ fontSize: "16px", flexShrink: 0 }}>ℹ️</span>
            <div>
              <span style={{ color: "#93c5fd", fontWeight: 600, fontSize: "13px" }}>For judges & reviewers: </span>
              <span style={{ color: "#94a3b8", fontSize: "13px" }}>
                <strong style={{ color: "#f59e0b" }}>Demo Mode</strong> — active by default, no wallet needed.{" "}
                <strong style={{ color: "#60a5fa" }}>Watch Mode</strong> — paste any Solana wallet to view real positions read-only.{" "}
                <strong style={{ color: "#22c55e" }}>Live Mode</strong> — connect your own Phantom wallet.
                Live & Watch modes require open positions on <strong style={{ color: "#e2e8f0" }}>Marginfi</strong> or <strong style={{ color: "#e2e8f0" }}>Kamino</strong>.
              </span>
            </div>
          </div>
          <button
            onClick={() => setShowJudgeNotice(false)}
            style={{ background: "transparent", border: "none", color: "#475569", cursor: "pointer", fontSize: "18px", flexShrink: 0 }}
          >×</button>
        </div>
      )}

      {/* ── Live Pyth feed bar ──────────────────────────── */}
      <FeedStatusBar isDemoMode={isDemoMode} />

      {/* ── Main content ───────────────────────────────── */}
      <main style={mainContentStyle}>

        {riskDataError && (
          <div style={errorBannerStyle}>
            ⚠️ {riskDataError}
            <button onClick={refreshRiskData} style={retryBtnStyle}>Retry</button>
          </div>
        )}

        {isLoadingRiskData && !riskSummary && (
          <EmptyState
            title="Loading risk data…"
            description={
              isWatchMode
                ? `Scanning positions for ${watchedWalletAddress?.slice(0,6)}…${watchedWalletAddress?.slice(-4)}`
                : "Fetching Pyth price feeds and confidence intervals."
            }
          />
        )}

        {riskSummary && (
          <>
            {/* Summary row */}
            <div style={summaryRowStyle}>
              <RiskMeter
                riskScore={riskSummary.highest_risk_score}
                riskLevel={riskSummary.overall_risk_level}
                label="Overall Risk"
              />
              <div style={{ display: "flex", gap: "24px", alignItems: "center", flexWrap: "wrap" }}>
                <SummaryMetric label="OPEN POSITIONS" value={riskSummary.position_count} />
                <SummaryMetric label="MODE" value={modeLabel} color={modeColor} />
                <SummaryMetric
                  label="WALLET"
                  value={
                    isLiveMode
                      ? `${connectedWalletAddress.slice(0,6)}…${connectedWalletAddress.slice(-4)}`
                      : isWatchMode
                      ? `${watchedWalletAddress.slice(0,6)}…${watchedWalletAddress.slice(-4)}`
                      : "Not connected"
                  }
                  mono
                />
                <SummaryMetric
                  label="LAST UPDATED"
                  value={new Date(riskSummary.computed_at_timestamp * 1000).toLocaleTimeString()}
                />
              </div>
              <button onClick={refreshRiskData} style={refreshBtnStyle}>↻ Refresh</button>
            </div>

            {/* No positions found */}
            {riskSummary.position_count === 0 && (
              <div style={noPositionsBoxStyle}>
                <div style={{ fontSize: "32px", marginBottom: "12px" }}>🔍</div>
                <h2 style={{ color: "#e2e8f0", margin: "0 0 10px", fontSize: "18px" }}>
                  No open positions found
                </h2>
                <p style={{ color: "#64748b", maxWidth: "500px", margin: "0 auto 16px", lineHeight: 1.6, fontSize: "14px" }}>
                  No active lending or borrowing positions detected on Marginfi or Kamino.
                </p>
                {(isWatchMode || isLiveMode) && (
                  <div style={liveHintStyle}>
                    <strong style={{ color: "#93c5fd" }}>Tip: </strong>
                    <span style={{ color: "#64748b" }}>
                      Try a wallet with open positions on{" "}
                      <a href="https://app.marginfi.com" target="_blank" rel="noopener noreferrer" style={{ color: "#6366f1" }}>Marginfi</a>
                      {" "}or{" "}
                      <a href="https://app.kamino.finance" target="_blank" rel="noopener noreferrer" style={{ color: "#6366f1" }}>Kamino</a>.
                      {" "}Or use the example wallets in the Watch input above.
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
        <a href="https://github.com/BHHZIN/pythguard" target="_blank" rel="noopener noreferrer" style={{ color: "#6366f1" }}>
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

const pageStyle        = { minHeight: "100vh", background: "#020817", color: "#e2e8f0", fontFamily: "'Inter', system-ui, sans-serif" };
const headerStyle      = { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "14px 24px", borderBottom: "1px solid #1e293b", background: "#020817", flexWrap: "wrap", gap: "10px" };
const mainContentStyle = { maxWidth: "900px", margin: "0 auto", padding: "28px 24px" };
const summaryRowStyle  = { display: "flex", alignItems: "center", justifyContent: "space-between", background: "#0f172a", border: "1px solid #1e293b", borderRadius: "16px", padding: "18px 28px", marginBottom: "24px", flexWrap: "wrap", gap: "16px" };
const footerStyle      = { display: "flex", justifyContent: "space-between", padding: "18px 24px", borderTop: "1px solid #1e293b", color: "#334155", fontSize: "12px" };
const errorBannerStyle = { background: "rgba(239,68,68,.08)", border: "1px solid rgba(239,68,68,.3)", borderRadius: "8px", padding: "12px 16px", color: "#fca5a5", fontSize: "13px", display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" };
const retryBtnStyle    = { background: "transparent", border: "1px solid #ef4444", color: "#ef4444", padding: "4px 12px", borderRadius: "6px", cursor: "pointer", fontSize: "12px" };
const refreshBtnStyle  = { background: "transparent", border: "1px solid #1e293b", color: "#94a3b8", padding: "7px 14px", borderRadius: "8px", cursor: "pointer", fontSize: "12px" };
const judgeBannerStyle = { display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "12px", padding: "12px 24px", background: "rgba(99,102,241,0.06)", borderBottom: "1px solid rgba(99,102,241,0.15)" };
const noPositionsBoxStyle = { textAlign: "center", padding: "48px 24px", background: "#0f172a", border: "1px solid #1e293b", borderRadius: "16px", marginBottom: "20px" };
const liveHintStyle    = { display: "inline-block", background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.2)", borderRadius: "8px", padding: "10px 16px", fontSize: "13px", maxWidth: "520px", lineHeight: 1.6 };
const watchToggleButtonStyle = { background: "transparent", border: "1px solid #1e293b", borderRadius: "8px", color: "#64748b", fontSize: "12px", padding: "6px 12px", cursor: "pointer" };
const modeIndicatorStyle = (color) => ({
  display: "flex", alignItems: "center", gap: "6px",
  background: `${color}14`,
  border: `1px solid ${color}40`,
  color: color,
  padding: "5px 12px", borderRadius: "20px",
});
