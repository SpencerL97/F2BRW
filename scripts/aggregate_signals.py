#!/usr/bin/env python3
"""Aggregate scanner outputs into a ranked signal report.

Inputs: JSON files from flow-analyst, insider-watcher, social-scout, news-hawk.
Each file is a JSON object whose top-level keys are uppercase tickers.
Output: ranked tickers with composite scores and full evidence chain.

Analytics applied:
1. Source weighting (per-signal-type weights)
2. Recency decay (half-life: 5d news, 3d social, 30d insider, 45d 13F, 2d flow)
3. Cross-source corroboration (3+ distinct scanners contributing = 1.5x multiplier)
4. Strategy fit: matches an active strategy AND regime supports it = +0.3;
   matches an active strategy but regime does NOT support it = -0.5;
   matches no active strategy = neutral (0)
5. Earnings-window penalty (within 5 trading days = x0.7)

Usage:
    python scripts/aggregate_signals.py \\
        --flow data/scan/flow.json \\
        --insider data/scan/insider.json \\
        --social data/scan/social.json \\
        --news data/scan/news.json \\
        --strategy-match "AAPL,NVDA" \\
        --regime-supported "NVDA" \\
        --earnings-windows "AAPL:3,NVDA:1" \\
        --threshold 5.0

    python scripts/aggregate_signals.py --bootstrap   # print framework + exit
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
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


def _num(value, default: float = 0.0) -> float:
    """Coerce a possibly-missing/None/string value to float; never raises."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_json(path: Path | None) -> dict:
    if not path or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
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
    """Compute composite score with evidence.

    `scanners_with_signal` is the number of DISTINCT sources (flow/insider/social/news)
    that actually contributed weight — that is what the corroboration multiplier keys on.
    """
    f = flow.get(ticker, {})
    i = insider.get(ticker, {})
    s = social.get(ticker, {})
    n = news.get(ticker, {})

    contributions: list[dict] = []

    # FLOW
    z = _num(f.get("z_score"))
    if z >= 3:
        w = WEIGHTS["volume_z_3plus"] * _decay(0, HALF_LIFE_DAYS["flow"])
        contributions.append({"source": "flow", "type": "volume_z_3plus", "weight": w,
                              "evidence": f"volume z={z}, regime={f.get('regime')}"})
    if f.get("options_unusual"):
        w = WEIGHTS["options_unusual"] * _decay(0, HALF_LIFE_DAYS["flow"])
        contributions.append({"source": "flow", "type": "options_unusual", "weight": w,
                              "evidence": str(f.get("options_unusual"))[:200]})

    # INSIDER
    if _num(i.get("cluster_buy_count")) >= 3:
        w = WEIGHTS["insider_cluster_buy"] * _decay(_num(i.get("cluster_buy_age_days")),
                                                    HALF_LIFE_DAYS["insider"])
        contributions.append({"source": "insider", "type": "insider_cluster_buy", "weight": w,
                              "evidence": f"{int(_num(i.get('cluster_buy_count')))} insiders bought, "
                                         f"total ${_num(i.get('cluster_buy_total')):,.0f}"})
    elif i.get("ceo_or_cfo_buy"):
        w = WEIGHTS["insider_single_buy"] * _decay(_num(i.get("ceo_or_cfo_age_days")),
                                                   HALF_LIFE_DAYS["insider"])
        contributions.append({"source": "insider", "type": "insider_single_buy", "weight": w,
                              "evidence": i.get("ceo_or_cfo_evidence", "CEO/CFO buy")})
    if i.get("filing_13d_recent"):
        w = WEIGHTS["filing_13d"] * _decay(_num(i.get("filing_13d_age_days")),
                                           HALF_LIFE_DAYS["insider"])
        contributions.append({"source": "insider", "type": "filing_13d", "weight": w,
                              "evidence": i.get("filing_13d_evidence", "13D filed")})
    if _num(i.get("congress_trades_60d")) >= 1:
        w = WEIGHTS["congress_trade"] * _decay(_num(i.get("congress_avg_age_days"), 30),
                                               HALF_LIFE_DAYS["insider"])
        contributions.append({"source": "insider", "type": "congress_trade", "weight": w,
                              "evidence": f"{int(_num(i.get('congress_trades_60d')))} congressional trades disclosed"})

    # SOCIAL
    velocity = _num(s.get("velocity_ratio"))
    if velocity >= 5:
        w = WEIGHTS["social_velocity_5x"] * _decay(0, HALF_LIFE_DAYS["social"])
        contributions.append({"source": "social", "type": "social_velocity_5x", "weight": w,
                              "evidence": f"Reddit/ST velocity {velocity:.1f}x baseline"})
    if s.get("sentiment_dispersion_high"):
        w = WEIGHTS["sentiment_dispersion"] * _decay(0, HALF_LIFE_DAYS["social"])
        contributions.append({"source": "social", "type": "sentiment_dispersion", "weight": w,
                              "evidence": "high sentiment variance (controversy)"})

    # NEWS
    material_count = _num(n.get("material_news_count"))
    if material_count >= 1:
        w = WEIGHTS["news_material"] * _decay(_num(n.get("most_recent_news_age_days")),
                                              HALF_LIFE_DAYS["news"])
        contributions.append({"source": "news", "type": "news_material", "weight": w,
                              "evidence": f"{int(material_count)} material news items; latest: "
                                         f"{str(n.get('latest_headline', ''))[:100]}"})
    if n.get("analyst_cluster_upgrade"):
        w = WEIGHTS["analyst_cluster_up"] * _decay(_num(n.get("analyst_avg_age_days"), 7),
                                                   HALF_LIFE_DAYS["news"])
        contributions.append({"source": "news", "type": "analyst_cluster_up", "weight": w,
                              "evidence": f"{int(_num(n.get('analyst_upgrades_30d')))} upgrades in 30d"})

    # Sum raw score
    raw_score = sum(c["weight"] for c in contributions)

    # Cross-source corroboration: count DISTINCT sources that contributed weight.
    scanners_with_signal = len({c["source"] for c in contributions})
    corroboration_applied = scanners_with_signal >= CORROBORATION_THRESHOLD
    if corroboration_applied:
        raw_score *= CORROBORATION_MULTIPLIER

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

    # Normalize to 0-10 scale (cap at 10, floor at 0)
    composite = max(min(round(raw_score * 2, 2), 10.0), 0.0)

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


def _parse_ticker_set(raw: str) -> set[str]:
    return {t.strip().upper() for t in raw.split(",") if t.strip()}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--flow", type=Path)
    ap.add_argument("--insider", type=Path)
    ap.add_argument("--social", type=Path)
    ap.add_argument("--news", type=Path)
    ap.add_argument("--strategy-match", type=str, default="",
                    help="Comma-separated tickers that match an ACTIVE strategy's universe "
                         "(regardless of regime). Tickers listed here but NOT in "
                         "--regime-supported take the mismatch penalty. If omitted, the "
                         "--regime-supported set is used (no mismatch penalty fires).")
    ap.add_argument("--regime-supported", type=str, default="",
                    help="Comma-separated tickers whose matching strategy the current regime "
                         "supports (a subset of --strategy-match). These get the fit bonus.")
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

    supported_set = _parse_ticker_set(args.regime_supported)
    match_set = _parse_ticker_set(args.strategy_match)
    # If no explicit strategy-match set was given, treat the supported set as the matched
    # universe (legacy behaviour: bonus only, no mismatch penalty). Supported is always a
    # subset of matched.
    if not match_set:
        match_set = set(supported_set)
    match_set |= supported_set

    earnings_map: dict[str, int] = {}
    for pair in args.earnings_windows.split(","):
        pair = pair.strip()
        if ":" in pair:
            t, d = pair.split(":", 1)
            try:
                earnings_map[t.strip().upper()] = int(d)
            except ValueError:
                pass

    results = []
    for t in tickers:
        strategy_match = t in match_set
        if t in supported_set:
            regime = True
        elif t in match_set:
            regime = False
        else:
            regime = None
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
