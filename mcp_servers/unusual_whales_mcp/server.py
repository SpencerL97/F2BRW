#!/usr/bin/env python3
"""Unusual Whales MCP server stub.

This is a SCAFFOLD. It does not work until you:
1. Subscribe to Unusual Whales: https://unusualwhales.com/
2. Get your API token from your account settings
3. Add UNUSUAL_WHALES_API_KEY to your .env
4. Add this server to .mcp.json (see below)
5. Verify the endpoint paths against current UW API docs (they evolve)

Add to .mcp.json:
{
  "mcpServers": {
    ...,
    "unusual-whales": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "mcp_servers.unusual_whales_mcp.server"],
      "env": {
        "UNUSUAL_WHALES_API_KEY": "${UNUSUAL_WHALES_API_KEY}"
      }
    }
  }
}

Run via: python -m mcp_servers.unusual_whales_mcp.server
"""
from __future__ import annotations

import os
from typing import Any

import urllib.request
import urllib.parse
import json

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

API_KEY = os.environ.get("UNUSUAL_WHALES_API_KEY", "")
BASE_URL = "https://api.unusualwhales.com/api"

mcp = FastMCP("unusual-whales")


def _request(path: str, params: dict | None = None) -> dict[str, Any]:
    if not API_KEY:
        return {"error": "UNUSUAL_WHALES_API_KEY not set. This MCP is inactive."}
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def get_options_flow(ticker: str, min_premium: float = 25_000) -> dict:
    """Recent unusual options flow for a ticker. min_premium in USD.
    NOTE: Endpoint path may need adjustment per current UW API docs.
    """
    return _request(f"/stock/{ticker.upper()}/flow", {"min_premium": min_premium})


@mcp.tool()
def get_dark_pool_prints(ticker: str, limit: int = 20) -> dict:
    """Recent dark pool prints for a ticker.
    NOTE: Endpoint path may need adjustment.
    """
    return _request(f"/stock/{ticker.upper()}/dark-pool", {"limit": limit})


@mcp.tool()
def get_congressional_trades(ticker: str | None = None, limit: int = 50) -> dict:
    """Recent congressional trade disclosures, optionally filtered by ticker."""
    params = {"limit": limit}
    if ticker:
        params["ticker"] = ticker.upper()
    return _request("/congress/trades", params)


@mcp.tool()
def get_insider_buys(min_value: float = 100_000, limit: int = 50) -> dict:
    """Recent insider buys above a minimum dollar value, market-wide."""
    return _request("/insider/buys", {"min_value": min_value, "limit": limit})


@mcp.tool()
def get_oi_changes(ticker: str) -> dict:
    """Open interest changes for the ticker's options chain."""
    return _request(f"/stock/{ticker.upper()}/oi-changes")


@mcp.tool()
def health() -> dict:
    """Returns the current activation status of this MCP."""
    if not API_KEY:
        return {
            "active": False,
            "reason": "UNUSUAL_WHALES_API_KEY not set in environment.",
            "subscribe": "https://unusualwhales.com/",
        }
    return {"active": True, "base_url": BASE_URL}


if __name__ == "__main__":
    mcp.run()
