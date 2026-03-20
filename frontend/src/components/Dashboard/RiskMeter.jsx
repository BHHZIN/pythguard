/**
 * RiskMeter component.
 *
 * Renders a circular gauge showing a risk score from 0–100.
 * Color transitions: green (low) → yellow (medium) → red (high).
 */

const GAUGE_RADIUS       = 80;
const GAUGE_STROKE_WIDTH = 14;
const GAUGE_CIRCUMFERENCE = 2 * Math.PI * GAUGE_RADIUS;
// Only show the top 75% of the circle (standard gauge shape)
const GAUGE_ARC_FRACTION = 0.75;
const GAUGE_ARC_LENGTH   = GAUGE_CIRCUMFERENCE * GAUGE_ARC_FRACTION;

/**
 * Maps a score 0–100 to an RGB color via green → yellow → red.
 * @param {number} riskScore
 * @returns {string} CSS color string
 */
function resolveScoreColor(riskScore) {
  if (riskScore >= 75) return "#ef4444"; // red-500
  if (riskScore >= 45) return "#f59e0b"; // amber-500
  return "#22c55e";                       // green-500
}

/**
 * @param {{
 *   riskScore: number,
 *   riskLevel: "LOW" | "MEDIUM" | "HIGH",
 *   label?: string
 * }} props
 */
export function RiskMeter({ riskScore, riskLevel, label = "Risk Score" }) {
  const scoreColor          = resolveScoreColor(riskScore);
  const filledArcLength     = GAUGE_ARC_LENGTH * (riskScore / 100);
  const remainingArcLength  = GAUGE_ARC_LENGTH - filledArcLength;
  // Rotate so the arc starts at bottom-left
  const gaugeRotationDegrees = 135;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "8px" }}>
      <svg width="200" height="160" viewBox="0 0 200 160">
        {/* Background arc (grey track) */}
        <circle
          cx="100" cy="110"
          r={GAUGE_RADIUS}
          fill="none"
          stroke="#1e293b"
          strokeWidth={GAUGE_STROKE_WIDTH}
          strokeDasharray={`${GAUGE_ARC_LENGTH} ${GAUGE_CIRCUMFERENCE}`}
          strokeDashoffset="0"
          strokeLinecap="round"
          transform={`rotate(${gaugeRotationDegrees} 100 110)`}
        />
        {/* Filled arc (score indicator) */}
        <circle
          cx="100" cy="110"
          r={GAUGE_RADIUS}
          fill="none"
          stroke={scoreColor}
          strokeWidth={GAUGE_STROKE_WIDTH}
          strokeDasharray={`${filledArcLength} ${GAUGE_CIRCUMFERENCE - filledArcLength}`}
          strokeDashoffset="0"
          strokeLinecap="round"
          transform={`rotate(${gaugeRotationDegrees} 100 110)`}
          style={{ transition: "stroke-dasharray 0.6s ease, stroke 0.6s ease" }}
        />
        {/* Score number */}
        <text
          x="100" y="108"
          textAnchor="middle"
          dominantBaseline="middle"
          fill={scoreColor}
          fontSize="32"
          fontWeight="700"
          fontFamily="monospace"
          style={{ transition: "fill 0.6s ease" }}
        >
          {Math.round(riskScore)}
        </text>
        {/* Risk level label */}
        <text
          x="100" y="135"
          textAnchor="middle"
          fill={scoreColor}
          fontSize="12"
          fontWeight="600"
          fontFamily="sans-serif"
          letterSpacing="2"
        >
          {riskLevel}
        </text>
      </svg>
      <span style={{ color: "#94a3b8", fontSize: "13px", letterSpacing: "1px" }}>
        {label}
      </span>
    </div>
  );
}
