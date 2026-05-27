#!/usr/bin/env python3
"""Detect unusual volume using rolling z-score and percentile rank.

Statistical interpretation:
- z ~ 2.0  → ~5% probability if volume is normally distributed (it's not, but useful proxy)
- z ~ 3.0  → ~0.3% probability
- z ~ 4.0  → genuinely unusual

Volume distributions are right-skewed; for a more robust signal also report
percentile rank vs trailing 90 days, which doesn't assume normality.

Uses yfinance (free, daily granularity).

Usage:
    python scripts/unusual_volume.py AAPL
    python scripts/unusual_volume.py AAPL --json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta


def scan(ticker: str) -> dict:
    try:
        import yfinance as yf
        import numpy as np
    except ImportError as e:
        return {"ticker": ticker, "error": f"missing dep: {e}"}

    ticker = ticker.upper()
    try:
        t = yf.Ticker(ticker)
        # 120 trading days, plenty for stats
        hist = t.history(period="6mo", auto_adjust=False)
    except Exception as e:
        return {"ticker": ticker, "error": f"yf fetch failed: {e}"}

    if hist is None or hist.empty or len(hist) < 30:
        return {"ticker": ticker, "error": "insufficient history"}

    vol = hist["Volume"].dropna()
    if len(vol) < 30:
        return {"ticker": ticker, "error": "insufficient volume history"}

    today_vol = float(vol.iloc[-1])
    avg_20 = float(vol.iloc[-21:-1].mean())
    std_20 = float(vol.iloc[-21:-1].std())
    z = (today_vol - avg_20) / std_20 if std_20 > 0 else 0.0

    # Percentile vs trailing 90 days (excluding today)
    last_90 = vol.iloc[-91:-1]
    pct_rank = float((last_90 < today_vol).sum() / len(last_90) * 100) if len(last_90) else 0

    # Price change today
    close = hist["Close"].dropna()
    today_close = float(close.iloc[-1])
    prev_close = float(close.iloc[-2])
    pct_change = (today_close - prev_close) / prev_close * 100 if prev_close else 0

    # Price-volume regime
    abs_move = abs(pct_change)
    if z > 2 and abs_move < 1.0:
        regime = "institutional_accumulation_or_distribution"
    elif z > 2 and abs_move > 3:
        regime = "news_catalyst_or_breakout"
    elif z < -1 and abs_move > 2:
        regime = "low_conviction_move"
    elif z > 1 and abs_move > 2:
        regime = "trend_with_participation"
    else:
        regime = "normal"

    # Flag
    if z >= 4:
        flag = "EXTREME"
    elif z >= 3:
        flag = "SIGNIFICANT"
    elif z >= 2:
        flag = "NOTABLE"
    else:
        flag = "normal"

    return {
        "ticker": ticker,
        "today_volume": int(today_vol),
        "avg_20d_volume": int(avg_20),
        "std_20d_volume": int(std_20),
        "z_score": round(z, 2),
        "percentile_90d": round(pct_rank, 1),
        "today_close": round(today_close, 2),
        "today_pct_change": round(pct_change, 2),
        "regime": regime,
        "flag": flag,
        "source": "yfinance",
        "as_of": str(hist.index[-1].date()),
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
        print(f"VOLUME SCAN — {result['ticker']}  [ERROR: {result['error']}]")
        return

    print(f"VOLUME SCAN — {result['ticker']}  (as of {result['as_of']})")
    print(f"  Today volume:   {result['today_volume']:,}")
    print(f"  20D avg:        {result['avg_20d_volume']:,}")
    print(f"  Z-score:        {result['z_score']:+.2f}  [{result['flag']}]")
    print(f"  Percentile 90d: {result['percentile_90d']:.1f}%")
    print(f"  Today close:    ${result['today_close']:.2f}  ({result['today_pct_change']:+.2f}%)")
    print(f"  Regime:         {result['regime']}")


if __name__ == "__main__":
    main()
