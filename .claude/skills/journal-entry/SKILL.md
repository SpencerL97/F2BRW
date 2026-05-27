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

Insert via:
```bash
sqlite3 data/journal.db "
  INSERT INTO trades(entry_time, symbol, side, qty, entry, stop, target, outcome, strategy, thesis, emotion_pre)
  VALUES (datetime('now'), '<sym>', '<side>', <qty>, <entry>, <stop>, <target>, 'open', '<strategy>', '<thesis>', '<emo>');
"
```

Confirm with: "Journal entry #<id> written."

## On Exit

Required fields:
- exit_price, exit_time (auto), outcome ('win'|'loss'|'breakeven'), emotion_post, rule_violations (or 'none')
- notes: one sentence on what worked or didn't

Compute:
- `pnl = (exit_price - entry) * qty` for long, inverted for short
- `r_multiple = (exit_price - entry) / abs(entry - stop)` for long, inverted for short

Update via:
```bash
sqlite3 data/journal.db "
  UPDATE trades
  SET exit_time = datetime('now'),
      exit_price = <exit>,
      outcome = '<out>',
      pnl = <pnl>,
      r_multiple = <r>,
      emotion_post = '<emo>',
      rule_violations = '<v>',
      notes = '<notes>'
  WHERE id = <id>;
"
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
