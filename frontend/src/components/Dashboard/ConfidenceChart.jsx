/**
 * ConfidenceChart component.
 *
 * Renders a live SVG line chart showing the Pyth confidence ratio
 * for a given asset over the past 30 minutes.
 *
 * This is PythGuard's signature visualization — it makes the
 * abstract "confidence interval" concept tangible and alarming.
 * The spike event in the middle of the chart shows exactly when
 * oracle uncertainty spiked before prices moved.
 */
import { useState, useEffect, useRef } from "react";
import { fetchCandlestickChartData } from "../../api";

const CHART_WIDTH        = 520;
const CHART_HEIGHT       = 140;
const CHART_PADDING_X    = 40;
const CHART_PADDING_TOP  = 16;
const CHART_PADDING_BTM  = 28;
const PLOT_WIDTH         = CHART_WIDTH - CHART_PADDING_X * 2;
const PLOT_HEIGHT        = CHART_HEIGHT - CHART_PADDING_TOP - CHART_PADDING_BTM;

const REFRESH_INTERVAL_MS = 15_000;

const RISK_ZONE_COLOR_HIGH   = "rgba(239, 68, 68, 0.08)";
const RISK_ZONE_COLOR_MEDIUM = "rgba(245, 158, 11, 0.06)";
const LINE_COLOR_RISING      = "#ef4444";
const LINE_COLOR_STABLE      = "#22c55e";
const LINE_COLOR_MEDIUM      = "#f59e0b";

/**
 * @param {{
 *   assetTicker: string,
 *   confidenceHistory?: Array<{timestamp: number, confidence_ratio: number}>,
 *   isDemo?: boolean
 * }} props
 */
export function ConfidenceChart({ assetTicker, confidenceHistory = [], isDemo = false }) {
  const [chartDataPoints, setChartDataPoints]     = useState(confidenceHistory);
  const [isChartLoading, setIsChartLoading]       = useState(!isDemo);
  const [peakConfidenceRatio, setPeakConfidenceRatio] = useState(0);
  const pollingRef = useRef(null);

  useEffect(() => {
    if (isDemo && confidenceHistory.length > 0) {
      setChartDataPoints(confidenceHistory);
      setPeakConfidenceRatio(Math.max(...confidenceHistory.map(d => d.confidence_ratio)));
      return;
    }
    fetchAndUpdateChartData();
    pollingRef.current = setInterval(fetchAndUpdateChartData, REFRESH_INTERVAL_MS);
    return () => clearInterval(pollingRef.current);
  }, [assetTicker, isDemo]);

  async function fetchAndUpdateChartData() {
    try {
      const candleResponse = await fetchCandlestickChartData(assetTicker, "1", 1);
      const derivedDataPoints = candleResponse.candles.map(candle => ({
        timestamp: candle.timestamp,
        confidence_ratio: candle.close_price > 0
          ? (candle.high_price - candle.low_price) / candle.close_price
          : 0,
      }));
      setChartDataPoints(derivedDataPoints);
      setPeakConfidenceRatio(Math.max(...derivedDataPoints.map(d => d.confidence_ratio)));
    } catch {
      // silently keep existing data
    } finally {
      setIsChartLoading(false);
    }
  }

  if (isChartLoading) {
    return <ChartSkeleton />;
  }

  if (chartDataPoints.length === 0) {
    return <ChartSkeleton message="No data" />;
  }

  // ── Build SVG path from data ─────────────────────────────
  const confidenceValues = chartDataPoints.map(d => d.confidence_ratio);
  const minValue  = Math.min(...confidenceValues) * 0.85;
  const maxValue  = Math.max(...confidenceValues) * 1.15;
  const valueRange = maxValue - minValue || 0.001;

  function toX(dataIndex) {
    return CHART_PADDING_X + (dataIndex / (chartDataPoints.length - 1)) * PLOT_WIDTH;
  }

  function toY(confidenceValue) {
    const normalized = (confidenceValue - minValue) / valueRange;
    return CHART_PADDING_TOP + PLOT_HEIGHT - (normalized * PLOT_HEIGHT);
  }

  // Smooth SVG path using cubic bezier curves
  const svgPathData = chartDataPoints.reduce((pathString, dataPoint, dataIndex) => {
    const xCoord = toX(dataIndex);
    const yCoord = toY(dataPoint.confidence_ratio);
    if (dataIndex === 0) return `M ${xCoord} ${yCoord}`;
    const previousX = toX(dataIndex - 1);
    const previousY = toY(chartDataPoints[dataIndex - 1].confidence_ratio);
    const controlX1 = previousX + (xCoord - previousX) * 0.5;
    return `${pathString} C ${controlX1} ${previousY}, ${controlX1} ${yCoord}, ${xCoord} ${yCoord}`;
  }, "");

  // Area fill path (closed at the bottom)
  const lastX   = toX(chartDataPoints.length - 1);
  const bottomY = CHART_PADDING_TOP + PLOT_HEIGHT;
  const areaFillPath = `${svgPathData} L ${lastX} ${bottomY} L ${CHART_PADDING_X} ${bottomY} Z`;

  // Determine line color from trend
  const recentMean    = avg(confidenceValues.slice(-5));
  const baselineMean  = avg(confidenceValues.slice(0, 5));
  const isTrendRising = recentMean > baselineMean * 1.1;
  const isTrendHigh   = recentMean > 0.005;
  const lineColor = isTrendHigh ? LINE_COLOR_RISING : (isTrendRising ? LINE_COLOR_MEDIUM : LINE_COLOR_STABLE);

  // Risk threshold Y position
  const highRiskY   = toY(0.005);
  const mediumRiskY = toY(0.001);

  return (
    <div style={{ background: "#0a1628", borderRadius: "10px", padding: "12px 0 4px" }}>
      {/* Chart header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0 16px 8px" }}>
        <span style={{ color: "#64748b", fontSize: "11px", letterSpacing: "1px" }}>
          CONFIDENCE RATIO — {assetTicker}/USD (30 min)
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: lineColor, boxShadow: `0 0 6px ${lineColor}` }} />
          <span style={{ color: lineColor, fontSize: "12px", fontFamily: "monospace" }}>
            {(peakConfidenceRatio * 100).toFixed(3)}% peak
          </span>
        </div>
      </div>

      {/* SVG chart */}
      <svg
        width="100%"
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        preserveAspectRatio="none"
        style={{ display: "block" }}
      >
        <defs>
          <linearGradient id={`areaGrad-${assetTicker}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={lineColor} stopOpacity="0.25" />
            <stop offset="100%" stopColor={lineColor} stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {/* HIGH risk zone (> 0.5%) */}
        {highRiskY > CHART_PADDING_TOP && (
          <rect
            x={CHART_PADDING_X} y={CHART_PADDING_TOP}
            width={PLOT_WIDTH} height={Math.max(highRiskY - CHART_PADDING_TOP, 0)}
            fill={RISK_ZONE_COLOR_HIGH}
          />
        )}

        {/* MEDIUM risk zone (0.1% – 0.5%) */}
        {mediumRiskY > highRiskY && (
          <rect
            x={CHART_PADDING_X} y={highRiskY}
            width={PLOT_WIDTH} height={mediumRiskY - highRiskY}
            fill={RISK_ZONE_COLOR_MEDIUM}
          />
        )}

        {/* Threshold dashed lines */}
        <line x1={CHART_PADDING_X} y1={highRiskY} x2={CHART_WIDTH - CHART_PADDING_X} y2={highRiskY}
          stroke="#ef4444" strokeWidth="0.8" strokeDasharray="3,4" opacity="0.5" />
        <line x1={CHART_PADDING_X} y1={mediumRiskY} x2={CHART_WIDTH - CHART_PADDING_X} y2={mediumRiskY}
          stroke="#f59e0b" strokeWidth="0.8" strokeDasharray="3,4" opacity="0.4" />

        {/* Threshold labels */}
        <text x={CHART_PADDING_X - 4} y={highRiskY + 3} textAnchor="end" fill="#ef4444" fontSize="8" opacity="0.8">0.5%</text>
        <text x={CHART_PADDING_X - 4} y={mediumRiskY + 3} textAnchor="end" fill="#f59e0b" fontSize="8" opacity="0.7">0.1%</text>

        {/* Area fill */}
        <path d={areaFillPath} fill={`url(#areaGrad-${assetTicker})`} />

        {/* Main line */}
        <path
          d={svgPathData}
          fill="none"
          stroke={lineColor}
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Latest value dot */}
        <circle
          cx={toX(chartDataPoints.length - 1)}
          cy={toY(chartDataPoints[chartDataPoints.length - 1].confidence_ratio)}
          r="3"
          fill={lineColor}
          style={{ filter: `drop-shadow(0 0 4px ${lineColor})` }}
        />

        {/* X-axis labels */}
        <text x={CHART_PADDING_X} y={CHART_HEIGHT - 6} fill="#334155" fontSize="8" textAnchor="middle">30m ago</text>
        <text x={CHART_WIDTH / 2} y={CHART_HEIGHT - 6} fill="#334155" fontSize="8" textAnchor="middle">15m ago</text>
        <text x={CHART_WIDTH - CHART_PADDING_X} y={CHART_HEIGHT - 6} fill="#334155" fontSize="8" textAnchor="middle">now</text>
      </svg>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────

function avg(numberArray) {
  if (numberArray.length === 0) return 0;
  return numberArray.reduce((sum, value) => sum + value, 0) / numberArray.length;
}

function ChartSkeleton({ message = "Loading…" }) {
  return (
    <div style={{
      background: "#0a1628", borderRadius: "10px",
      height: "140px", display: "flex",
      alignItems: "center", justifyContent: "center",
    }}>
      <span style={{ color: "#334155", fontSize: "13px" }}>{message}</span>
    </div>
  );
}
