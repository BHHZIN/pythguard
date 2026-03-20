# PythGuard — Architecture

## Overview

PythGuard is a three-layer system: a **Rust on-chain reader**, a **Python Risk Engine**, and a **React frontend**. Each layer has a single responsibility and communicates via clean JSON interfaces.

```
┌─────────────────────────────────────────────────────────┐
│  React Frontend                                         │
│  • Connects Phantom/Solflare wallet                     │
│  • Polls backend every 15s for risk scores              │
│  • Renders RiskMeter gauges and PositionCards           │
└────────────────────┬────────────────────────────────────┘
                     │ REST (JSON)
┌────────────────────▼────────────────────────────────────┐
│  Python Backend (FastAPI)                               │
│  • Risk Engine: computes 0–100 score per position       │
│  • Pyth Pro MCP Client: fetches confidence + history    │
│  • REST API: /risk, /feeds/status, /feeds/chart         │
└──────────┬─────────────────────────┬────────────────────┘
           │ Internal HTTP           │ HTTPS
┌──────────▼───────────┐  ┌──────────▼──────────────────┐
│  Rust Reader (Axum)  │  │  Pyth Pro MCP Server        │
│  • Reads Solana RPC  │  │  mcp.pyth.network/mcp       │
│  • Pyth on-chain     │  │  get_latest_price           │
│    price + confidence│  │  get_candlestick_data       │
│  • Marginfi positions│  └─────────────────────────────┘
└──────────┬───────────┘
           │ Solana RPC
┌──────────▼───────────────────────────────────────────── ┐
│  Solana Mainnet                                         │
│  • Pyth price feed accounts (price + confidence)        │
│  • Marginfi / Kamino position accounts                  │
└─────────────────────────────────────────────────────────┘
```

---

## Why Confidence Intervals?

Every Pyth price feed publishes two values most apps ignore:

```
price:      $182.40   ← what everyone reads
confidence: ± $0.18   ← what PythGuard reads
```

The **confidence interval** represents the spread of prices reported by Pyth's data providers. When it widens:
- Market makers are disagreeing on price
- Liquidity is fragmenting
- Volatility is increasing

This is a **leading indicator** of price instability — it often rises before prices actually move. PythGuard turns this into an actionable risk signal.

---

## Risk Score Formula

```
Score = (collateral_ratio_component × 0.40)
      + (confidence_interval_component × 0.40)
      + (volatility_trend_component × 0.20)
```

### Collateral Ratio Component (40%)
```
safety_buffer = collateral_ratio - liquidation_threshold
score = (1 - safety_buffer / max_buffer) × 100
```
- Score = 0 when position is 2× above threshold
- Score = 100 when at or below threshold

### Confidence Interval Component (40%)
```
confidence_ratio = confidence / |price|
score = lerp(0, 100, between thresholds 0.001 and 0.005)
```
- Below 0.1% → score = 0 (oracle is certain)
- Above 0.5% → score = 100 (oracle is very uncertain)

### Volatility Trend Component (20%)
```
trend = mean(recent_5) / mean(baseline_5) - 1
score = min(trend / 0.5, 1.0) × 100
```
- Uses 30-minute confidence ratio history from Pyth Pro
- A 50% rise in confidence ratio over 30 min → score = 100

---

## Data Flow (per request)

```
1. Frontend: GET /api/v1/risk/{wallet}

2. Python backend calls Rust reader:
   GET http://localhost:8001/payload/{wallet}

3. Rust reader:
   a. Reads Solana RPC for Marginfi accounts owned by wallet
   b. Reads Pyth on-chain accounts for price + confidence
   c. Returns RiskInputPayload JSON

4. Python backend calls Pyth Pro MCP:
   - get_latest_price (real_time channel) for confidence ratios
   - get_candlestick_data (1-min, 30 lookback) for trend

5. Risk Engine computes score for each position

6. FastAPI returns WalletRiskSummary JSON

7. Frontend renders RiskMeter + PositionCards
```

---

## Security Considerations

- **No private keys** — PythGuard only reads public on-chain data
- **Stale price guard** — prices older than 60 seconds are rejected
- **Zero confidence guard** — prices with confidence = 0 are rejected
- **Pyth Pro token** — stored server-side only, never exposed to frontend
- **Read-only CORS** — frontend only allows GET requests

---

## Protocols Supported

| Protocol | Status | Notes |
|----------|--------|-------|
| Marginfi | ✅ | Primary integration |
| Kamino | 🔲 Planned | Same architecture, different IDL |
| Solend | 🔲 Planned | Legacy protocol, lower priority |
