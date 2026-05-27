---
name: pre-trade-checklist
description: Auto-activates whenever the user proposes buying or selling a specific ticker, or asks whether to enter a trade. Runs the full pre-trade workflow including invoking the four-specialist panel. Refuses to be skipped.
---

# Pre-Trade Checklist

When the user proposes a specific trade (e.g., "long AAPL at 220 stop 215 target 232"), walk through every step below in order. Do not skip. Do not summarize four into one. Each step must produce a numeric output.

## Step 1 — Parse the proposed trade

Extract from the user's message:
- Symbol
- Side (long / short)
- Entry price (or "market")
- Stop price (REQUIRED — refuse to proceed if missing)
- Target price (REQUIRED — refuse to proceed if missing)
- Time horizon (intraday, swing, position)

If any of the above is missing, ask one clarifying question and stop until answered.

## Step 2 — Confirm strategy match

Check `data/strategies/*.yaml`. Does this trade fit one of the approved strategies?
- If YES: name the strategy and note which conditions are satisfied.
- If NO: REJECT the trade. Tell the user "this trade does not match any approved strategy. Define one in data/strategies/ first, then re-propose."

## Step 3 — Regime + cross-asset + multi-timeframe context (consulting, no vote)

Invoke ALL of these in parallel as context for the Panel:

- `market-regime-analyst` — today's regime + strategy fit table
- `cross-asset-analyst` — confirms or contradicts the equity thesis via VIX, DXY, TLT, sector ETFs
- `multi-timeframe-analyst` — convergence/divergence across 5m / 1h / 1d / 1w
- If this is an options trade: `options-strategist` — IV rank, expected move, structure validation (MANDATORY for any options trade)
- If this would add to an already-exposed sector or factor: `portfolio-risk-decomposer` — surfaces concentration risk
- If entry is intraday: `microstructure-analyst` — spread, liquidity, timing advice

Surface conflicts prominently. If cross-asset CONTRADICT or multi-timeframe CONFLICT, that's a Panel-level concern.

## Step 4 — Invoke the four-specialist Panel IN PARALLEL

Spawn all four subagents simultaneously. Each receives the proposed trade AND the analytical context from Step 3. Collect verdicts:

- `quant-builder` → math, sizing, R:R, Kelly fraction
- `risk-officer` → veto check against all limits + portfolio-risk-decomposer findings
- `behavioral-coach` → journal pattern check
- `skeptical-pm` → thesis-killer hunt

## Step 5 — Synthesize the Pre-Trade Card

Render this exact format:

```
==========================================
PRE-TRADE CARD — <SYMBOL> <SIDE>
==========================================
Strategy:  <name>   (regime fit today: <SUPPORTED|NEUTRAL|UNSUPPORTED>)
Entry:     $<E>
Stop:      $<S>   (risk per share: $<E-S>)
Target:    $<T>   (R:R = <T-E>/<E-S> = <X>)
Size:      <N> shares = $<notional>
Risk $:    $<dollars>  (<pct>% of equity)

ANALYTICAL CONTEXT
  Regime:          <one line from market-regime-analyst>
  Cross-asset:     <CONFIRM|CAUTION|CONTRADICT> — <one line>
  Multi-timeframe: <STRONG|MODERATE|WEAK|CONFLICT> convergence
  Options (if applicable): <one line from options-strategist incl. IV rank + structure>
  Microstructure (if intraday): <GREEN|YELLOW|RED> + order routing
  Portfolio concentration (if applicable): <one line from portfolio-risk-decomposer>

PANEL VERDICTS
  Quant Builder    : <PASS|FAIL|NEEDS_INPUT>  — <one line reason>
  Risk Officer     : <APPROVE|VETO|CHANGES>   — <one line reason>
  Behavioral Coach : <GREEN|YELLOW|RED>       — <one line reason>
  Skeptical PM     : <APPROVE|VETO|MORE_WORK> — <one line reason>

UNANIMOUS APPROVE? <YES | NO>
==========================================
```

## Step 6 — Decision

- **All four APPROVE / PASS / GREEN** → Write the proposed trade to `data/journal.db` as a pending entry, then say:
  > "Pre-trade card written to journal. To submit the paper order, reply with: CONFIRM PAPER ORDER"
  > Wait. Do not call `mcp__interactive-brokers__create_order_instruction` until the user replies with that exact phrase. (In paper mode the PreToolUse hook allows it; in live mode it also requires the `EXECUTE LIVE: ...` phrase per Hard Rule #1, and IBKR still confirms in its own interface.)

- **Any specialist vetoes** → Do NOT write to the journal. Surface every dissent verbatim. End with:
  > "This trade did not clear unanimous approval. To override a specific veto, you must address that specialist's stated concern with new evidence — not just a stronger opinion."

## Refusal protocol

If the user tries to skip this checklist ("just place the order," "I know what I'm doing," "we already checked this"):

> I will not skip the pre-trade checklist. The specific failure mode I'm avoiding is: you taking an unsized, unstopped, or unjournaled trade based on a feeling. Reapply the four-specialist mandate from CLAUDE.md. If you believe the checklist is wrong, edit it in `.claude/skills/pre-trade-checklist/SKILL.md` BEFORE the trade, never during.
