#!/usr/bin/env python3
"""Parameterized journal writer for the trading sidekick.

Why this exists: the skills must record free text (thesis, notes) that frequently
contains apostrophes ("couldn't hold support"). Building SQL by string interpolation
breaks on those and is an injection hazard. Every write here uses bound parameters,
and P&L / R-multiple are computed from the stored row so the model never hand-math
them inconsistently.

Subcommands:
  open      record a trade at entry        -> prints "Journal entry #<id> written."
  close     record a trade at exit         -> computes pnl + r_multiple
  pending   record a pre-trade card        -> prints "Pending trade #<id> written."
  note      append a line to trades.notes  (used by post-mortem)
  debrief   upsert today's debriefs row     (used by daily-debrief)

Examples:
  python scripts/journal.py open --symbol NVDA --side long --qty 100 \\
    --entry 145 --stop 140 --target 158 --strategy strategy_001 \\
    --thesis "20d breakout, regime supported" --emotion-pre "3 calm"
  python scripts/journal.py close --id 12 --exit 158 --outcome win \\
    --emotion-post "3 satisfied" --rule-violations none --notes "hit target, clean"
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "journal.db"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        sys.exit(f"journal db not found at {DB_PATH}. Run: python scripts/init_db.py")
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def cmd_open(a) -> None:
    con = _connect()
    cur = con.execute(
        """INSERT INTO trades
           (entry_time, symbol, side, qty, entry, stop, target, outcome,
            strategy, thesis, emotion_pre)
           VALUES (?,?,?,?,?,?,?, 'open', ?,?,?)""",
        (_now(), a.symbol.upper(), a.side, a.qty, a.entry, a.stop, a.target,
         a.strategy, a.thesis, a.emotion_pre),
    )
    con.commit()
    print(f"Journal entry #{cur.lastrowid} written.")
    con.close()


def cmd_close(a) -> None:
    con = _connect()
    row = con.execute(
        "SELECT side, qty, entry, stop, outcome FROM trades WHERE id = ?", (a.id,)
    ).fetchone()
    if row is None:
        con.close()
        sys.exit(f"No trade with id {a.id}.")
    if row["outcome"] != "open":
        con.close()
        sys.exit(f"Trade #{a.id} is already closed (outcome={row['outcome']}). Refusing to overwrite.")

    side = (row["side"] or "long").lower()
    qty, entry, stop = row["qty"], row["entry"], row["stop"]
    direction = 1 if side == "long" else -1
    pnl = (a.exit - entry) * qty * direction
    risk_per_share = abs(entry - stop)
    r_multiple = ((a.exit - entry) * direction / risk_per_share) if risk_per_share else None

    con.execute(
        """UPDATE trades
           SET exit_time = ?, exit_price = ?, outcome = ?, pnl = ?, r_multiple = ?,
               emotion_post = ?, rule_violations = ?, notes = ?
           WHERE id = ?""",
        (_now(), a.exit, a.outcome, round(pnl, 2),
         round(r_multiple, 3) if r_multiple is not None else None,
         a.emotion_post, a.rule_violations, a.notes, a.id),
    )
    con.commit()
    con.close()
    r_str = f"{r_multiple:+.2f}R" if r_multiple is not None else "n/a (zero risk)"
    print(f"Trade #{a.id} closed: pnl={pnl:+.2f}, {r_str}.")


def cmd_pending(a) -> None:
    con = _connect()
    cur = con.execute(
        """INSERT INTO pending_trades
           (created_at, symbol, side, qty, entry, stop, target, strategy, thesis,
            quant_verdict, risk_verdict, behavior_verdict, skeptical_verdict, resolved)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?, 0)""",
        (_now(), a.symbol.upper(), a.side, a.qty, a.entry, a.stop, a.target,
         a.strategy, a.thesis, a.quant_verdict, a.risk_verdict,
         a.behavior_verdict, a.skeptical_verdict),
    )
    con.commit()
    print(f"Pending trade #{cur.lastrowid} written.")
    con.close()


def cmd_note(a) -> None:
    con = _connect()
    if con.execute("SELECT 1 FROM trades WHERE id = ?", (a.id,)).fetchone() is None:
        con.close()
        sys.exit(f"No trade with id {a.id}.")
    con.execute(
        "UPDATE trades SET notes = CASE "
        "WHEN notes IS NULL OR notes = '' THEN ? "
        "ELSE notes || ' | ' || ? END "
        "WHERE id = ?",
        (a.text, a.text, a.id),
    )
    con.commit()
    con.close()
    print(f"Note appended to trade #{a.id}.")


def cmd_debrief(a) -> None:
    con = _connect()
    con.execute(
        """INSERT INTO debriefs (date, equity, day_pnl, notes)
           VALUES (?,?,?,?)
           ON CONFLICT(date) DO UPDATE SET
               equity = excluded.equity,
               day_pnl = excluded.day_pnl,
               notes = excluded.notes""",
        (a.date or _today(), a.equity, a.day_pnl, a.notes),
    )
    con.commit()
    con.close()
    print(f"Debrief recorded for {a.date or _today()}.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("open", help="record a trade at entry")
    p.add_argument("--symbol", required=True)
    p.add_argument("--side", required=True, choices=["long", "short"])
    p.add_argument("--qty", type=float, required=True)
    p.add_argument("--entry", type=float, required=True)
    p.add_argument("--stop", type=float, required=True)
    p.add_argument("--target", type=float)
    p.add_argument("--strategy", required=True)
    p.add_argument("--thesis", required=True)
    p.add_argument("--emotion-pre", dest="emotion_pre", required=True,
                   help='e.g. "3 calm"')
    p.set_defaults(func=cmd_open)

    p = sub.add_parser("close", help="record a trade at exit (computes pnl + R)")
    p.add_argument("--id", type=int, required=True)
    p.add_argument("--exit", type=float, required=True)
    p.add_argument("--outcome", required=True,
                   choices=["win", "loss", "breakeven"])
    p.add_argument("--emotion-post", dest="emotion_post", required=True)
    p.add_argument("--rule-violations", dest="rule_violations", default="none")
    p.add_argument("--notes", default="")
    p.set_defaults(func=cmd_close)

    p = sub.add_parser("pending", help="record a pre-trade card")
    p.add_argument("--symbol", required=True)
    p.add_argument("--side", required=True, choices=["long", "short"])
    p.add_argument("--qty", type=float, required=True)
    p.add_argument("--entry", type=float, required=True)
    p.add_argument("--stop", type=float, required=True)
    p.add_argument("--target", type=float, required=True)
    p.add_argument("--strategy", required=True)
    p.add_argument("--thesis", required=True)
    p.add_argument("--quant-verdict", dest="quant_verdict", default="")
    p.add_argument("--risk-verdict", dest="risk_verdict", default="")
    p.add_argument("--behavior-verdict", dest="behavior_verdict", default="")
    p.add_argument("--skeptical-verdict", dest="skeptical_verdict", default="")
    p.set_defaults(func=cmd_pending)

    p = sub.add_parser("note", help="append a line to a trade's notes")
    p.add_argument("--id", type=int, required=True)
    p.add_argument("--text", required=True)
    p.set_defaults(func=cmd_note)

    p = sub.add_parser("debrief", help="upsert today's debriefs row")
    p.add_argument("--equity", type=float)
    p.add_argument("--day-pnl", dest="day_pnl", type=float)
    p.add_argument("--notes", default="")
    p.add_argument("--date", help="YYYY-MM-DD (defaults to today, UTC)")
    p.set_defaults(func=cmd_debrief)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
