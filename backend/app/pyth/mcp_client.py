"""
Pyth Pro MCP Client.

Connects to the Pyth MCP server at https://mcp.pyth.network/mcp
and provides typed methods for each MCP tool:
  - get_symbols       (no auth required)
  - get_latest_price  (requires Pyth Pro token)
  - get_historical_price
  - get_candlestick_data

Used by the Risk Engine to fetch institutional-grade price data
and historical confidence trends.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────
# Response data classes
# ─────────────────────────────────────────────────────────────

@dataclass
class PythSymbol:
    """A single symbol returned by get_symbols."""
    symbol: str
    asset_type: str
    feed_id: Optional[int]


@dataclass
class PythLatestPrice:
    """Latest price data returned by get_latest_price."""
    symbol: str
    price: float
    confidence: float
    confidence_ratio: float   # confidence / |price| — PythGuard's core signal
    publish_time: int
    channel: str


@dataclass
class PythCandlestick:
    """A single OHLC candle returned by get_candlestick_data."""
    timestamp: int
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: Optional[float]


# ─────────────────────────────────────────────────────────────
# PythMCPClient
# ─────────────────────────────────────────────────────────────

class PythMCPClient:
    """
    HTTP client for the Pyth Pro MCP server.

    All methods are synchronous. For async usage, run them in a
    thread pool via asyncio.to_thread().
    """

    def __init__(self) -> None:
        self._http_client = httpx.Client(
            base_url=settings.pyth_mcp_server_url,
            timeout=30.0,
            headers={"Content-Type": "application/json"},
        )

    # ── MCP tool: get_symbols ─────────────────────────────────

    def get_symbols(
        self,
        query: Optional[str] = None,
        asset_type: Optional[str] = None,
        result_limit: int = 50,
    ) -> list[PythSymbol]:
        """
        Searches for available Pyth Pro feeds.
        No authentication required.

        Args:
            query:        Text search filter (e.g. "SOL", "BTC")
            asset_type:   Filter by type: "crypto", "fx", "equity", etc.
            result_limit: Maximum number of results (max 200)

        Returns:
            List of matching PythSymbol objects
        """
        tool_arguments: dict = {"limit": result_limit}

        if query is not None:
            tool_arguments["query"] = query
        if asset_type is not None:
            tool_arguments["asset_type"] = asset_type

        raw_response = self._call_mcp_tool(
            tool_name="get_symbols",
            tool_arguments=tool_arguments,
        )

        return [
            PythSymbol(
                symbol=symbol_entry.get("symbol", ""),
                asset_type=symbol_entry.get("assetType", ""),
                feed_id=symbol_entry.get("feedId"),
            )
            for symbol_entry in raw_response.get("symbols", [])
        ]

    # ── MCP tool: get_latest_price ────────────────────────────

    def get_latest_prices(
        self,
        symbols: list[str],
    ) -> list[PythLatestPrice]:
        """
        Fetches current prices for up to 100 feeds.
        Requires a valid Pyth Pro access token.

        Args:
            symbols: List of full symbol names e.g. ["Crypto.SOL/USD", "Crypto.BTC/USD"]

        Returns:
            List of PythLatestPrice objects with price and confidence data
        """
        # Guard: Pyth Pro token is mandatory for this tool
        if not settings.pyth_pro_access_token:
            raise ValueError(
                "PYTH_PRO_ACCESS_TOKEN is not set. "
                "DM CHOPPAtheSHARK on the Pyth forum to get one."
            )

        raw_response = self._call_mcp_tool(
            tool_name="get_latest_price",
            tool_arguments={
                "access_token": settings.pyth_pro_access_token,
                "symbols": symbols,
                "channel": "real_time",
            },
        )

        latest_prices: list[PythLatestPrice] = []

        for price_entry in raw_response.get("prices", []):
            raw_price = float(price_entry.get("price", 0))
            raw_confidence = float(price_entry.get("conf", 0))

            # Guard: skip entries with zero price to avoid division errors
            if raw_price == 0:
                logger.warning(
                    "skipping_zero_price_entry",
                    symbol=price_entry.get("symbol"),
                )
                continue

            confidence_ratio = raw_confidence / abs(raw_price)

            latest_prices.append(PythLatestPrice(
                symbol=price_entry.get("symbol", ""),
                price=raw_price,
                confidence=raw_confidence,
                confidence_ratio=confidence_ratio,
                publish_time=price_entry.get("publishTime", 0),
                channel=price_entry.get("channel", ""),
            ))

        return latest_prices

    # ── MCP tool: get_candlestick_data ────────────────────────

    def get_candlestick_data(
        self,
        symbol: str,
        resolution_minutes: str,
        from_timestamp: int,
        to_timestamp: int,
    ) -> list[PythCandlestick]:
        """
        Fetches OHLC candlestick data for a single feed.
        Used to compute volatility trends over recent history.

        Args:
            symbol:             Full symbol e.g. "Crypto.SOL/USD"
            resolution_minutes: "1", "5", "15", "30", "60", etc.
            from_timestamp:     Start time (Unix seconds)
            to_timestamp:       End time (Unix seconds)

        Returns:
            List of PythCandlestick objects (max 500 candles)
        """
        raw_response = self._call_mcp_tool(
            tool_name="get_candlestick_data",
            tool_arguments={
                "symbol": symbol,
                "resolution": resolution_minutes,
                "from": from_timestamp,
                "to": to_timestamp,
            },
        )

        return [
            PythCandlestick(
                timestamp=candle.get("time", 0),
                open_price=float(candle.get("open", 0)),
                high_price=float(candle.get("high", 0)),
                low_price=float(candle.get("low", 0)),
                close_price=float(candle.get("close", 0)),
                volume=candle.get("volume"),
            )
            for candle in raw_response.get("candles", [])
        ]

    # ── Convenience: recent confidence history ────────────────

    def get_recent_candlesticks_for_confidence_trend(
        self,
        symbol: str,
        lookback_minutes: int = 30,
    ) -> list[PythCandlestick]:
        """
        Fetches the last N minutes of 1-minute candles for a symbol.
        Used by the Risk Engine to detect rising volatility trends.

        Args:
            symbol:            Full symbol e.g. "Crypto.SOL/USD"
            lookback_minutes:  How far back to look (default: 30 min)
        """
        current_timestamp = int(time.time())
        start_timestamp = current_timestamp - (lookback_minutes * 60)

        return self.get_candlestick_data(
            symbol=symbol,
            resolution_minutes="1",
            from_timestamp=start_timestamp,
            to_timestamp=current_timestamp,
        )

    # ─────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────

    def _call_mcp_tool(
        self,
        tool_name: str,
        tool_arguments: dict,
    ) -> dict:
        """
        Sends a JSON-RPC style request to the Pyth MCP server.

        The MCP protocol uses POST requests with a JSON body
        containing the tool name and its arguments.
        """
        request_body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": tool_arguments,
            },
        }

        logger.debug("calling_mcp_tool", tool=tool_name)

        http_response = self._http_client.post("/", json=request_body)
        http_response.raise_for_status()

        response_json = http_response.json()

        # Guard: surface MCP-level errors explicitly
        if "error" in response_json:
            mcp_error = response_json["error"]
            raise RuntimeError(
                f"Pyth MCP error on tool '{tool_name}': "
                f"{mcp_error.get('code')} — {mcp_error.get('message')}"
            )

        result_content = response_json.get("result", {}).get("content", [])

        # MCP returns content as a list of typed blocks; we want the text block
        for content_block in result_content:
            if content_block.get("type") == "text":
                import json
                return json.loads(content_block["text"])

        return {}
