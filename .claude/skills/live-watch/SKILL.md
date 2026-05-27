---
name: live-watch
description: Auto-activates on prompts like "watch X", "alert me if Y", "keep an eye on my book", "monitor SPY for breakout". Sets up a polling loop that checks specified conditions during market hours and surfaces alerts when thresholds are breached. This is not push-streaming; it is structured periodic polling, designed for Claude's request-response model.
---

# Live Watch

## What this skill does

Sets up a structured monitoring loop. Every N minutes during market hours, the sidekick checks the specified conditions and surfaces alerts when triggered. This is **polling**, not streaming — Claude operates on request-response.

## Workflow

### Step 1 — Define the watch
Ask (or accept) from the user:

1. **What to watch**:
   - Current positions (default if unspecified)
   - A specific ticker or list
   - A macro condition (e.g., "if SPY breaks below 20D SMA")
2. **Trigger conditions** (must be numeric):
   - Price level breaches (above/below)
   - % move from current
   - Volume z-score > X
   - VIX above/below
   - Spread widening past X bps
   - Multi-timeframe convergence change
3. **Poll interval**:
   - Default: 5 minutes
   - Faster: 1 minute (but watch context bloat)
   - Slower: 15 minutes for swing-style watches
4. **Watch duration**:
   - Default: until market close today
   - Or: until a condition triggers
5. **What to do on trigger**:
   - Default: surface alert + recommended next step (NEVER auto-trade)
   - Optional: invoke `pre-trade-checklist` if user pre-approved that path

Confirm the watch parameters back to the user before starting.

### Step 2 — Pre-flight checks
- Confirm market is open (compute from broker calendar; if closed, schedule watch to start at next open and notify)
- Confirm IBKR MCP is reachable: `mcp__interactive-brokers__get_account_summary`
- Confirm CLAUDE.md halts are not active

### Step 3 — Run the watch loop

For each poll cycle:

```
For each ticker/condition:
  1. Pull current snapshot via mcp__interactive-brokers__get_price_snapshot
  2. Evaluate each trigger condition numerically
  3. If triggered → continue to Step 4
  4. If not triggered → log a one-line status; sleep for interval
```

Use bash sleep between cycles. Each cycle is one Claude turn; the loop is achieved by Claude continuing to invoke the watch on its own schedule, or by the user prompting "check the watch" periodically. Be honest that this is polling — long-duration unattended loops are not practical.

### Step 4 — On trigger

```
=================================================
TRIGGER FIRED — <timestamp>
=================================================
Ticker:           <SYM>
Trigger:          <condition description>
Current:          <price> | <volume z>
Triggered value:  <numeric>

CONTEXT
  Cross-asset:    <one line from cross-asset-analyst>
  Regime:         <one line from market-regime-analyst>
  Microstructure: <spread state, volume profile>
  Multi-TF:       <convergence verdict at trigger>

RECOMMENDED NEXT STEP
  <none of the below auto-trade; the user must explicitly invoke>
  - Run pre-trade-checklist with proposed entry / stop / target
  - Adjust an existing position stop
  - Do nothing — note in journal
  - Cancel the watch
=================================================
```

### Step 5 — Honest constraints

State these up front when setting up any watch:

- Claude is request-response. The watch does not run in the background indefinitely. Practical max is ~6 hours of attended polling per session.
- Poll intervals < 1 minute are not useful for Claude — round-trip latency is too high.
- The watch can miss events between polls. If the trader needs sub-minute precision, IBKR's own alert system (or a dedicated event-driven script outside Claude) is the right tool.
- Watch loops consume context. After ~50 cycles, start a fresh session and re-state the watch.

## Output Format (initial setup confirmation)

```
LIVE-WATCH SET
=================================================
What:           <description>
Tickers:        <list>
Triggers:       <list with numeric thresholds>
Poll interval:  <N> minutes
Duration:       <until market close|until trigger|N hours>
On trigger:     surface alert + recommend pre-trade-checklist

First poll in <N> minutes. I will surface a one-line status on each poll
and the full TRIGGER format only when a condition is hit.
=================================================
```

## Hard Rules

- Never auto-execute on a trigger. A trigger surfaces the alert and recommends the user invoke `pre-trade-checklist`. The Panel still gates the trade.
- Never run a watch if the daily/weekly/monthly halt is active. Refuse and explain.
- Never poll an instrument the user hasn't authorized in CLAUDE.md.
- Always state the poll interval and the inherent miss risk. Trader needs to understand the tradeoff.
- Every triggered alert gets written to the journal with timestamp and current context — even if the user takes no action.
- If the user asks to extend a watch indefinitely or set it to "always running," refuse. Long unattended loops are not appropriate use of an LLM sidekick.
