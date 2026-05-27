---
name: journal-entry
description: Auto-activates after every trade entry, every trade exit, and every "log this" prompt. Writes a structured row to data/journal.db. Refuses to skip required fields.
---

# Journal Entry

Every trade gets two journal rows: one at entry, one at exit. Neither can be skipped.

## Schema (created by scripts/init_db.py)

```sql
CREATE TABLE trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entry_time TEXT NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,           -- 'long' | 'short'
  qty REAL NOT NULL,
  entry REAL NOT NULL,
  stop REAL NOT NULL,
  target REAL,
  exit_time TEXT,
  exit_price REAL,
  outcome TEXT,                  -- 'win' | 'loss' | 'breakeven' | 'open'
  pnl REAL,
  r_multiple REAL,
  strategy TEXT NOT NULL,
  thesis TEXT NOT NULL,
  emotion_pre TEXT,              -- 1-5 scale + word
  emotion_post TEXT,
  rule_violations TEXT,          -- comma-separated, '' if none
  notes TEXT
);

CREATE TABLE debriefs (
  date TEXT PRIMARY KEY,
  equity REAL,
  day_pnl REAL,
  notes TEXT
);
```

## On Entry

Required fields (REFUSE TO PROCEED if any missing):
- symbol, side, qty, entry, stop, strategy, thesis (one sentence)
- emotion_pre: 1–5 + one word (e.g., "3 calm", "5 fomo")

Insert via the parameterized helper (handles apostrophes in the thesis safely — never
hand-build SQL with the free text):
```bash
python scripts/journal.py open \
  --symbol <SYM> --side <long|short> --qty <qty> \
  --entry <entry> --stop <stop> --target <target> \
  --strategy <strategy> --thesis "<one sentence>" --emotion-pre "<emo>"
```

It prints "Journal entry #<id> written." — surface that id to the trader.

## On Exit

Required fields:
- exit price, outcome ('win'|'loss'|'breakeven'), emotion_post, rule_violations (or 'none')
- notes: one sentence on what worked or didn't

`pnl` and `r_multiple` are computed by the helper from the stored side/entry/stop/qty
(long: `(exit-entry)*qty`; short inverted; `r = (exit-entry)/abs(entry-stop)` long, inverted
short). Do NOT compute them by hand.

```bash
python scripts/journal.py close \
  --id <id> --exit <exit> --outcome <win|loss|breakeven> \
  --emotion-post "<emo>" --rule-violations "<tags or none>" --notes "<one sentence>"
```

## Rule Violations — Predefined Tags

Use these exact strings (comma-separate if multiple):
- `moved_stop` — stop was widened after entry
- `no_stop` — entered without a stop
- `oversized` — position exceeded per-trade risk cap
- `revenge` — entered within 60min of a loss
- `averaged_down` — added to a loser
- `outside_strategy` — trade did not match an approved strategy
- `outside_session` — entered outside stated time windows
- `skipped_checklist` — pre-trade-checklist was bypassed
- `none` — clean trade

## Weekly Export to Drive

Every Friday after close, also write a markdown summary to Google Drive:

```
Title: Trading Journal — Week of YYYY-MM-DD
- Trades: N (Wins X / Losses Y)
- Week P&L: $Z
- Best trade: <symbol> +<R>R
- Worst trade: <symbol> -<R>R
- Rule violations: <count by tag>
- One thing to fix next week: <user input required>
```

Use `mcp__gdrive__create_file` to write to a "Trading Journal" folder.

## Refusal Protocol

If the user tries to skip emotion fields ("just log the trade, skip the feelings stuff"):

> Emotion fields are non-optional. Without them, the behavioral-coach has no signal to detect tilt cycles. One number, one word. That's it.
