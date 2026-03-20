# Contributing to PythGuard

PythGuard is an Apache 2.0 open source project. Contributions are welcome.

## Quick Setup

```bash
git clone https://github.com/your-handle/pythguard
cd pythguard
cp .env.example .env
# Fill in PYTH_PRO_ACCESS_TOKEN in .env

# Python backend
cd backend && pip install -r requirements.txt
uvicorn app.main:application --reload --port 8000

# Rust reader
cd rust && cargo run

# Frontend
cd frontend && npm install && npm run dev
```

## Project Structure

```
pythguard/
├── rust/              Solana on-chain reader (price feeds + positions)
├── backend/           Python Risk Engine + FastAPI REST API
│   └── app/
│       ├── core/      risk_engine.py, demo_data.py, telegram_alerts.py
│       ├── pyth/      mcp_client.py (Pyth Pro MCP integration)
│       ├── protocols/ marginfi_adapter.py
│       └── api/       routes/ schemas.py
├── marginfi_reader/   Node.js service using official @mrgnlabs SDK
├── frontend/          React dashboard
│   └── src/
│       ├── components/Dashboard/  RiskMeter, PositionCard, ConfidenceChart
│       ├── hooks/                 useRiskScore, useFeeds
│       └── pages/                 index.jsx
└── docs/              ARCHITECTURE.md, API.md
```

## Guidelines

- Run `pytest backend/tests/ -v` before submitting a PR
- Follow the naming conventions in `formatacao-e-boas-praticas-de-codigo` — no single-letter variables
- Every public function needs a docstring
- No secrets in code — use `.env` only

## Pyth Integration Notes

- Always validate `confidence > 0` before using a price
- Always check `publish_time` is within 60 seconds
- Use `Crypto.SYMBOL/USD` format for Pyth Pro MCP calls
- The confidence ratio threshold constants are in `backend/app/config.py`

## License

Apache 2.0 — you keep ownership of your contributions.
