---
name: risk-audit
description: Auto-activates Fridays after close and on "weekly review" / "risk audit" prompts. Produces a structured per-strategy verdict and forces written commitments for the next week.
---

# Risk Audit (Weekly)

Run every Friday after close, or on demand. The output is a memo, not a chat.

## Step 1 — Pull the week's trades

```bash
sqlite3 data/journal.db "
  SELECT id, entry_time, symbol, side, strategy, pnl, r_multiple, outcome, rule_violations, emotion_pre, emotion_post
  FROM trades
  WHERE entry_time >= date('now', '-7 days')
  ORDER BY entry_time;
"
```

## Step 2 — Compute the stats

For each strategy that traded this week, compute:
- N trades
- Win rate
- Average R-multiple (use Wolfram for precision)
- Max drawdown intra-week
- Sum of R for the strategy
- Expectancy = avg_R per trade

## Step 3 — Edge decay test (the important one)

For each strategy, compare this week's expectancy to the strategy YAML's stated backtest expectancy.

Call `mcp__wolfram__WolframLanguageEvaluator` with a Monte Carlo simulation:
> "Given backtest mean R = X, stdev = Y, N = 7 trades, is the observed sum of R within the 95% confidence interval?"

If observed R is below the 5th percentile of the Monte Carlo distribution → flag as POSSIBLE EDGE DECAY (still could be noise — one week is small).
If observed R is below the 5th percentile for THREE consecutive weeks → flag as EDGE DECAY CONFIRMED, recommend retirement.

## Step 4 — Rule violations audit

```bash
sqlite3 data/journal.db "
  SELECT rule_violations, COUNT(*)
  FROM trades
  WHERE entry_time >= date('now', '-7 days')
    AND rule_violations != 'none' AND rule_violations IS NOT NULL
  GROUP BY rule_violations;
"
```

Surface each violation count. Any single violation in the last 7 days is yellow. Any repeat of the same violation is red.

## Step 5 — Account-level metrics

- Week P&L $ and %
- Largest single-trade loss vs per-trade cap
- Max intra-week portfolio heat vs 5% cap
- Number of days the daily loss limit was breached

## Step 6 — Output the memo

```
================================================
WEEKLY RISK AUDIT — Week of <YYYY-MM-DD>
================================================

ACCOUNT
  Starting equity:  $X
  Ending equity:    $Y
  Week P&L:         $Z (P%)
  Max drawdown:     D%

ACTIVITY
  Trades:           N
  Win rate:         W%
  Avg R:            R
  Sum R:            SR
  Best trade:       <symbol>  +Xr
  Worst trade:      <symbol>  -Yr

BY STRATEGY
  strategy_001: N trades, expectancy +0.4R (backtest: +0.6R) — within MC band ✓
  strategy_002: N trades, expectancy -0.3R (backtest: +0.5R) — BELOW 5th pct, 1st week
  ...

RULE VIOLATIONS
  moved_stop: 2 occurrences (RED — repeat)
  outside_session: 1 occurrence (yellow)

NEXT WEEK COMMITMENTS (USER MUST FILL)
  1. Fix for moved_stop: <user writes their commitment>
  2. Sizing change: <yes/no, justified>
  3. Strategies on probation: <list>

VERDICT
  CONTINUE | DOWNSIZE | HALT 1 WEEK | RETIRE_STRATEGY_<NAME>
================================================
```

## Step 7 — Persist to Drive

Use `mcp__gdrive__create_file` to write the memo to a "Risk Audits" folder with filename `risk-audit-YYYY-MM-DD.md`.

## Hard Rules

- Never approve "continue as-is" if rule violations repeated.
- Never auto-clear edge-decay flags. They persist until 3 consecutive weeks back inside MC bounds.
- Force the user to write the "next week commitments" section. Refuse to close the audit without them.
