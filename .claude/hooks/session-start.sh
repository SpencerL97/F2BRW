#!/bin/bash
# SessionStart hook for Claude Code on the web.
# Reproduces the README "Install" steps so the Trading Sidekick repo is
# usable the moment a fresh remote container boots. Idempotent and
# non-interactive; safe to run on every session start.
set -euo pipefail

# Only run setup in the remote (Claude Code on the web) environment.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$PROJECT_DIR"

# 1. Isolated virtualenv. The container's system Python has Debian-managed
#    packages that pip cannot safely upgrade, so install into .venv instead.
if [ ! -x .venv/bin/python ]; then
  python -m venv .venv
fi
.venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt

# 2. Make the venv the default interpreter for the rest of the session.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export PATH=\"$PROJECT_DIR/.venv/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"
  echo "export VIRTUAL_ENV=\"$PROJECT_DIR/.venv\"" >> "$CLAUDE_ENV_FILE"
fi

# 3. Local .env from template if absent. Gitignored; defaults to TRADING_MODE=paper.
if [ ! -f .env ]; then
  cp .env.template .env
fi

# 4. Journal database. init_db.py is idempotent (CREATE TABLE IF NOT EXISTS).
.venv/bin/python scripts/init_db.py

# 5. Deterministic safety hooks must stay executable.
chmod +x .claude/hooks/*.sh

echo "Trading Sidekick setup complete (venv: .venv)."
