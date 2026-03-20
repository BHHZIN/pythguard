# PythGuard — API Reference

Base URL: `http://localhost:8000`
All endpoints return JSON. All errors follow the standard error shape.

---

## GET `/api/v1/risk/{wallet_address}`

Returns the full risk summary for all open lending/borrowing positions
found for the given Solana wallet address.

**Parameters**

| Name | In | Type | Description |
|------|----|------|-------------|
| `wallet_address` | path | string | Solana base58 wallet address |

**Example Request**
```
GET /api/v1/risk/4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU
```

**Example Response — 200 OK**
```json
{
  "wallet_address": "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU",
  "overall_risk_level": "MEDIUM",
  "highest_risk_score": 61.4,
  "position_count": 2,
  "computed_at_timestamp": 1743200000,
  "positions": [
    {
      "wallet_address": "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU",
      "protocol_name": "marginfi",
      "collateral_asset": "SOL/USD",
      "borrowed_asset": "USDC/USD",
      "composite_risk_score": 61.4,
      "collateral_ratio_score": 48.2,
      "confidence_interval_score": 72.0,
      "volatility_trend_score": 55.0,
      "risk_level": "MEDIUM",
      "estimated_liquidation_price_drop_percent": 24.5,
      "current_confidence_ratio": 0.0038,
      "is_confidence_trending_upward": true,
      "alert_message": "🟡 MEDIUM RISK: SOL/USD position has 24.5% buffer before liquidation. Oracle confidence is rising — market uncertainty increasing. Monitor closely."
    }
  ]
}
```

**Error Responses**

| Status | Meaning |
|--------|---------|
| 504 | Rust reader timed out (Solana RPC slow) |
| 502 | Failed to fetch on-chain data |

---

## GET `/api/v1/feeds/status`

Returns current price and confidence ratio for all supported Pyth feeds.

**Example Response — 200 OK**
```json
[
  {
    "asset_symbol": "Crypto.SOL/USD",
    "normalized_price": 182.40,
    "confidence_ratio": 0.00098,
    "risk_level_from_confidence": "LOW",
    "publish_timestamp": 1743200000,
    "is_feed_fresh": true
  },
  {
    "asset_symbol": "Crypto.BTC/USD",
    "normalized_price": 84321.50,
    "confidence_ratio": 0.00041,
    "risk_level_from_confidence": "LOW",
    "publish_timestamp": 1743200001,
    "is_feed_fresh": true
  }
]
```

---

## GET `/api/v1/feeds/chart/{asset_ticker}`

Returns OHLC candlestick data for a single asset.

**Parameters**

| Name | In | Type | Default | Description |
|------|----|------|---------|-------------|
| `asset_ticker` | path | string | — | SOL, BTC, ETH, USDC, JITOSOL |
| `resolution` | query | string | `"5"` | Candle size in minutes |
| `lookback_hours` | query | int | `24` | How far back to fetch (max 168) |

**Example Request**
```
GET /api/v1/feeds/chart/SOL?resolution=5&lookback_hours=6
```

**Example Response — 200 OK**
```json
{
  "symbol": "Crypto.SOL/USD",
  "resolution": "5",
  "is_truncated": false,
  "candles": [
    {
      "timestamp": 1743196800,
      "open_price": 181.20,
      "high_price": 183.50,
      "low_price": 180.90,
      "close_price": 182.40,
      "volume": null
    }
  ]
}
```

---

## GET `/health`

Returns 200 OK when the backend is running.

```json
{
  "status": "ok",
  "service": "pythguard-backend",
  "timestamp": 1743200000
}
```

---

## Standard Error Shape

All 4xx and 5xx responses use this format:

```json
{
  "error_code": "RUST_READER_TIMEOUT",
  "error_message": "Rust reader timed out — Solana RPC may be slow",
  "details": null
}
```

---

## Risk Score Thresholds

| Score | Level | Meaning |
|-------|-------|---------|
| 0 – 44 | 🟢 LOW | Position is healthy |
| 45 – 74 | 🟡 MEDIUM | Monitor closely |
| 75 – 100 | 🔴 HIGH | Act immediately |

## Confidence Ratio Thresholds

| Ratio | Level | Meaning |
|-------|-------|---------|
| < 0.1% | 🟢 LOW | Oracle is certain |
| 0.1% – 0.5% | 🟡 MEDIUM | Some uncertainty |
| > 0.5% | 🔴 HIGH | Oracle is very uncertain |
