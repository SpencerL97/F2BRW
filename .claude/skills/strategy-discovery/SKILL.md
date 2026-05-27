---
name: strategy-discovery
description: Auto-activates on prompts like "propose a new strategy", "I need a new edge", "what should I trade", or after a strategy is retired. Runs the full Phase 2 edge hypothesis workflow with the strategy-researcher and the four-specialist panel.
---

# Strategy Discovery

This is the only skill that can add a new strategy to `data/strategies/`. Trades cannot execute outside an approved strategy, so this gate is where everything starts.

## Step 1 — Pre-flight check

Read `data/strategies/*.yaml`.
- If there are ≥ 5 active strategies, REFUSE to add another. Tell the user: "You have a saturation problem, not an edge problem. Retire one first."
- If the user has logged < 30 trades in the last 90 days, ask: "Are you sure you need a new strategy, or do you need to execute the existing one more consistently?"

## Step 2 — Discovery interview

Ask the user, one cluster at a time, waiting for answers:

1. **What gap are you trying to fill?**
   - Existing strategies are unsupported in current regime? Strategy retired? Capacity issue? Boredom? (Boredom is a red flag — do not proceed if that's the answer.)

2. **What you've seen recently** — one or two market phenomena you noticed that *might* be exploitable. (Don't accept "I have a feeling." Force a specific observation with a ticker, a timeframe, and a pattern.)

3. **Constraints** — time per day, intraday vs EOD, options/equity/crypto, capital allocation cap for this strategy.

## Step 3 — Invoke `strategy-researcher`

Pass the user's answers. The researcher returns 2–3 candidates in the standard template.

## Step 4 — Invoke `market-regime-analyst`

For each candidate, get the regime fit assessment: does the current regime even support this candidate? If not, would it be a strategy you sit out for months at a time? That's fine if disclosed.

## Step 5 — Invoke the four-specialist panel on each candidate

For each candidate from the researcher:
- `quant-builder` → backtest feasibility, math soundness, sample size requirements
- `risk-officer` → can this be sized within the trader's risk limits? Capacity issues?
- `behavioral-coach` → does this strategy match the trader's psychology, or will it trigger known failure modes?
- `skeptical-pm` → why is this not already arbitraged? What's the trader missing?

## Step 6 — Synthesize the comparison table

```
==========================================
STRATEGY DISCOVERY — <date>
==========================================
Candidate A: <name>
  Edge prob:       55% real / 35% artifact / 10% arbed
  Regime fit:      SUPPORTED today, ~6mo/year historically
  Quant:           PASS — backtest feasible, 5yr daily data sufficient
  Risk:            APPROVE — sizable within 1% per trade cap
  Behavioral:      YELLOW — requires patience, trader's journal shows impatience flag
  Skeptical:       NEEDS_MORE_WORK — could be a known factor, not a true edge

Candidate B: <name>
  ...

Candidate C: <name>
  ...
==========================================
RECOMMENDATION FOR USER:
  - If you pick A: address the behavioral flag with a rule (e.g., "no checking position until EOD")
  - If you pick B: ...
  - If you pick none: that is a valid answer.
```

## Step 7 — User chooses (or declines)

If user chooses one:
1. Generate a complete `data/strategies/strategy_NNN.yaml` from the template, status `paper_only`, with all decay/retirement conditions filled in.
2. Tell the user: "Strategy is paper_only. It cannot trade until you complete the backtest stats fields in the YAML AND the strategy passes 30 paper trades within the graduation criteria."

If user declines all three:
> "Good call. Strategy discovery without a real gap is how books get bloated. Re-run when conditions change."

## Hard Rules

- Never auto-mark a new strategy `active`. New strategies are always `paper_only` until graduation criteria are met.
- Never let the user write the edge statement themselves with hand-waving. The researcher writes it; the user accepts or rejects.
- Never propose a strategy that conflicts with an existing approved strategy (e.g., long momentum + short momentum on same universe).
- Strategy discovery is rare. Doing it more than once every 60 days is a sign of unfocused trading. Flag it.
