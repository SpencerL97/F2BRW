#!/usr/bin/env python3
"""Initialize the journal database. Idempotent — safe to run repeatedly."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "journal.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entry_time TEXT NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  qty REAL NOT NULL,
  entry REAL NOT NULL,
  stop REAL NOT NULL,
  target REAL,
  exit_time TEXT,
  exit_price REAL,
  outcome TEXT,
  pnl REAL,
  r_multiple REAL,
  strategy TEXT NOT NULL,
  thesis TEXT NOT NULL,
  emotion_pre TEXT,
  emotion_post TEXT,
  rule_violations TEXT,
  notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy);

CREATE TABLE IF NOT EXISTS debriefs (
  date TEXT PRIMARY KEY,
  equity REAL,
  day_pnl REAL,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS pending_trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  qty REAL NOT NULL,
  entry REAL NOT NULL,
  stop REAL NOT NULL,
  target REAL NOT NULL,
  strategy TEXT NOT NULL,
  thesis TEXT NOT NULL,
  quant_verdict TEXT,
  risk_verdict TEXT,
  behavior_verdict TEXT,
  skeptical_verdict TEXT,
  resolved INTEGER DEFAULT 0
);
"""

def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)
    con.commit()
    con.close()
    print(f"Database initialized at {DB_PATH}")

if __name__ == "__main__":
    main()
