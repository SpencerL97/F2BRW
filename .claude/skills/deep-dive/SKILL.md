---
name: deep-dive
description: Auto-activates on prompts like "deep dive on X", "scan for signals", "what's hot", "any unusual activity", "blast the sources", "find me something". Fans out 4 parallel scanner subagents (flow-analyst, insider-watcher, social-scout, news-hawk) and aggregates findings into a ranked signal report. This is RESEARCH output — it does NOT bypass the four-specialist trade gate.
---

# Deep Dive Signal Scan

## Mandate

The deep-dive produces **research**, not trade signals. Output feeds INTO the pre-trade-checklist if the user wants to act — it never replaces it.

## Step 1 — Determine scope

Parse the user request into one of three modes:

| Mode | Trigger phrases | Scope |
|---|---|---|
| `TICKER` | "deep dive on AAPL", "scan NVDA" | One specific symbol |
| `UNIVERSE` | "what's hot", "scan for signals", "find me something" | Top movers + watchlist + recent journal symbols |
| `EVENT` | "what happened today", "any unusual activity last hour" | Time-bounded sweep across active universe |

If ambiguous, ask one clarifying question.

## Step 2 — Build the symbol list

- TICKER mode: just the named symbol.
- UNIVERSE mode: union of
  - Current IBKR positions (`mcp__interactive-brokers__get_account_positions`)
  - Tickers in last 30 days of journal
  - Top 10 gainers + top 10 losers (`mcp__fmp__marketPerformance`)
  - Tickers in any active strategy YAML's universe spec
  - Deduplicated, capped at 25.
- EVENT mode: same as UNIVERSE but filtered by `mcp__interactive-brokers__get_price_history` activity in last N hours.

## Step 3 — Fan out four scanners IN PARALLEL

Spawn ALL four subagents simultaneously. Do NOT chain them.
Each receives the symbol list and runs its scan independently.

```
PARALLEL INVOKE:
  → flow-analyst       (volume, options flow, 13F, dark pool)
  → insider-watcher    (Form 4, congress, 13D/G, recent SEC filings)
  → social-scout       (Reddit, Stocktwits, X via web search, LunarCrush)
  → news-hawk          (news, analyst, earnings calendar, transcripts)
```

While they run, also kick off `python scripts/aggregate_signals.py --bootstrap` to confirm the aggregation framework loads (it prints the weight/half-life table and exits).

## Step 4 — Aggregate with statistical weighting

Each scanner writes its structured findings to a JSON file under `data/scan/`, where the
**top-level keys are uppercase tickers**. The aggregator builds the scored universe from the
union of those keys, so a ticker only needs to appear in the files where it actually has a signal.

Minimum fields the scorer reads per source (omit any you don't have):

```jsonc
// data/scan/flow.json
{ "NVDA": { "z_score": 3.4, "regime": "news_catalyst_or_breakout", "options_unusual": "..." } }
// data/scan/insider.json
{ "NVDA": { "cluster_buy_count": 3, "cluster_buy_age_days": 4, "cluster_buy_total": 2100000,
            "ceo_or_cfo_buy": true, "filing_13d_recent": false, "congress_trades_60d": 0 } }
// data/scan/social.json
{ "NVDA": { "velocity_ratio": 5.2, "sentiment_dispersion_high": true } }
// data/scan/news.json
{ "NVDA": { "material_news_count": 2, "most_recent_news_age_days": 1,
            "latest_headline": "...", "analyst_cluster_upgrade": true, "analyst_upgrades_30d": 4 } }
```

Once all four scanners have written their files, run (these flags match the script's actual
interface — see `python scripts/aggregate_signals.py --help`):

```bash
python scripts/aggregate_signals.py \
  --flow data/scan/flow.json \
  --insider data/scan/insider.json \
  --social data/scan/social.json \
  --news data/scan/news.json \
  --regime-supported "<comma-separated tickers matching an active+supported strategy>" \
  --earnings-windows "<TICKER:days,...>" \
  --threshold 5.0
```

`--regime-supported` is the set of tickers that both match an active strategy's universe AND are
supported by today's regime (from `market-regime-analyst`); the scorer applies the +0.3 fit bonus
to those and the −0.5 mismatch penalty to the rest of the scored universe. `--earnings-windows`
carries trading-days-to-earnings per ticker (from `news-hawk`) so the ×0.7 earnings penalty fires.

The aggregator applies:

1. **Source weighting**:
   - Insider cluster buy: 1.0
   - 13D filing: 0.9
   - News (material): 0.8
   - Volume z>3: 0.7
   - Analyst cluster upgrade: 0.7
   - Congressional trade: 0.5
   - Insider single buy: 0.4
   - Social mention velocity > 5x: 0.4
   - 13F change: 0.3
   - Sentiment dispersion only: 0.2
   - Generic news: 0.1

2. **Recency decay**: half-life of 5 days for news/social, 30 days for insider/13F.

3. **Cross-source corroboration multiplier**: signals confirmed by 3+ independent scanners get a 1.5x multiplier on composite score.

4. **Strategy fit bonus**: if the ticker matches an active strategy YAML's universe AND the regime supports it, +0.3 to composite. If unsupported, -0.5.

5. **Earnings-window penalty**: signals within 5 trading days of earnings get composite × 0.7 (more noise, less actionable).

## Step 5 — Render the report

```
==========================================
DEEP DIVE REPORT — <timestamp>
Mode: <TICKER|UNIVERSE|EVENT>
Symbols scanned: <N>
Wall time: <S> seconds
==========================================

TOP 5 SIGNALS BY COMPOSITE SCORE
------------------------------------------

#1. <TICKER>  composite: <score>/10  earnings in <D>d
  flow:      <one line summary>
  insider:   <one line summary>
  social:    <one line summary>
  news:      <one line summary>
  ─────
  CONVERGENCE: <which scanners agree, in plain language>
  CONFLICT:    <which scanners disagree, if any>
  STRATEGY FIT: <strategy_name | none — would require new strategy>
  NEXT STEP:   <e.g., "run pre-trade-checklist with proposed entry/stop/target" | "watch, do not enter — narrative too thin" | "investigate cluster buy further">

#2. ...

==========================================
SIGNALS BELOW THE BAR (composite 3-6, FYI only)
  <TICKER> — <one line>
  <TICKER> — <one line>

NO-SIGNAL UNIVERSE (composite <3, mentioned only for completeness)
  <tickers>

==========================================
SOURCE COVERAGE
  Sources hit:    <list>
  Sources empty:  <list>
  Sources unavailable today: <list with reason>
==========================================
```

## Step 6 — Hand off

If the user picks a signal to act on:
> "To trade <TICKER>, run the pre-trade-checklist. The deep-dive does NOT bypass it. Propose: entry, stop, target, and strategy from data/strategies/."

If no signal clears the bar:
> "Nothing above threshold today. Best action: do nothing, run the daily-debrief tomorrow, re-scan."

## Hard Rules

- **Research only.** Deep dive output is NEVER a trade trigger. Surface findings; the Panel decides.
- **Source citations on every claim.** If a signal can't be cited, omit it.
- **Honest about gaps.** If X data is missing (e.g., no Unusual Whales subscription), say so explicitly. Don't paper over.
- **No "actionable insight" boilerplate language.** State the data, name the convergence/conflict, hand off.
- **Strategy fit matters.** A 10/10 composite score on a ticker that doesn't fit any approved strategy is not tradable. Surface this.
- **Earnings respect.** Aggressive composite scores within 5 days of earnings get downweighted — that's not pessimism, it's discipline.

## What "advanced analytics" actually means here

- Multi-source corroboration with proper weighting (not just "lots of news = good")
- Recency-decayed scoring (a 5-day-old insider buy ≠ a same-day one)
- Statistical anomaly detection (z-scores, percentiles — not visual chart-feel)
- Strategy and regime conditioning (signals are only useful in supported contexts)
- Earnings-window discipline (noise vs signal differentiation)
- Honest empty-set handling (no signal is a valid finding)
