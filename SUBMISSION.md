# Hackathon Submission — PythGuard

> Copy this file's content into a new topic on the Pyth Developer Forum
> under the Pyth Community Hackathon category.

---

## [PythGuard — DeFi Liquidation Risk Monitor for Solana]

**Team:** @your-discord-handle
**Wallet:** your-solana-wallet-address

---

## Answer Capsule (40–60 words)

PythGuard uses Pyth Price Feeds and Pyth Pro confidence intervals to monitor
open lending positions on Solana in real time. It computes a 0–100 risk score
using the oracle's confidence interval — a signal most DeFi apps ignore — to
warn users before liquidation happens, not after. Supports Marginfi and Kamino.

---

## What It Does

PythGuard is a real-time risk monitor for Solana DeFi lending positions.
Users connect their wallet and see a live risk score for each open position
on Marginfi and Kamino.

The key insight: Pyth publishes not just a price, but also how *certain* it is
about that price (the confidence interval). When confidence widens, the market
is disagreeing on price — exactly when liquidations spike. PythGuard makes this
visible before it becomes a problem.

---

## Pyth Features Used

- **Pyth Price Feeds (on-chain):** Real-time price + confidence interval for
  SOL, BTC, ETH, USDC, JitoSOL read directly from Solana program accounts.
  The confidence field is the core signal of the risk engine.

- **Pyth Pro MCP Server:** `get_latest_price` with `real_time` channel for
  institutional-grade prices. `get_candlestick_data` for 30-minute confidence
  ratio history used in volatility trend scoring.

---

## How the Risk Score Works

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

- **Rust** — On-chain reader: reads Pyth price feed accounts + Marginfi positions
  from Solana RPC, exposes JSON over internal HTTP
- **Python (FastAPI)** — Risk Engine: computes scores, calls Pyth Pro MCP,
  exposes REST API
- **Node.js** — Marginfi SDK reader using official @mrgnlabs/marginfi-client-v2
- **React** — Dashboard: wallet connect, live risk meters, confidence chart

---

## Demo

Live demo (no wallet needed): https://pythguard.your-deployment.com

GitHub: https://github.com/your-handle/pythguard

---

## Content Links

- Reddit post: https://reddit.com/r/solana/comments/your-post
- Dev.to article: https://dev.to/your-handle/pythguard

---

## License

Apache 2.0
