#!/bin/bash
# ============================================================================
# ✦ Hawk Claude Statusline - © 2026 ValentinHawk. All rights reserved.
# Thin wrapper - finds a working Python across macOS / Linux / Windows.
# ============================================================================
DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$DIR/statusline.py"

# Explicit override wins (e.g. CLAUDE_PY=/path/to/python in your shell)
if [ -n "$CLAUDE_PY" ] && "$CLAUDE_PY" -c "import sys" >/dev/null 2>&1; then
    exec "$CLAUDE_PY" "$SCRIPT"
fi

# Try common launchers; verify each actually runs (skips the Windows Store stub
# that hijacks "python3" on a fresh machine and breaks the naive `|| python`).
for py in py python python3; do
    if command -v "$py" >/dev/null 2>&1 && "$py" -c "import sys" >/dev/null 2>&1; then
        exec "$py" "$SCRIPT"
    fi
done

# Nothing usable: stay silent so Claude Code falls back to its default bar.
exit 0
