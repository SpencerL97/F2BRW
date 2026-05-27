# Trading Sidekick

An institutional-grade trading research and execution agent built on Claude Code with Interactive Brokers as the broker/data backbone.

Paper-trading by default. Live orders require both `TRADING_MODE=live` in `.env` AND an explicit confirmation phrase per order. Even then, IBKR requires its own confirmation in the interface. Two gates, by design.

This is not a stock picker. It is a Panel of four specialists that can veto any trade, plus a roster of analytical specialists that produce institutional-grade context.

---

## Quickstart

### 1. Prereqs

- Python 3.11+
- Node 18+ (Claude Code CLI: `npm install -g @anthropic-ai/claude-code`)
- An IBKR account with API access enabled (paper account is fine)
- The IBKR MCP added to your Claude.ai connectors

### 2. Install

```bash
cd ~/trading-sidekick
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.template .env
# Edit .env: TRADING_MODE=paper to start (match this to your actual IBKR account type)

python scripts/init_db.py
chmod +x .claude/hooks/*.sh
```

### 3. Authenticate MCPs

```bash
claude
# In session:
/mcp     # Open the panel; authenticate each remote server via browser OAuth
         # interactive-brokers, fmp, bigdata, wolfram, crypto-com, coindesk,
         # lunarcrush, indeed, gcal, gdrive
```

If you have an Unusual Whales subscription, add your API key to `.env` and uncomment the `unusual-whales` block in `.mcp.json` (a stub server is in `mcp_servers/unusual_whales_mcp/`).

### 4. Configure profile

Open `CLAUDE.md` and fill in the **Trader Profile** section: capital at risk, per-trade %, daily/weekly/monthly limits, allowed instruments. The risk-officer enforces these.

### 5. Define a strategy

```bash
cp data/strategies/strategy_001.yaml.template data/strategies/strategy_001.yaml
# Edit it. Until you fill in backtest metrics, quant-builder returns NEEDS_INPUT
# on any trade that uses it. By design.
```

### 6. First session

```bash
claude
```

Try in order:
1. *"Run daily-debrief."* — pulls IBKR state, calendar, regime, behavioral pulse
2. *"Deep dive on the market."* — fans out 4 scanners in parallel, aggregates with proper statistical weighting
3. *"I'm considering long NVDA at 145 stop 140 target 158 via strategy_001."* — invokes regime / cross-asset / multi-timeframe analysts THEN the four-specialist Panel. You'll get a Pre-Trade Card.
4. *"Watch SPY and alert me if it breaks 5800 with volume z > 2."* — sets up a live-watch loop.
5. End of day: *"Daily debrief, then journal anything open."*
6. End of week: *"Risk audit."*

---

## The Team

### Voting Panel (any one can veto)
- **quant-builder** — math, sizing, R:R, Kelly fraction
- **risk-officer** — limits + concentration; default answer is no
- **behavioral-coach** — journal patterns, tilt detection
- **skeptical-pm** — thesis-killer hunt

### Consulting Specialists (no vote, inform decisions)
- **market-regime-analyst** — bull/bear/vol/breadth/rate classification
- **strategy-researcher** — Phase 2 edge hypothesis for new strategies

### Real-Time Analytical Specialists (IBKR-powered)
- **options-strategist** — IV rank, term structure, skew, expected move, structure selection
- **microstructure-analyst** — spread, tape reading, intraday volume profile, order routing
- **multi-timeframe-analyst** — 5m/1h/1d/1w convergence detection
- **portfolio-risk-decomposer** — sector + factor + correlation + beta + implicit macro bets
- **cross-asset-analyst** — VIX/DXY/TLT/HYG/sector confirmation or contradiction

### Signal Scanners (parallel research, invoked by deep-dive)
- **flow-analyst** — volume z-scores, 13F changes, options/dark-pool (if UW)
- **insider-watcher** — Form 4 cluster buys, congress, 13D/G
- **social-scout** — Reddit, Stocktwits, X (web search), LunarCrush
- **news-hawk** — material news, analyst, transcripts, calendar

### Skills (auto-activating workflows)
- **pre-trade-checklist** — fires on any trade proposal
- **daily-debrief** — fires at session start
- **deep-dive** — fires on "scan for signals" / "deep dive on X"
- **live-watch** — fires on "watch X" / "alert me if Y"
- **journal-entry** — fires post entry/exit
- **risk-audit** — fires Fridays / on demand
- **strategy-discovery** — fires on "propose new strategy"
- **post-mortem** — fires after losing trades

### Free data scanners (Python scripts)
- `scripts/scan_reddit.py` — public Reddit JSON
- `scripts/scan_stocktwits.py` — public Stocktwits API
- `scripts/unusual_volume.py` — yfinance volume z-scores
- `scripts/aggregate_signals.py` — composite scoring with recency decay, cross-source corroboration

### Optional paid integrations
- `mcp_servers/unusual_whales_mcp/` — drop in API key to activate UW options flow + dark pool

---

## Hooks (deterministic safety)

`.claude/hooks/pre-tool-use.sh` blocks IBKR `create_order_instruction` and `delete_order_instruction` calls unless:
- `TRADING_MODE=paper` in `.env`, OR
- The user's prompt contains `EXECUTE LIVE: <TICKER> <BUY|SELL> <QTY>`

This is the second gate. IBKR's own confirmation in the interface is the third.

---

## Paper graduation criteria

The default in `strategy_001.yaml.template`:
- ≥ 30 paper trades
- ≥ 60 trading days
- Live expectancy within 30% of backtested
- Live max drawdown within 30% of backtested
- Live fill slippage within 10 bps of backtest assumption

When all met, you may flip `TRADING_MODE=live`. Start at ¼ size for the first 30 live days; scale only after milestones.

---

## What this does NOT do

- It does not predict prices.
- It does not run autonomously while you sleep.
- It does not generate strategies from thin air — you author them, the strategy-researcher proposes candidates.
- It does not make you a great trader. It makes it structurally hard to be a sloppy one.

---

## Why these rules? (research basis)

Every empirical claim the specialists rely on is documented — with sources, effect sizes, and honest
caveats — in [`docs/research-notes.md`](docs/research-notes.md): Kelly sizing, insider-buy alpha
(and the routine-vs-opportunistic refinement), the variance risk premium behind the options rules,
momentum and momentum crashes, volume z-scores, the behavioral failure modes the coach hunts for,
and backtest-overfitting discipline. Short version: the edges are small, period-dependent, and decay
after publication — which is exactly why this tool is built around process, not prediction.

---

## Troubleshooting

- **MCP shows "failed"** — open `/mcp` panel, re-authenticate.
- **A tool isn't found by a subagent** — verify the tool name format `mcp__<server-key>__<tool>` matches what `/mcp` shows. Server keys come from `.mcp.json`.
- **Hook not blocking** — `chmod +x .claude/hooks/*.sh`. Verify `.claude/settings.json` is valid JSON.
- **IBKR data sparse** — confirm market data subscriptions in your IBKR account portal. Some venues require explicit subscription.
- **Subagent doesn't see real-time options data** — IBKR options data requires the OPRA subscription (~$5/mo per exchange tier) for non-pro retail users.

---

## Honest limitations

- LLM round-trips are seconds, not microseconds. This is for swing/position/options trading, not scalping.
- The `live-watch` loop is structured polling, not push-streaming. Practical max session length ~6 hours of attended polling.
- Cross-asset signals can break in regime changes; past correlations are not future facts.
- Insider/congress signals have known lag and modest historical alpha. Use them as one input, never the trigger.
- "AI" does not give you institutional edge. Process discipline does.
