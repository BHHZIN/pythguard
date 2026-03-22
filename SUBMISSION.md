# Hackathon Submission — PythGuard

> Copy this file's content into a new topic on the Pyth Developer Forum
> under the Pyth Community Hackathon category.

---

## [PythGuard — DeFi Liquidation Risk Monitor for Solana]

**Team:** @BHHZIN
**Wallet:** your-solana-wallet-address-here

---

## Answer Capsule (40–60 words)

PythGuard uses Pyth Price Feeds and Pyth Pro confidence intervals to monitor
open lending positions on Solana in real time. It computes a 0–100 risk score
using the oracle's confidence interval — a signal most DeFi apps ignore — to
warn users before liquidation happens, not after. Supports Marginfi and Kamino.

---

## Note for Judges

**Demo Mode** (default, no wallet needed) showcases all features with
simulated Pyth-style confidence intervals that update in real time — feed bar,
risk gauges, confidence charts, alert messages.

**Live Mode** activates when connecting a Phantom wallet with active lending
or borrowing positions on Marginfi or Kamino. Without open positions, the app
correctly shows "No positions found" — this is expected behavior, not a bug.

---

## What It Does

PythGuard is a real-time risk monitor for Solana DeFi lending positions.
Users connect their wallet and see a live risk score for each open position
on Marginfi and Kamino.

The key insight: Pyth publishes not just a price, but also how *certain* it is
about that price (the confidence interval). When confidence widens, the market
is disagreeing on price — exactly when liquidations spike. PythGuard makes this
visible before it becomes a problem.

Notably, Marginfi itself uses Pyth confidence intervals internally when
calculating liquidation thresholds (bottom of the 95% confidence band).
PythGuard surfaces that same signal directly to users.

---

## Pyth Features Used

- **Pyth Price Feeds (on-chain):** Real-time price + confidence interval for
  SOL, BTC, ETH, USDC, JitoSOL read directly from Solana program accounts.
  The confidence field is the core signal of the risk engine.

- **Pyth Pro MCP Server:** `get_latest_price` with `real_time` channel for
  institutional-grade prices. `get_candlestick_data` for 30-minute confidence
  ratio history used in volatility trend scoring.

---

## Risk Score Formula

```
Score (0–100) =
  Collateral ratio component  × 40%   (how close to liquidation threshold)
  Confidence interval component × 40% (Pyth oracle uncertainty level)
  Volatility trend component  × 20%   (is confidence rising over 30 min?)
```

Score ≥ 75 → HIGH (act immediately)
Score ≥ 45 → MEDIUM (monitor closely)
Score < 45 → LOW (healthy)

---

## Technical Stack

- **Rust** — On-chain reader: reads Pyth price feed accounts + Marginfi
  positions from Solana RPC, exposes JSON over internal HTTP
- **Python (FastAPI)** — Risk Engine: computes scores, calls Pyth Pro MCP,
  exposes REST API
- **Node.js** — Marginfi SDK reader using official @mrgnlabs/marginfi-client-v2
- **React** — Dashboard: wallet connect, DEMO/LIVE toggle, live risk meters,
  confidence chart per position

---

## Links

- **Live Demo:** https://pythguard.vercel.app *(update with real URL)*
- **GitHub:** https://github.com/BHHZIN/pythguard

---

## Content Links

- Reddit post: *(add link after posting)*
- Dev.to article: *(optional)*

---

## License

Apache 2.0
