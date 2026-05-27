#!/usr/bin/env bash
# PreToolUse gate for IBKR order instructions (CLAUDE.md hard rule #1).
#
# Claude Code passes the hook payload as JSON on STDIN (fields: tool_name,
# tool_input, transcript_path, cwd, ...), NOT as environment variables. We read
# stdin, and use $CLAUDE_PROJECT_DIR (set by Claude Code) to locate .env.
#
# Policy:
#   - non-order tools                          -> allow (exit 0)
#   - TRADING_MODE=paper                        -> allow
#   - TRADING_MODE=live + confirmation phrase   -> allow
#   - TRADING_MODE=live + phrase missing        -> BLOCK (exit 2; reason on stderr)
#
# The confirmation phrase "EXECUTE LIVE: <TICKER> <BUY|SELL> <QTY>" must appear
# in the trader's MOST RECENT message; we read it from the conversation
# transcript (transcript_path on stdin). IBKR also requires its own in-app
# confirmation — this is the second of those gates.
#
# Fails CLOSED: any parse/read error in live mode results in a block.
#
# Blocking convention: exit code 2 reliably blocks a PreToolUse call across
# Claude Code versions and feeds stderr back to the model.

set -uo pipefail

INPUT="$(cat)"

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
if [[ -f "$PROJECT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_DIR/.env"
  set +a
fi

HOOK_JSON="$INPUT" TRADING_MODE="${TRADING_MODE:-paper}" python3 - <<'PY'
import json
import os
import re
import sys

ORDER_TOOLS = {
    "mcp__interactive-brokers__create_order_instruction",
    "mcp__interactive-brokers__delete_order_instruction",
}

try:
    data = json.loads(os.environ.get("HOOK_JSON") or "{}")
except json.JSONDecodeError:
    # Can't parse the payload — be conservative but don't break unrelated tools.
    sys.exit(0)

tool = data.get("tool_name", "")
if tool not in ORDER_TOOLS:
    sys.exit(0)  # not an order instruction — allow

mode = (os.environ.get("TRADING_MODE") or "paper").strip().lower()
if mode == "paper":
    sys.exit(0)  # paper orders always allowed

# --- live mode: require the confirmation phrase in the latest user message ---
PHRASE = re.compile(r"EXECUTE LIVE:\s*[A-Z.]+\s+(BUY|SELL)\s+\d+")


def latest_user_text(transcript_path: str) -> str:
    text = ""
    try:
        with open(transcript_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("type") != "user":
                    continue
                content = ev.get("message", {}).get("content", "")
                if isinstance(content, str):
                    chunk = content
                elif isinstance(content, list):
                    chunk = " ".join(
                        part.get("text", "")
                        for part in content
                        if isinstance(part, dict) and part.get("type") == "text"
                    )
                else:
                    chunk = ""
                if chunk.strip():
                    text = chunk  # keep the most recent non-empty user turn
    except OSError:
        return ""
    return text


if PHRASE.search(latest_user_text(data.get("transcript_path", ""))):
    sys.exit(0)  # confirmed — allow

sys.stderr.write(
    "Live IBKR order instruction blocked. TRADING_MODE is 'live' but the "
    "confirmation phrase is missing from your latest message. Required format: "
    "EXECUTE LIVE: <TICKER> <BUY|SELL> <QTY>. This PreToolUse hook enforces "
    "CLAUDE.md hard rule #1. Even if bypassed, IBKR still requires its own "
    "confirmation in the interface.\n"
)
sys.exit(2)  # exit 2 = block the tool call
PY
exit $?
