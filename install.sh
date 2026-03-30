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

mkdir -p "$SCRIPTS_DIR"

curl -sL "$REPO_URL/statusline.py" -o "$SCRIPTS_DIR/statusline.py"
curl -sL "$REPO_URL/statusline.sh" -o "$SCRIPTS_DIR/statusline.sh"
chmod +x "$SCRIPTS_DIR/statusline.sh"

if [ -f "$SETTINGS_FILE" ]; then
    if grep -q '"statusLine"' "$SETTINGS_FILE"; then
        echo "  [!] statusLine already configured in settings.json"
        echo "  Update it manually to:"
        echo ""
        echo '  "statusLine": {'
        echo '    "type": "command",'
        echo '    "command": "bash ~/.claude/scripts/statusline.sh",'
        echo '    "timeout": 10000'
        echo '  }'
    else
        python3 -c "
import json
with open('$SETTINGS_FILE', 'r') as f:
    cfg = json.load(f)
cfg['statusLine'] = {
    'type': 'command',
    'command': 'bash ~/.claude/scripts/statusline.sh',
    'timeout': 10000
}
with open('$SETTINGS_FILE', 'w') as f:
    json.dump(cfg, f, indent=2)
print('  [+] statusLine added to settings.json')
"
    fi
else
    echo '  [!] No settings.json found. Run: claude config'
fi

echo ""
echo "  ✦ Done! Restart Claude Code to see your new statusline."
echo ""
