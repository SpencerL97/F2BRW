# Setup — running the Trading Sidekick with Claude Code

This is the complete first-run walkthrough. The README quickstart is the condensed version; this
file spells out every step, including the Claude Code trust/approval prompts that trip people up.

**The single most important rule:** Claude Code only loads this project — `CLAUDE.md`, the 15
agents in `.claude/agents/`, the 8 skills in `.claude/skills/`, the safety hook, and the MCP
servers in `.mcp.json` — when you run `claude` **from the repo root**. Launch it anywhere else and
none of it activates.

---

## 1. Prerequisites

- **Python 3.11+**
- **Node 18+**, then the Claude Code CLI:
  ```bash
  npm install -g @anthropic-ai/claude-code
  ```
- An **Anthropic account** for Claude Code (you'll sign in on first launch).
- An **Interactive Brokers account** with API access enabled. A **paper** account is fine and is
  the recommended starting point.
- Accounts/keys for the other data MCPs you intend to use (FMP, Bigdata, Wolfram, etc.). You can
  start with just IBKR + FMP and add the rest later — agents degrade gracefully when a tool is
  missing (they say "I don't have that" rather than fabricate; `CLAUDE.md` Hard Rule #7).

## 2. Clone the repo

```bash
git clone https://github.com/SpencerL97/F2BRW.git
cd F2BRW
# optionally: git checkout main   (or whichever branch you run from)
```

The repo root **is** the project. From here on, every command and every `claude` launch happens
from inside `F2BRW/`.

## 3. Python environment + dependencies

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## 4. Initialize the journal and config

```bash
python scripts/init_db.py          # creates data/journal.db (gitignored)
cp .env.template .env              # then edit .env
chmod +x .claude/hooks/*.sh        # make the live-order safety gate executable
```

In `.env`, leave `TRADING_MODE=paper` for now. `DEFAULT_EQUITY` is used for sizing math before a
live account balance is pulled. `.env` is gitignored — never commit real keys.

## 5. First launch + trust prompts

```bash
claude
```

On the **first launch inside this folder**, Claude Code will prompt you to:

1. **Trust the workspace folder** — yes.
2. **Allow the project `.claude/settings.json`**, which registers a `PreToolUse` hook
   (`.claude/hooks/pre-tool-use.sh`). Review it and approve — this hook is the second gate that
   blocks live orders without the confirmation phrase.
3. **Enable the project MCP servers** declared in `.mcp.json` (10 of them). Approve.

If you skip the MCP approval, the data tools simply won't be available and the agents will tell you
so.

## 6. Authenticate the data/broker MCPs

In the running session:

```
/mcp
```

This opens the MCP panel. Authenticate each remote server via browser OAuth:

```
interactive-brokers   fmp   bigdata   wolfram   crypto-com
coindesk   lunarcrush   indeed   gcal   gdrive
```

A server shows **connected** once OAuth succeeds. Re-run `/mcp` any time one shows "failed" to
re-authenticate.

> **Unusual Whales (optional):** if you subscribe, put your key in `.env`
> (`UNUSUAL_WHALES_API_KEY=...`) and add the `unusual-whales` stdio block to `.mcp.json` — the stub
> server is in `mcp_servers/unusual_whales_mcp/`. Without it, `flow-analyst` and `insider-watcher`
> just report that options-flow/dark-pool data is unavailable.

## 7. Confirm everything loaded

```
/agents
```

You should see all 15: `quant-builder`, `risk-officer`, `behavioral-coach`, `skeptical-pm`,
`market-regime-analyst`, `strategy-researcher`, `options-strategist`, `microstructure-analyst`,
`multi-timeframe-analyst`, `portfolio-risk-decomposer`, `cross-asset-analyst`, `flow-analyst`,
`insider-watcher`, `social-scout`, `news-hawk`.

Skills load automatically from `.claude/skills/` — you don't enable them by hand. They activate on
natural phrasing (see §9).

## 8. Fill in your profile and define a strategy

- Open `CLAUDE.md` → the **Trader Profile** section. Fill in capital at risk and the loss limits.
  `risk-officer` enforces these literally, so put in real numbers.
- Create at least one approved strategy — **trades are rejected if they don't match one**:
  ```bash
  cp data/strategies/strategy_001.yaml.template data/strategies/strategy_001.yaml
  ```
  Edit it fully. Until the backtest metric fields are filled, `quant-builder` returns `NEEDS_INPUT`
  on any trade using it, and new strategies stay `paper_only` until they clear the graduation gates.

## 9. Drive it

You talk to the main session in plain English; it routes to the right skill, which fans out to the
agents. Good first prompts:

| You say | What happens |
|---|---|
| *"Run daily-debrief."* | Account, positions, regime, calendar, behavioral pulse |
| *"Deep dive on the market."* | 4 scanner agents in parallel → ranked signal report |
| *"I'm considering long NVDA at 145, stop 140, target 158 via strategy_001."* | Analytical specialists + the 4-vote Panel → Pre-Trade Card |
| *"Watch SPY, alert me if it breaks 5800 with volume z > 2."* | A `live-watch` polling loop |
| *"Risk audit."* | Weekly per-strategy verdict (forces next-week commitments) |

You can also target one agent directly, e.g. *"have the options-strategist look at TSLA Jun calls."*

## 10. Paper → live (when you're ready)

Live trading has three gates, by design:

1. `TRADING_MODE=live` in `.env`, **and**
2. the exact per-order phrase `EXECUTE LIVE: <TICKER> <BUY|SELL> <QTY>` in your prompt (the hook
   enforces this), **and**
3. IBKR's own confirmation in its interface.

Don't flip to live until a strategy meets the graduation criteria in its YAML (≥30 paper trades,
≥60 days, live expectancy within 30% of backtest, etc.). Then start at ¼ size.

---

## Optional: verify the local pieces work without the MCPs

These don't need any server auth and are a quick sanity check after install:

```bash
python scripts/aggregate_signals.py --bootstrap        # prints the scoring framework
python scripts/unusual_volume.py AAPL                  # needs network + yfinance

# the order-gating hook (should ALLOW in paper, BLOCK in live without the phrase):
CLAUDE_TOOL_NAME=mcp__interactive-brokers__create_order_instruction \
  CLAUDE_USER_PROMPT="buy NVDA" TRADING_MODE=paper bash .claude/hooks/pre-tool-use.sh; echo "exit=$?"
CLAUDE_TOOL_NAME=mcp__interactive-brokers__create_order_instruction \
  CLAUDE_USER_PROMPT="buy NVDA" TRADING_MODE=live  bash .claude/hooks/pre-tool-use.sh; echo "exit=$?"
```

## Troubleshooting

- **Agents/skills don't show up** → you launched `claude` outside the repo root. `cd` into `F2BRW/`
  and relaunch.
- **MCP shows "failed"** → `/mcp` and re-authenticate.
- **A subagent can't find a tool** → the tool name must be `mcp__<server-key>__<tool>`, where the
  server key comes from `.mcp.json` (e.g. `mcp__interactive-brokers__get_account_summary`).
- **Hook not blocking live orders** → `chmod +x .claude/hooks/*.sh` and confirm
  `.claude/settings.json` is valid JSON.
- **IBKR data sparse / no options data** → check your IBKR market-data subscriptions (real-time
  options need OPRA).

See the README's "Honest limitations" for what this tool deliberately does **not** do.
