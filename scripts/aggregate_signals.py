#!/usr/bin/env python3
"""Aggregate scanner outputs into a ranked signal report.

Inputs: JSON files from flow-analyst, insider-watcher, social-scout, news-hawk.
Output: ranked tickers with composite scores and full evidence chain.

Analytics applied:
1. Source weighting (per-signal-type weights)
2. Recency decay (half-life: 5d news/social, 30d insider/13F)
3. Cross-source corroboration (3+ scanners = 1.5x multiplier)
4. Strategy fit (active strategy match + regime support = +0.3; mismatch = -0.5)
5. Earnings-window penalty (within 5 trading days = x0.7)

Usage:
    python scripts/aggregate_signals.py \\
        --flow flow.json \\
        --insider insider.json \\
        --social social.json \\
        --news news.json \\
        --strategies-dir data/strategies/ \\
        [--regime supported|unsupported|neutral]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# -------- Configuration --------

WEIGHTS = {
    "insider_cluster_buy": 1.0,
    "filing_13d":          0.9,
    "news_material":       0.8,
    "volume_z_3plus":      0.7,
    "analyst_cluster_up":  0.7,
    "options_unusual":     0.6,  # only when UW data available
    "congress_trade":      0.5,
    "insider_single_buy":  0.4,
    "social_velocity_5x":  0.4,
    "filing_13f_new":      0.3,
    "sentiment_dispersion": 0.2,
    "news_generic":        0.1,
}

HALF_LIFE_DAYS = {
    "news":     5,
    "social":   3,
    "insider":  30,
    "13f":      45,
    "flow":     2,
}

EARNINGS_WINDOW_DAYS = 5
EARNINGS_PENALTY = 0.7
STRATEGY_FIT_BONUS = 0.3
STRATEGY_MISMATCH_PENALTY = 0.5
CORROBORATION_THRESHOLD = 3
CORROBORATION_MULTIPLIER = 1.5


def _decay(days_old: float, half_life: float) -> float:
    """Exponential decay factor based on age."""
    if days_old < 0:
        return 1.0
    return 0.5 ** (days_old / half_life)


def _load_json(path: Path | None) -> dict:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception as e:
        sys.stderr.write(f"[aggregate] failed to load {path}: {e}\n")
        return {}


def _ticker_universe(*sources: dict) -> set[str]:
    tickers = set()
    for s in sources:
        if isinstance(s, dict):
            for k in s.keys():
                if isinstance(k, str) and 1 <= len(k) <= 10 and k.isupper():
                    tickers.add(k)
    return tickers


def score_ticker(
    ticker: str,
    flow: dict,
    insider: dict,
    social: dict,
    news: dict,
    strategy_match: bool,
    regime_supported: bool | None,
    earnings_in_days: int | None,
) -> dict:
    """Compute composite score with evidence."""
    f = flow.get(ticker, {})
    i = insider.get(ticker, {})
    s = social.get(ticker, {})
    n = news.get(ticker, {})

    contributions: list[dict] = []
    scanners_with_signal = 0

    # FLOW
    z = f.get("z_score", 0)
    if z and z >= 3:
        w = WEIGHTS["volume_z_3plus"] * _decay(0, HALF_LIFE_DAYS["flow"])
        contributions.append({"source": "flow", "type": "volume_z_3plus", "weight": w,
                              "evidence": f"volume z={z}, regime={f.get('regime')}"})
    if f.get("options_unusual"):
        w = WEIGHTS["options_unusual"] * _decay(0, HALF_LIFE_DAYS["flow"])
        contributions.append({"source": "flow", "type": "options_unusual", "weight": w,
                              "evidence": str(f.get("options_unusual"))[:200]})
    if contributions and contributions[-1]["source"] == "flow":
        scanners_with_signal += 1
    elif f and z and z >= 2:
        # Notable but below the heavy-weight threshold
        scanners_with_signal += 1

    # INSIDER
    if i.get("cluster_buy_count", 0) >= 3:
        w = WEIGHTS["insider_cluster_buy"] * _decay(i.get("cluster_buy_age_days", 0),
                                                   HALF_LIFE_DAYS["insider"])
        contributions.append({"source": "insider", "type": "insider_cluster_buy", "weight": w,
                              "evidence": f"{i['cluster_buy_count']} insiders bought, "
                                         f"total ${i.get('cluster_buy_total', 0):,.0f}"})
        scanners_with_signal += 1
    elif i.get("ceo_or_cfo_buy"):
        w = WEIGHTS["insider_single_buy"] * _decay(i.get("ceo_or_cfo_age_days", 0),
                                                  HALF_LIFE_DAYS["insider"])
        contributions.append({"source": "insider", "type": "insider_single_buy", "weight": w,
                              "evidence": i.get("ceo_or_cfo_evidence", "CEO/CFO buy")})
        scanners_with_signal += 1
    if i.get("filing_13d_recent"):
        w = WEIGHTS["filing_13d"] * _decay(i.get("filing_13d_age_days", 0),
                                          HALF_LIFE_DAYS["insider"])
        contributions.append({"source": "insider", "type": "filing_13d", "weight": w,
                              "evidence": i.get("filing_13d_evidence", "13D filed")})
        if not any(c["source"] == "insider" for c in contributions[:-1]):
            scanners_with_signal += 1
    if i.get("congress_trades_60d", 0) >= 1:
        w = WEIGHTS["congress_trade"] * _decay(i.get("congress_avg_age_days", 30),
                                              HALF_LIFE_DAYS["insider"])
        contributions.append({"source": "insider", "type": "congress_trade", "weight": w,
                              "evidence": f"{i['congress_trades_60d']} congressional trades disclosed"})

    # SOCIAL
    velocity = s.get("velocity_ratio")
    if velocity and velocity >= 5:
        w = WEIGHTS["social_velocity_5x"] * _decay(0, HALF_LIFE_DAYS["social"])
        contributions.append({"source": "social", "type": "social_velocity_5x", "weight": w,
                              "evidence": f"Reddit/ST velocity {velocity:.1f}x baseline"})
        scanners_with_signal += 1
    if s.get("sentiment_dispersion_high"):
        w = WEIGHTS["sentiment_dispersion"] * _decay(0, HALF_LIFE_DAYS["social"])
        contributions.append({"source": "social", "type": "sentiment_dispersion", "weight": w,
                              "evidence": "high sentiment variance (controversy)"})
        if not any(c["source"] == "social" for c in contributions[:-1]):
            scanners_with_signal += 1

    # NEWS
    material_count = n.get("material_news_count", 0)
    if material_count >= 1:
        w = WEIGHTS["news_material"] * _decay(n.get("most_recent_news_age_days", 0),
                                             HALF_LIFE_DAYS["news"])
        contributions.append({"source": "news", "type": "news_material", "weight": w,
                              "evidence": f"{material_count} material news items; latest: "
                                         f"{n.get('latest_headline', '')[:100]}"})
        scanners_with_signal += 1
    if n.get("analyst_cluster_upgrade"):
        w = WEIGHTS["analyst_cluster_up"] * _decay(n.get("analyst_avg_age_days", 7),
                                                  HALF_LIFE_DAYS["news"])
        contributions.append({"source": "news", "type": "analyst_cluster_up", "weight": w,
                              "evidence": f"{n.get('analyst_upgrades_30d', 0)} upgrades in 30d"})

    # Sum raw score
    raw_score = sum(c["weight"] for c in contributions)

    # Cross-source corroboration
    if scanners_with_signal >= CORROBORATION_THRESHOLD:
        raw_score *= CORROBORATION_MULTIPLIER
        corroboration_applied = True
    else:
        corroboration_applied = False

    # Strategy fit
    if strategy_match and regime_supported:
        raw_score += STRATEGY_FIT_BONUS
    elif strategy_match and regime_supported is False:
        raw_score -= STRATEGY_MISMATCH_PENALTY

    # Earnings penalty
    earnings_applied = False
    if earnings_in_days is not None and 0 <= earnings_in_days <= EARNINGS_WINDOW_DAYS:
        raw_score *= EARNINGS_PENALTY
        earnings_applied = True

    # Normalize to 0-10 scale (cap at 10)
    composite = min(round(raw_score * 2, 2), 10.0)

    return {
        "ticker": ticker,
        "composite_score": composite,
        "raw_score": round(raw_score, 3),
        "scanners_with_signal": scanners_with_signal,
        "corroboration_applied": corroboration_applied,
        "earnings_in_days": earnings_in_days,
        "earnings_penalty_applied": earnings_applied,
        "strategy_match": strategy_match,
        "regime_supported": regime_supported,
        "contributions": contributions,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flow", type=Path)
    ap.add_argument("--insider", type=Path)
    ap.add_argument("--social", type=Path)
    ap.add_argument("--news", type=Path)
    ap.add_argument("--strategies-dir", type=Path, default=Path("data/strategies"))
    ap.add_argument("--regime-supported", type=str, default="",
                    help="Comma-separated tickers that match active+supported strategies")
    ap.add_argument("--earnings-windows", type=str, default="",
                    help="Comma-separated ticker:days pairs (e.g., 'AAPL:3,NVDA:1')")
    ap.add_argument("--threshold", type=float, default=5.0,
                    help="Composite score threshold for 'top signals' section")
    ap.add_argument("--bootstrap", action="store_true",
                    help="Print framework info and exit (used by deep-dive skill)")
    args = ap.parse_args()

    if args.bootstrap:
        print(json.dumps({
            "weights": WEIGHTS,
            "half_lives": HALF_LIFE_DAYS,
            "threshold": args.threshold,
            "corroboration_threshold": CORROBORATION_THRESHOLD,
            "ready": True,
        }, indent=2))
        return

    flow = _load_json(args.flow)
    insider = _load_json(args.insider)
    social = _load_json(args.social)
    news = _load_json(args.news)

    tickers = _ticker_universe(flow, insider, social, news)

    supported_set = {t.strip().upper() for t in args.regime_supported.split(",") if t.strip()}

    earnings_map: dict[str, int] = {}
    for pair in args.earnings_windows.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if ":" in pair:
            t, d = pair.split(":", 1)
            try:
                earnings_map[t.strip().upper()] = int(d)
            except ValueError:
                pass

    results = []
    for t in tickers:
        regime = True if t in supported_set else (False if supported_set else None)
        strategy_match = t in supported_set
        results.append(score_ticker(
            t, flow, insider, social, news,
            strategy_match=strategy_match,
            regime_supported=regime,
            earnings_in_days=earnings_map.get(t),
        ))

    results.sort(key=lambda r: r["composite_score"], reverse=True)

    print(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tickers_scored": len(results),
        "threshold": args.threshold,
        "above_threshold": [r for r in results if r["composite_score"] >= args.threshold],
        "below_threshold": [r for r in results if r["composite_score"] < args.threshold],
    }, indent=2))


if __name__ == "__main__":
    main()
