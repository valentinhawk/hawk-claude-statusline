#!/bin/bash
# ============================================================================
# ✦ Hawk Claude Statusline - Installer
# © 2026 ValentinHawk. All rights reserved.
# https://github.com/valentinhawk/hawk-claude-statusline
# ============================================================================
set -e

SCRIPTS_DIR="$HOME/.claude/scripts"
SETTINGS_FILE="$HOME/.claude/settings.json"
REPO_URL="https://raw.githubusercontent.com/valentinhawk/hawk-claude-statusline/main"

echo ""
echo "  ✦ Hawk Claude Statusline"
echo "  Installing..."
echo ""

# -- Find a working Python (Windows often only has 'py' or 'python') ----------
PY=""
for c in py python python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys" >/dev/null 2>&1; then
        PY="$c"; break
    fi
done
if [ -z "$PY" ]; then
    echo "  [!] Python 3 not found. Install it from https://python.org and re-run."
    exit 1
fi

# -- Download the scripts -----------------------------------------------------
mkdir -p "$SCRIPTS_DIR"
curl -fsSL "$REPO_URL/statusline.py" -o "$SCRIPTS_DIR/statusline.py"
curl -fsSL "$REPO_URL/statusline.sh" -o "$SCRIPTS_DIR/statusline.sh"
chmod +x "$SCRIPTS_DIR/statusline.sh"

# -- Wire up settings.json (create or merge, never clobber other keys) --------
"$PY" - "$SETTINGS_FILE" <<'PYEOF'
import json, os, sys
path = sys.argv[1]
os.makedirs(os.path.dirname(path), exist_ok=True)
try:
    with open(path) as f:
        cfg = json.load(f)
    if not isinstance(cfg, dict):
        cfg = {}
except Exception:
    cfg = {}
cfg["statusLine"] = {
    "type": "command",
    "command": "bash ~/.claude/scripts/statusline.sh",
    "timeout": 10000,
}
with open(path, "w") as f:
    json.dump(cfg, f, indent=2)
print("  [+] statusLine configured in", path)
PYEOF

echo ""
echo "  ✦ Done! Restart Claude Code to see your statusline."
echo ""
