#!/usr/bin/env python3
"""Scan Stocktwits for ticker activity. Public API, no auth, rate-limited.

Usage:
    python scripts/scan_stocktwits.py AAPL
    python scripts/scan_stocktwits.py AAPL --json
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Any

USER_AGENT = "trading-sidekick-research/0.1 (educational)"
TIMEOUT_S = 8


def _fetch_json(url: str) -> dict[str, Any] | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return json.loads(r.read())
    except Exception as e:
        sys.stderr.write(f"[stocktwits] {url} failed: {e}\n")
        return None


def scan(ticker: str) -> dict[str, Any]:
    ticker = ticker.upper()
    url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
    data = _fetch_json(url)
    if not data:
        return {"ticker": ticker, "error": "fetch failed or rate limited"}

    msgs = data.get("messages", [])
    cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    cutoff_7d = datetime.now(timezone.utc) - timedelta(days=7)

    sent_24h = {"bull": 0, "bear": 0, "untagged": 0}
    sent_7d = {"bull": 0, "bear": 0, "untagged": 0}
    posts_24h = 0
    posts_7d_total = 0

    for m in msgs:
        ts_str = m.get("created_at")
        if not ts_str:
            continue
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            continue

        if ts < cutoff_7d:
            continue
        posts_7d_total += 1

        sentiment = (m.get("entities") or {}).get("sentiment") or {}
        basic = sentiment.get("basic", "").lower()

        bucket = "bull" if basic == "bullish" else "bear" if basic == "bearish" else "untagged"
        sent_7d[bucket] += 1

        if ts >= cutoff_24h:
            posts_24h += 1
            sent_24h[bucket] += 1

    posts_per_hour_24h = posts_24h / 24
    posts_per_hour_baseline = posts_7d_total / (7 * 24) if posts_7d_total else 0
    velocity = (
        posts_per_hour_24h / posts_per_hour_baseline
        if posts_per_hour_baseline > 0
        else None
    )

    total_tagged_24h = sent_24h["bull"] + sent_24h["bear"]
    bull_pct = (sent_24h["bull"] / total_tagged_24h * 100) if total_tagged_24h else None
    bear_pct = (sent_24h["bear"] / total_tagged_24h * 100) if total_tagged_24h else None

    return {
        "ticker": ticker,
        "posts_24h": posts_24h,
        "posts_7d_total": posts_7d_total,
        "velocity_ratio": round(velocity, 2) if velocity else None,
        "velocity_flag": (
            "ACCELERATING" if velocity and velocity > 3 else
            "elevated" if velocity and velocity > 1.5 else
            "cold" if velocity and velocity < 0.5 else
            "normal"
        ),
        "sentiment_24h": sent_24h,
        "sentiment_7d": sent_7d,
        "bull_pct_24h": round(bull_pct, 1) if bull_pct is not None else None,
        "bear_pct_24h": round(bear_pct, 1) if bear_pct is not None else None,
        "source": "stocktwits_public_api",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    result = scan(args.ticker)
    if args.json:
        print(json.dumps(result, indent=2))
        return

    if "error" in result:
        print(f"STOCKTWITS SCAN — {result['ticker']}  [ERROR: {result['error']}]")
        return

    print(f"STOCKTWITS SCAN — {result['ticker']}")
    print(f"  Posts 24h:    {result['posts_24h']} (7d total: {result['posts_7d_total']})")
    print(f"  Velocity:     {result['velocity_ratio']}x  [{result['velocity_flag']}]")
    print(f"  Sentiment 24h: {result['bull_pct_24h']}% bull / {result['bear_pct_24h']}% bear "
          f"(tagged: {result['sentiment_24h']['bull']+result['sentiment_24h']['bear']}, "
          f"untagged: {result['sentiment_24h']['untagged']})")


if __name__ == "__main__":
    main()
