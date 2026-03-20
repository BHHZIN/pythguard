/**
 * PositionCard component.
 *
 * Displays a single lending/borrowing position with its
 * risk score, confidence ratio, liquidation estimate,
 * and an embedded 30-minute confidence ratio chart.
 */
import { useState } from "react";
import { RiskMeter } from "./RiskMeter";
import { ConfidenceChart } from "./ConfidenceChart";

const RISK_LEVEL_BORDER_COLORS = {
  HIGH:   "#ef4444",
  MEDIUM: "#f59e0b",
  LOW:    "#22c55e",
};

const RISK_LEVEL_BG_COLORS = {
  HIGH:   "rgba(239, 68, 68, 0.05)",
  MEDIUM: "rgba(245, 158, 11, 0.05)",
  LOW:    "rgba(34, 197, 94, 0.05)",
};

/**
 * @param {{
 *   position: import("../../api").PositionRisk,
 *   confidenceHistory?: Array,
 *   isDemo?: boolean
 * }} props
 */
export function PositionCard({ position, confidenceHistory = [], isDemo = false }) {
  const [isChartExpanded, setIsChartExpanded] = useState(false);

  const borderColor = RISK_LEVEL_BORDER_COLORS[position.risk_level];
  const bgColor     = RISK_LEVEL_BG_COLORS[position.risk_level];
  const confidencePct = (position.current_confidence_ratio * 100).toFixed(3);

  // Extract ticker from "SOL/USD" → "SOL"
  const assetTicker = position.collateral_asset.replace("/USD", "");

  return (
    <div style={{
      border: `1px solid ${borderColor}`,
      borderLeft: `4px solid ${borderColor}`,
      background: bgColor,
      borderRadius: "12px",
      overflow: "hidden",
      transition: "border-color 0.4s ease",
    }}>
      {/* ── Main row ─────────────────────────────────────── */}
      <div style={{ padding: "20px 24px", display: "flex", alignItems: "center", gap: "28px" }}>
        {/* Risk gauge */}
        <div style={{ flexShrink: 0 }}>
          <RiskMeter
            riskScore={position.composite_risk_score}
            riskLevel={position.risk_level}
            label={position.protocol_name}
          />
        </div>

        {/* Position details */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <h3 style={{ margin: "0 0 12px", color: "#f1f5f9", fontSize: "16px", fontWeight: 600 }}>
            {position.collateral_asset} → {position.borrowed_asset}
          </h3>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px 24px" }}>
            <MetricRow
              label="Liquidation Buffer"
              value={`${position.estimated_liquidation_price_drop_percent.toFixed(1)}%`}
              isWarning={position.estimated_liquidation_price_drop_percent < 20}
              isDanger={position.estimated_liquidation_price_drop_percent < 10}
            />
            <MetricRow
              label="Confidence Ratio"
              value={`${confidencePct}%`}
              isWarning={position.current_confidence_ratio >= 0.001}
              isDanger={position.current_confidence_ratio >= 0.005}
            />
            <MetricRow
              label="Collateral Score"
              value={`${position.collateral_ratio_score.toFixed(0)}/100`}
            />
            <MetricRow
              label="Oracle Score"
              value={`${position.confidence_interval_score.toFixed(0)}/100`}
            />
          </div>

          {/* Confidence trend badge */}
          {position.is_confidence_trending_upward && (
            <div style={{
              marginTop: "10px",
              display: "inline-block",
              padding: "4px 10px",
              background: "rgba(245,158,11,0.1)",
              border: "1px solid rgba(245,158,11,0.3)",
              borderRadius: "6px",
              color: "#fbbf24",
              fontSize: "12px",
            }}>
              ↑ Oracle confidence rising — market uncertainty increasing
            </div>
          )}

          <p style={{ margin: "10px 0 0", color: "#94a3b8", fontSize: "13px", lineHeight: 1.5 }}>
            {position.alert_message}
          </p>
        </div>

        {/* Chart toggle button */}
        <button
          onClick={() => setIsChartExpanded(prev => !prev)}
          style={{
            flexShrink: 0,
            background: "transparent",
            border: `1px solid ${isChartExpanded ? borderColor : "#1e293b"}`,
            borderRadius: "8px",
            color: isChartExpanded ? borderColor : "#475569",
            padding: "8px 14px",
            cursor: "pointer",
            fontSize: "12px",
            transition: "all 0.2s",
          }}
          title="Toggle confidence chart"
        >
          {isChartExpanded ? "▲ Chart" : "▼ Chart"}
        </button>
      </div>

      {/* ── Expandable confidence chart ───────────────────── */}
      {isChartExpanded && (
        <div style={{ borderTop: `1px solid ${borderColor}44`, padding: "0 24px 16px" }}>
          <ConfidenceChart
            assetTicker={assetTicker}
            confidenceHistory={confidenceHistory}
            isDemo={isDemo}
          />
        </div>
      )}
    </div>
  );
}

/** Single label/value metric row. */
function MetricRow({ label, value, isWarning = false, isDanger = false }) {
  const valueColor = isDanger ? "#ef4444" : isWarning ? "#f59e0b" : "#e2e8f0";
  return (
    <div>
      <span style={{ color: "#64748b", fontSize: "11px", display: "block", marginBottom: "2px" }}>
        {label}
      </span>
      <span style={{
        color: valueColor,
        fontSize: "14px",
        fontWeight: 600,
        fontFamily: "monospace",
        transition: "color 0.4s",
      }}>
        {value}
      </span>
    </div>
  );
}
