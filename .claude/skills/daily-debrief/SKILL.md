---
name: daily-debrief
description: Auto-activates at session start and on phrases like "daily debrief", "morning check", "what's the state of the world". Produces the morning dashboard.
---

# Daily Debrief

Run all steps. Surface a single dashboard at the end.

## Step 1 — Account & positions
- Call `mcp__interactive-brokers__get_account_summary`. Note equity, day P&L, mode (must be paper).
- Call `mcp__interactive-brokers__get_account_positions`. List every open position with unrealized P&L.
- Call `mcp__interactive-brokers__get_account_orders`. Anything pending overnight?
- Determine market open/closed from gcal or recent price data timestamps.

## Step 1b — Portfolio snapshot
Invoke `portfolio-risk-decomposer` for a brief — sector breakdown, factor tilts, beta to SPY, implicit macro bet. Surface any breaches.

## Step 1c — Cross-asset state
Invoke `cross-asset-analyst` for today's tape — VIX, DXY, TLT, HYG state. This sets up the regime context.

## Step 2 — Per-position event check
For each open position, call `mcp__fmp__calendar` to find earnings within next 5 days. Surface any matches.

## Step 3 — Macro calendar
- Call `mcp__gcal__list_events` for today and tomorrow. Surface Fed, CPI, NFP, jobless claims, GDP, PMI.
- Call `mcp__bigdata__bigdata_events_calendar` for the next 48h to catch anything `gcal` missed.

## Step 4 — Regime classification

Invoke `market-regime-analyst`. Surface today's regime AND the strategy fit table. Flag any UNSUPPORTED strategies — they should sit out today.

## Step 5 — Behavioral pulse
Query the journal:
```bash
sqlite3 data/journal.db "
  SELECT
    COUNT(*) as trades_this_week,
    SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) as losses,
    SUM(pnl) as week_pnl
  FROM trades
  WHERE entry_time >= date('now', '-7 days');
"
```
Surface week stats and any flagged patterns from `behavioral-coach`.

## Step 6 — Limit status
Compute and surface:
- Day P&L vs −2% limit
- Week P&L vs −5% limit
- Month drawdown vs −8% limit
- Any limit breached → state HALT MODE ACTIVE and what's allowed (journaling only).

## Output Format

```
================================================
DAILY DEBRIEF — <YYYY-MM-DD>  Market: <OPEN|CLOSED>
================================================

ACCOUNT
  Mode:     paper
  Equity:   $X
  Day P&L:  $Y (Z%)
  Buying power: $W

POSITIONS (N open)
  AAPL    50 @ $185.20 → $187.10 ($95 / +0.5%) | stop: $182.00 | earnings: 2026-05-02
  ...

OPEN ORDERS
  none / list

TODAY'S CALENDAR
  09:30 ET  Market open
  14:00 ET  FOMC minutes
  ...

THIS WEEK
  Trades: 4 (3W / 1L)
  Week P&L: +$340 (+0.34%)
  Behavioral flags: none / list
  Pending post-mortems: <count of closed losing trades without POST-MORTEM in notes>

LIMIT STATUS
  Daily:   −0.2% / −2.0%   [OK]
  Weekly:  +0.3% / −5.0%   [OK]
  Monthly: +1.1% / −8.0%   [OK]

ATTENTION TODAY
  - <thing>
  - <thing>
================================================
```

## Step 7 — Record the debrief

Write today's debrief row so `behavioral-coach` can confirm the trader actually ran it
(it checks `debriefs` for today's date):
```bash
python scripts/journal.py debrief --equity <equity> --day-pnl <day_pnl> \
  --notes "<one-line summary of regime + attention items>"
```

End with: "What would you like to look at first?" — NOT a trade suggestion.
