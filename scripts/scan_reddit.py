#!/usr/bin/env python3
"""Scan Reddit for ticker mentions across finance subs. Uses public JSON
endpoints (no auth). Rate-limited; do not hammer.

Usage:
    python scripts/scan_reddit.py AAPL
    python scripts/scan_reddit.py AAPL --hours 24 --json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Any

SUBS = ["wallstreetbets", "stocks", "investing", "options", "StockMarket"]
USER_AGENT = "trading-sidekick-research/0.1 (educational)"
TIMEOUT_S = 8


def _fetch_json(url: str) -> dict[str, Any] | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return json.loads(r.read())
    except Exception as e:
        sys.stderr.write(f"[reddit] {url} failed: {e}\n")
        return None


def _classify_sentiment(text: str) -> str:
    """Very crude sentiment proxy. Returns bull|bear|neutral."""
    text_l = text.lower()
    bull = sum(text_l.count(w) for w in [
        "calls", "moon", "long ", "buying", "bullish", "to the moon",
        "breakout", "squeeze", "rocket", "🚀", "pump", "rip",
    ])
    bear = sum(text_l.count(w) for w in [
        "puts", "short", "shorting", "bearish", "dump", "crash",
        "tank", "rug", "bag", "rugpull", "drilling", "tanking",
    ])
    if bull > bear + 1:
        return "bull"
    if bear > bull + 1:
        return "bear"
    return "neutral"


def _account_age_days(created_utc: float | None) -> float | None:
    if not created_utc:
        return None
    return (datetime.now(timezone.utc) - datetime.fromtimestamp(created_utc, tz=timezone.utc)).days


def scan(ticker: str, hours: int = 24) -> dict[str, Any]:
    ticker = ticker.upper()
    cutoff_ts = (datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp()
    cutoff_baseline_ts = (datetime.now(timezone.utc) - timedelta(days=7)).timestamp()

    hits_recent: list[dict] = []
    hits_baseline: list[dict] = []
    account_ages: list[float] = []
    sentiments = {"bull": 0, "bear": 0, "neutral": 0}
    top_posts: list[dict] = []

    for sub in SUBS:
        # Use search endpoint with restrict_sr=on to scope to the sub
        q = urllib.parse.quote(f"${ticker} OR {ticker}")
        url = f"https://www.reddit.com/r/{sub}/search.json?q={q}&restrict_sr=on&sort=new&limit=100&t=week"
        data = _fetch_json(url)
        time.sleep(1.2)  # be polite
        if not data:
            continue
        children = data.get("data", {}).get("children", [])
        for c in children:
            p = c.get("data", {})
            created = p.get("created_utc", 0)
            if created < cutoff_baseline_ts:
                continue
            title = p.get("title", "")
            selftext = p.get("selftext", "") or ""
            entry = {
                "subreddit": sub,
                "title": title,
                "score": p.get("score", 0),
                "num_comments": p.get("num_comments", 0),
                "created_utc": created,
                "permalink": "https://reddit.com" + p.get("permalink", ""),
                "ratio": p.get("upvote_ratio", 0),
                "author": p.get("author", ""),
            }
            if created >= cutoff_ts:
                hits_recent.append(entry)
                sent = _classify_sentiment(title + " " + selftext)
                sentiments[sent] += 1
                top_posts.append(entry)
                # Fetch author age (optional, costly)
                # Skip for speed; can be enabled later
            else:
                hits_baseline.append(entry)

    # Mention velocity vs 7d baseline
    posts_per_hour_recent = len(hits_recent) / max(hours, 1)
    baseline_hours = max(7 * 24 - hours, 1)
    posts_per_hour_baseline = len(hits_baseline) / baseline_hours
    velocity = posts_per_hour_recent / posts_per_hour_baseline if posts_per_hour_baseline > 0 else None

    total = sum(sentiments.values())
    sentiment_pct = {k: round(v / total * 100, 1) if total else 0 for k, v in sentiments.items()}

    # Top posts
    top_posts.sort(key=lambda x: x.get("score", 0), reverse=True)
    top_3 = top_posts[:3]

    return {
        "ticker": ticker,
        "window_hours": hours,
        "mentions_recent": len(hits_recent),
        "mentions_baseline_7d": len(hits_baseline),
        "posts_per_hour_recent": round(posts_per_hour_recent, 3),
        "posts_per_hour_baseline": round(posts_per_hour_baseline, 3),
        "velocity_ratio": round(velocity, 2) if velocity is not None else None,
        "velocity_flag": (
            "ACCELERATING" if velocity is not None and velocity > 3 else
            "elevated" if velocity is not None and velocity > 1.5 else
            "cold" if velocity is not None and velocity < 0.5 else
            "normal"
        ),
        "sentiment_counts": sentiments,
        "sentiment_pct": sentiment_pct,
        "subs_with_activity": sorted({h["subreddit"] for h in hits_recent}),
        "top_posts": [
            {
                "title": p["title"][:140],
                "subreddit": p["subreddit"],
                "score": p["score"],
                "comments": p["num_comments"],
                "permalink": p["permalink"],
            }
            for p in top_3
        ],
        "data_age_seconds": 0,
        "source": "reddit_public_json",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--json", action="store_true", help="JSON output (default is human)")
    args = ap.parse_args()

    result = scan(args.ticker, hours=args.hours)
    if args.json:
        print(json.dumps(result, indent=2))
        return

    # Human format
    print(f"REDDIT SCAN — {result['ticker']} ({result['window_hours']}h window)")
    print(f"  Mentions:        {result['mentions_recent']} (7d baseline: {result['mentions_baseline_7d']})")
    print(f"  Velocity:        {result['velocity_ratio']}x  [{result['velocity_flag']}]")
    s = result["sentiment_pct"]
    print(f"  Sentiment:       {s['bull']}% bull / {s['bear']}% bear / {s['neutral']}% neutral")
    print(f"  Active subs:     {', '.join(result['subs_with_activity']) or '(none)'}")
    print(f"  Top posts:")
    for p in result["top_posts"]:
        print(f"    [{p['score']:>4}↑/{p['comments']:>3}c] r/{p['subreddit']}: {p['title']}")
        print(f"      {p['permalink']}")


if __name__ == "__main__":
    main()
