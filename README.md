# 🛡️ PythGuard — DeFi Risk Monitor for Solana

> Real-time liquidation risk monitoring for lending/borrowing positions on Solana,
> powered by **Pyth Price Feeds** and **Pyth Pro confidence intervals**.

**Pyth Community Hackathon 2026 submission.**

---

## ⚡ Live Demo

**→ [pythguard.vercel.app](https://pythguard.vercel.app)** *(update with real URL after deploy)*

> **For judges & reviewers:** Demo Mode is active by default — no wallet needed.
> It showcases all features with simulated Pyth-style data that updates in real time.
> **Live Mode** activates when you connect a Phantom wallet with active lending or
> borrowing positions on **Marginfi** or **Kamino**. Without open positions, the app
> correctly shows "No positions found".

---

## What PythGuard Does

Most DeFi users get liquidated not because prices crashed unexpectedly —
but because they had no warning. PythGuard monitors your open positions
on Marginfi and Kamino and computes a **Risk Score (0–100)** using three
Pyth-powered signals:

| Signal | Source | Weight |
|--------|--------|--------|
| Collateral ratio vs liquidation threshold | Pyth Price Feeds on-chain | 40% |
| **Oracle confidence interval** | Pyth `confidence` field | 40% |
| Confidence ratio trend (last 30 min) | Pyth Pro MCP `get_candlestick_data` | 20% |

The confidence interval is the key insight — **Pyth publishes not just a price,
but how certain it is.** When confidence rises, the market is unstable. Marginfi
itself uses this internally for liquidation thresholds. PythGuard exposes it to you.

---

## Features

- 🔴 **Live Risk Score** per position (0–100, LOW / MEDIUM / HIGH)
- 📊 **Confidence ratio chart** — 30-minute live chart per position (click ▼ Chart)
- 💥 **Liquidation buffer estimate** — "your SOL position is 12.4% from liquidation"
- 📡 **Live Pyth feed bar** — confidence ratios for all supported assets at a glance
- 🎭 **Demo Mode** — full dashboard works immediately, no wallet needed
- 🔔 **Telegram alerts** — DM when any position crosses HIGH risk (75+)
- 🔄 **DEMO / LIVE toggle** — seamless switch via wallet connect button
- 🔐 **Read-only** — PythGuard never requests signing permissions

---

## Quick Start — Windows

Double-click the scripts in order:

```
scripts/
├── 1_rodar_backend.bat    ← run first
├── 2_rodar_frontend.bat   ← run in second terminal
├── 3_rodar_testes.bat     ← optional: run tests
└── 4_alertas_telegram.bat ← optional: Telegram alerts
```

Before running: edit `.env` in the root folder and set:
```
PYTH_PRO_ACCESS_TOKEN=your_token_here
```

Then open http://localhost:3000 — Demo Mode loads automatically.

---

## Quick Start — Mac/Linux

```bash
# Backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp ../.env .env
uvicorn app.main:application --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
echo "VITE_BACKEND_URL=http://localhost:8000" > .env
npm run dev
```

Open http://localhost:3000

---

## Architecture

```
Frontend (React)
    ↓ REST polling every 10–15s
Python Backend (FastAPI)
    ↓ Internal HTTP
Rust Reader (Axum) + Marginfi JS Reader (@mrgnlabs SDK)
    ↓ Solana RPC
Pyth On-chain Price Feeds + Confidence Intervals
    +
Pyth Pro MCP Server (historical + real-time)
```

See [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) for full technical breakdown.

---

## Pyth Integration

| Feature | How PythGuard Uses It |
|---------|----------------------|
| **Price Feeds** | Collateral price for LTV calculation |
| **Confidence Interval** | Core risk signal — oracle uncertainty |
| **Pyth Pro `get_latest_price`** | Real-time confidence with `real_time` channel |
| **Pyth Pro `get_candlestick_data`** | 30-min confidence history for trend analysis |

---

## Running Tests

```bash
# Windows: double-click scripts/3_rodar_testes.bat

# Mac/Linux:
cd backend && source venv/bin/activate
pytest tests/ -v --cov=app/core
# 46 tests, 87% coverage
```

---

## Answer Capsule

> PythGuard uses Pyth Price Feeds and Pyth Pro confidence intervals to monitor
> open lending positions on Solana in real time. It computes a 0–100 risk score
> using the oracle's confidence interval — a signal most DeFi apps ignore — to
> warn users before liquidation happens, not after. Supports Marginfi and Kamino.

---

## License

Apache 2.0 — see [LICENSE](./LICENSE).
