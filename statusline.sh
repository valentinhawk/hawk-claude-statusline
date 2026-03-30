#!/bin/bash
# ============================================================================
# ✦ Hawk Claude Statusline - © 2026 ValentinHawk. All rights reserved.
# Thin wrapper - delegates to Python script
# ============================================================================
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/statusline.py" 2>/dev/null || exec python "$SCRIPT_DIR/statusline.py"
