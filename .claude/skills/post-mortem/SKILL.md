---
name: post-mortem
description: Auto-activates after any losing trade closes and on prompts like "post-mortem", "what went wrong", "analyze that trade". Forces a structured analysis instead of letting the trader either ignore the loss or spiral about it.
---

# Post-Mortem

The point of a post-mortem is to separate **process losses** (followed the rules, lost anyway — this is fine, do it again) from **rule-violation losses** (broke the system, lost — must fix the system).

## Step 1 — Pull the closed trade

```bash
sqlite3 data/journal.db "
  SELECT id, symbol, side, qty, entry, stop, target, exit_price, pnl, r_multiple,
         strategy, thesis, emotion_pre, emotion_post, rule_violations, notes
  FROM trades
  WHERE id = <trade_id>;
"
```

If no trade_id given, default to the most recent closed losing trade.

## Step 2 — Classify the loss

Compute and surface:

```
LOSS CLASSIFICATION
-------------------
Process clean? <YES if rule_violations = 'none', else NO>
R-multiple:    <r>R (expected by strategy: <X>R)
Within normal Monte Carlo band for this strategy? <YES|NO>
Strategy was SUPPORTED by regime that day? <YES|NO> — use market-regime-analyst
Emotion delta: <emotion_pre> → <emotion_post>
```

## Step 3 — Match against retail blowup archetypes

For each of these, check the trade record and surface evidence:
- Was the stop moved? (compare original stop in pre-trade card to actual exit logic)
- Was size at or above cap?
- Was this trade taken within 60 minutes of the previous loss?
- Was the thesis written BEFORE entry or rationalized after?
- Did the trader add to the position after it moved against them?

## Step 4 — Determine the lesson

```
LESSON CATEGORY: <one of below>
  CLEAN_PROCESS_LOSS   — followed rules, market didn't cooperate. Action: nothing. Do it again.
  RULE_VIOLATION       — broke a specific rule. Action: identify the rule, update behavior, add safeguard.
  STRATEGY_DECAY       — strategy losing outside MC bounds. Action: flag, run risk-audit, possibly retire.
  REGIME_MISMATCH      — strategy was UNSUPPORTED that day. Action: tighten when-to-trade rules.
  PSYCHOLOGICAL        — emotional state drove entry/exit. Action: behavioral coaching, possibly time-out.
```

## Step 5 — Write the post-mortem note to the journal

Append to the `notes` column via the parameterized helper (safe with apostrophes):
```bash
python scripts/journal.py note --id <trade_id> \
  --text "POST-MORTEM: <category>. Lesson: <one sentence>. Action: <specific change to make>."
```

## Step 6 — If category is RULE_VIOLATION or PSYCHOLOGICAL

Before allowing the trader to place another trade:
1. Require them to articulate the specific rule that was broken.
2. Require a written safeguard (e.g., "I will not enter a trade within 60 min of a loss" → added as a tag the behavioral-coach watches for).
3. Optionally add a 24-hour cooling-off period — trader can override but the override is logged.

## Output Format

```
==========================================
POST-MORTEM — Trade #<id> <SYMBOL> <SIDE>
==========================================
Result:        <pnl> ($) | <r>R
Strategy:      <name>
Process clean: <YES|NO>

WHAT HAPPENED
  <2-3 sentences of factual reconstruction>

WHAT THE DATA SHOWS
  - <archetype>: <evidence>
  - <archetype>: <evidence>

CATEGORY: <one of the five>

LESSON
  <one specific sentence the trader could put on a sticky note>

ACTION
  <one specific change to make, with an owner: the trader, the YAML, or the constitution>
==========================================
```

## Hard Rules

- Never close a post-mortem without an entry in the `notes` field of the journal.
- Never categorize as CLEAN_PROCESS_LOSS unless rule_violations = 'none' AND the R-multiple is within normal MC band.
- If 3 of the last 10 trades are PSYCHOLOGICAL category, recommend the trader take a 1-week halt. The behavioral-coach has veto power on the next trade until the halt is observed.
- Never tell the trader "you'll get it next time" or any equivalent. State the data, name the category, prescribe the action.
