/**
 * FeedStatusBar component.
 *
 * Horizontal bar showing live Pyth feed confidence ratios.
 * Supports both live mode (real Pyth Pro data) and demo mode.
 */
import { useFeeds } from "../../hooks/useFeeds";

const RISK_COLORS = { LOW: "#22c55e", MEDIUM: "#f59e0b", HIGH: "#ef4444" };

/**
 * @param {{ isDemoMode?: boolean }} props
 */
export function FeedStatusBar({ isDemoMode = false }) {
  const { feedStatuses, isLoadingFeeds } = useFeeds(isDemoMode);

  if (isLoadingFeeds && feedStatuses.length === 0) {
    return (
      <div style={containerStyle}>
        <span style={{ color: "#334155", fontSize: "12px" }}>Loading feeds…</span>
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      <span style={{ color: "#334155", fontSize: "10px", letterSpacing: "1px", flexShrink: 0 }}>
        PYTH FEEDS
      </span>
      {isDemoMode && (
        <span style={{ color: "#334155", fontSize: "10px", marginRight: "4px" }}>DEMO ·</span>
      )}
      <div style={{ display: "flex", gap: "20px", overflowX: "auto" }}>
        {feedStatuses.map(feedStatus => (
          <FeedPill key={feedStatus.asset_symbol} feedStatus={feedStatus} />
        ))}
      </div>
    </div>
  );
}

function FeedPill({ feedStatus }) {
  const confColor = RISK_COLORS[feedStatus.risk_level_from_confidence] || "#22c55e";
  const confPct   = (feedStatus.confidence_ratio * 100).toFixed(3);
  const symbol    = feedStatus.asset_symbol.replace("Crypto.", "").replace("/USD", "");

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "1px", flexShrink: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
        <div style={{ width: "5px", height: "5px", borderRadius: "50%", background: feedStatus.is_feed_fresh ? "#22c55e" : "#ef4444" }} />
        <span style={{ color: "#cbd5e1", fontSize: "12px", fontWeight: 600 }}>{symbol}</span>
      </div>
      <span style={{ color: "#94a3b8", fontSize: "11px", fontFamily: "monospace" }}>
        ${feedStatus.normalized_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </span>
      <span style={{ color: confColor, fontSize: "10px", fontFamily: "monospace" }}>
        ±{confPct}%
      </span>
    </div>
  );
}

const containerStyle = {
  display: "flex", alignItems: "center", gap: "16px",
  padding: "8px 24px", background: "#0f172a",
  borderBottom: "1px solid #1e293b", position: "sticky", top: 0, zIndex: 10,
};
