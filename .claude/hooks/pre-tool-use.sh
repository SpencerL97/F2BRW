#!/usr/bin/env bash
# Blocks IBKR order-instruction calls unless TRADING_MODE=paper OR the user
# prompt contains the explicit live-confirmation phrase.
#
# IBKR's MCP exposes 'order instructions' rather than direct order submission.
# Instructions still need explicit confirmation in the IBKR interface — but we
# add a second gate here so the model can't draft a live instruction casually.

set -euo pipefail

if [[ -f "$(pwd)/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$(pwd)/.env"
  set +a
fi

TOOL_NAME="${CLAUDE_TOOL_NAME:-}"
USER_PROMPT="${CLAUDE_USER_PROMPT:-}"
MODE="${TRADING_MODE:-paper}"

case "$TOOL_NAME" in
  mcp__interactive-brokers__create_order_instruction|mcp__interactive-brokers__delete_order_instruction)
    ;;
  *)
    exit 0
    ;;
esac

if [[ "$MODE" == "paper" ]]; then
  exit 0
fi

if grep -qE "EXECUTE LIVE: [A-Z]+ (BUY|SELL) [0-9]+" <<<"$USER_PROMPT"; then
  exit 0
fi

cat <<'JSON'
{
  "decision": "block",
  "reason": "Live IBKR order instruction blocked. TRADING_MODE is 'live' but the confirmation phrase is missing. Required format: EXECUTE LIVE: <TICKER> <BUY|SELL> <QTY>. The PreToolUse hook is enforcing CLAUDE.md hard rule #1. Note: even if this is bypassed, IBKR will still require you to confirm the instruction in its own interface."
}
JSON
exit 0
