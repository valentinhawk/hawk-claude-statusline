#!/usr/bin/env python
# ============================================================================
# ✦ Hawk Claude Statusline - © 2026 ValentinHawk. All rights reserved.
# Free to use, modify, and distribute with attribution.
# https://github.com/valentinhawk/hawk-claude-statusline
# ============================================================================
"""
3-line powerline status bar for Claude Code.
L1: 🧠 Model  💰 $cost  ⏱ 5h:X% ~reset  📅 7d:X% ~reset
L2: 📊 [bar] X% total/size  📥 i:input  📤 o:output
L3: 📂 Dir  🌿 branch  🔥 +add -del ~mod  🔄 ↑ahead ↓behind
"""

import sys
import json
import subprocess
import os
import re
import time
import stat
import urllib.request
import urllib.error
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

# -- ANSI --
RESET = "\033[0m"
BOLD = "\033[1m"
FG_WHITE = "\033[38;5;255m"

# ============================================================================
# Palette: dodger blue (27) accent + gray gradient (236 -> 239 -> 243)
# ============================================================================

BG_ACCENT = "\033[48;5;27m"  ; FG_ACCENT = "\033[38;5;27m"
BG_G1 = "\033[48;5;236m"     ; FG_G1 = "\033[38;5;236m"
BG_G2 = "\033[48;5;239m"     ; FG_G2 = "\033[38;5;239m"
BG_G3 = "\033[48;5;243m"     ; FG_G3 = "\033[38;5;243m"

# Powerline + symbols
PL = "\ue0b0"
BLOCK = "\u2588"
SHADE = "\u2591"
BULLET = "\u25cf"
ELLIP = "\u2026"
BAR_WIDTH = 12

# -- Config --
_NO_WIN = 0x08000000 if os.name == "nt" else 0
USAGE_API_URL = "https://api.anthropic.com/api/oauth/usage"
USAGE_API_BETA = "oauth-2025-04-20"
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "scripts")
USAGE_CACHE = os.path.join(CACHE_DIR, ".usage_cache.json")
GIT_CACHE = os.path.join(CACHE_DIR, ".git_cache.json")
USAGE_TTL = 60
GIT_TTL = 5
CRED_PATH = os.path.join(os.path.expanduser("~"), ".claude", ".credentials.json")


# ============================================================================
# Helpers
# ============================================================================

def fmt_tok(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def pct_fg(pct):
    """Colored percentage: green < 50, yellow < 75, red >= 75."""
    if pct < 50:
        return "\033[92m"
    if pct < 75:
        return "\033[93m"
    return "\033[91m"


def _restrict(path):
    """Restrict file permissions to owner only (security for cache/creds)."""
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass


def git_cmd(cwd, *args):
    try:
        r = subprocess.run(
            ["git", "-C", cwd, "--no-optional-locks"] + list(args),
            capture_output=True, text=True, timeout=2, creationflags=_NO_WIN,
        )
        return r.stdout.strip()
    except Exception:
        return ""


# ============================================================================
# Powerline segment
# ============================================================================

def seg(icon, text, bg, fg_bg, next_bg=None, last=False):
    """Segment with icon, text, colored background, and arrow transition."""
    content = f"{bg}{FG_WHITE}{BOLD} {icon} {text} {RESET}"
    if next_bg is not None:
        arrow = f"{next_bg}{fg_bg}{PL}{RESET}"
    elif last:
        arrow = f"{RESET}{fg_bg}{PL}{RESET} "
    else:
        arrow = f"{fg_bg}{PL}{RESET}"
    return content + arrow


# ============================================================================
# Data extractors
# ============================================================================

def get_model(d):
    full = d.get("model", {}).get("display_name", "")
    if full:
        return full.replace("Claude ", "")
    return d.get("model", {}).get("id", "unknown").replace("claude-", "")


def get_dir(d):
    cwd = d.get("workspace", {}).get("current_dir", d.get("cwd", "?"))
    home = os.path.expanduser("~").replace("\\", "/")
    c = cwd.replace("\\", "/")
    if c.startswith(home):
        c = "~" + c[len(home):]
    parts = c.split("/")
    if len(parts) > 3:
        return ELLIP + "/" + "/".join(parts[-2:])
    return c


def get_git(d):
    """Get git info with 5s cache + parallel commands."""
    cwd = d.get("workspace", {}).get("current_dir", d.get("cwd", ""))
    if not cwd:
        return None

    # Check git cache
    try:
        if os.path.exists(GIT_CACHE):
            with open(GIT_CACHE, "r") as f:
                cache = json.load(f)
            if cache.get("cwd") == cwd and time.time() - cache.get("ts", 0) < GIT_TTL:
                return cache.get("data")
    except Exception:
        pass

    # Quick check: is this a git repo?
    branch = git_cmd(cwd, "branch", "--show-current")
    if not branch:
        return None

    # Run remaining git commands in parallel
    with ThreadPoolExecutor(max_workers=4) as pool:
        f_status = pool.submit(git_cmd, cwd, "status", "--porcelain")
        f_diff = pool.submit(git_cmd, cwd, "diff", "--shortstat")
        f_cached = pool.submit(git_cmd, cwd, "diff", "--cached", "--shortstat")
        f_upstream = pool.submit(git_cmd, cwd, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")

    porc = f_status.result()
    staged = mod = add = dele = 0
    if porc:
        plines = [l for l in porc.split("\n") if l]
        staged = sum(1 for l in plines if len(l) >= 2 and l[0] in "AMDR")
        mod = sum(1 for l in plines if len(l) >= 2 and l[1] == "M")
        add = sum(1 for l in plines if l.startswith("??"))
        dele = sum(1 for l in plines if len(l) >= 2 and (l[0] == "D" or l[1] == "D"))

    # Line-level diff
    lines_added = lines_deleted = 0
    for stat_out in [f_diff.result(), f_cached.result()]:
        if stat_out:
            m_ins = re.search(r"(\d+) insertion", stat_out)
            m_del = re.search(r"(\d+) deletion", stat_out)
            if m_ins:
                lines_added += int(m_ins.group(1))
            if m_del:
                lines_deleted += int(m_del.group(1))

    # Ahead/behind
    ahead = behind = 0
    upstream = f_upstream.result()
    if upstream:
        ab = git_cmd(cwd, "rev-list", "--left-right", "--count", f"HEAD...{upstream}")
        if ab and "\t" in ab:
            p = ab.split("\t")
            ahead = int(p[0]) if p[0].isdigit() else 0
            behind = int(p[1]) if p[1].isdigit() else 0

    clean = not (staged or mod or add or dele or lines_added or lines_deleted)
    result = {
        "branch": branch, "clean": clean,
        "staged": staged, "modified": mod, "added": add, "deleted": dele,
        "lines_added": lines_added, "lines_deleted": lines_deleted,
        "ahead": ahead, "behind": behind,
    }

    # Write git cache
    try:
        with open(GIT_CACHE, "w") as f:
            json.dump({"cwd": cwd, "ts": time.time(), "data": result}, f)
        _restrict(GIT_CACHE)
    except Exception:
        pass

    return result


# Pricing per model ($/M tokens): (input, output, cache_create, cache_read)
MODEL_PRICING = {
    "opus":   (15.0,  75.0,  18.75,  1.875),
    "sonnet": (3.0,   15.0,  3.75,   0.375),
    "haiku":  (0.80,  4.0,   1.0,    0.10),
}


def _detect_pricing(d):
    """Auto-detect pricing from model id/name."""
    model_id = d.get("model", {}).get("id", "").lower()
    for key in MODEL_PRICING:
        if key in model_id:
            return MODEL_PRICING[key]
    return MODEL_PRICING["opus"]  # default fallback


def get_ctx(d):
    ctx = d.get("context_window", {})
    size = ctx.get("context_window_size", 200000)
    pct = ctx.get("used_percentage", 0)
    u = ctx.get("current_usage") or {}
    inp = (u.get("input_tokens", 0) or 0)
    cache_read = (u.get("cache_read_input_tokens", 0) or 0)
    cache_create = (u.get("cache_creation_input_tokens", 0) or 0)
    out = u.get("output_tokens", 0) or 0
    total = inp + cache_read + cache_create + out

    # Dynamic pricing based on model
    p_in, p_out, p_cc, p_cr = _detect_pricing(d)
    cost = (inp * p_in + cache_create * p_cc + cache_read * p_cr + out * p_out) / 1_000_000

    return {"total": total, "size": size, "pct": pct, "input": inp + cache_read, "output": out, "cost": cost}


# ============================================================================
# Usage API (cached 60s, stale fallback)
# ============================================================================

def _read_cache(allow_stale=False):
    try:
        if os.path.exists(USAGE_CACHE):
            with open(USAGE_CACHE, "r") as f:
                cache = json.load(f)
            ttl = cache.get("ttl", USAGE_TTL)
            if time.time() - cache.get("ts", 0) < ttl:
                return cache.get("data")
            if allow_stale:
                return cache.get("data")
    except Exception:
        pass
    return None


def _write_cache(data, ttl=None):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        entry = {"ts": time.time(), "data": data}
        if ttl is not None:
            entry["ttl"] = ttl
        with open(USAGE_CACHE, "w") as f:
            json.dump(entry, f)
        _restrict(USAGE_CACHE)
    except Exception:
        pass


def fetch_usage():
    cached = _read_cache()
    if cached is not None:
        return cached
    stale = _read_cache(allow_stale=True) or {}
    try:
        if not os.path.exists(CRED_PATH):
            return stale
        with open(CRED_PATH, "r") as f:
            creds = json.load(f)
        oauth = creds.get("claudeAiOauth", {})
        expires_at = oauth.get("expiresAt")
        if expires_at and time.time() * 1000 >= expires_at:
            return stale
        token = oauth.get("accessToken", "")
        if not token:
            return stale
        req = urllib.request.Request(
            USAGE_API_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "anthropic-beta": USAGE_API_BETA,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "hawk-claude-statusline/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if not isinstance(data, dict):
                return stale
            safe = {}
            for key in ("five_hour", "seven_day", "extra_usage"):
                if key in data and isinstance(data[key], dict):
                    safe[key] = {
                        k: v for k, v in data[key].items()
                        if k in ("utilization", "resets_at", "is_enabled", "monthly_limit", "used_credits")
                    }
            _write_cache(safe)
            return safe
    except urllib.error.HTTPError as e:
        if e.code == 429:
            _write_cache({"_unavailable": True}, ttl=30)
        return stale
    except Exception:
        return stale


def fmt_reset_time(resets_at):
    if not resets_at:
        return ""
    try:
        reset_dt = datetime.fromisoformat(resets_at)
        now = datetime.now(timezone.utc)
        diff = (reset_dt - now).total_seconds()
        if diff <= 0:
            return ""
        d = int(diff // 86400)
        h = int((diff % 86400) // 3600)
        m = int((diff % 3600) // 60)
        if d > 0:
            return f" ~{d}d{h:02d}h"
        if h > 0:
            return f" ~{h}h{m:02d}m"
        return f" ~{m}m"
    except Exception:
        return ""


# ============================================================================
# L1: 🧠 Model  💰 $cost  ⏱ 5h:X%  📅 7d:X%
# ============================================================================

def build_line1(d, usage_raw):
    ctx = get_ctx(d)
    fh = usage_raw.get("five_hour", {}) if usage_raw else {}
    sd = usage_raw.get("seven_day", {}) if usage_raw else {}

    # Model
    s1 = seg("\U0001f9e0", get_model(d), BG_ACCENT, FG_ACCENT, BG_G1)

    # Cost
    s2 = seg("\U0001f4b0", f"${ctx['cost']:.2f}", BG_G1, FG_G1, BG_G2)

    # 5h (always shown)
    if fh and fh.get("utilization") is not None:
        p5 = int(fh["utilization"])
        pc5 = pct_fg(p5)
        r5 = fmt_reset_time(fh.get("resets_at", ""))
        t5 = f"5h:{pc5}{p5}%{RESET}{BG_G2}{FG_WHITE}{BOLD}{r5}"
    else:
        t5 = "5h: -"
    s3 = seg("\u23f1", t5, BG_G2, FG_G2, BG_G3)

    # 7d (always shown)
    if sd and sd.get("utilization") is not None:
        p7 = int(sd["utilization"])
        pc7 = pct_fg(p7)
        r7 = fmt_reset_time(sd.get("resets_at", ""))
        t7 = f"7d:{pc7}{p7}%{RESET}{BG_G3}{FG_WHITE}{BOLD}{r7}"
    else:
        t7 = "7d: -"
    s4 = seg("\U0001f4c5", t7, BG_G3, FG_G3, last=True)

    return s1 + s2 + s3 + s4


# ============================================================================
# L2: 📊 [bar] X% total/size  📥 i:input  📤 o:output
# ============================================================================

def build_line2(d):
    ctx = get_ctx(d)
    pct = int(ctx["pct"])
    pc = pct_fg(pct)
    filled = pct * BAR_WIDTH // 100
    bar = "[" + BLOCK * filled + SHADE * (BAR_WIDTH - filled) + "]"
    ctx_text = f"{bar} {pc}{pct}%{RESET}{BG_ACCENT}{FG_WHITE}{BOLD} {fmt_tok(ctx['total'])}/{fmt_tok(ctx['size'])}"

    s1 = seg("\U0001f4ca", ctx_text, BG_ACCENT, FG_ACCENT, BG_G1)
    s2 = seg("\U0001f4e5", f"i:{fmt_tok(ctx['input'])}", BG_G1, FG_G1, BG_G2)
    s3 = seg("\U0001f4e4", f"o:{fmt_tok(ctx['output'])}", BG_G2, FG_G2, last=True)

    return s1 + s2 + s3


# ============================================================================
# L3: 📂 Dir  🌿 branch  🔥 changes  🔄 sync  (always 4 segments)
# ============================================================================

def build_line3(d):
    directory = get_dir(d)
    git = get_git(d)

    s1 = seg("\U0001f4c2", directory, BG_ACCENT, FG_ACCENT, BG_G1)

    if not git:
        s2 = seg("\U0001f33f", "-", BG_G1, FG_G1, BG_G2)
        s3 = seg("\U0001f525", "-", BG_G2, FG_G2, BG_G3)
        s4 = seg("\U0001f504", "-", BG_G3, FG_G3, last=True)
        return s1 + s2 + s3 + s4

    branch = git["branch"]

    # Changes
    parts = []
    if git["lines_added"]:
        parts.append(f"+{git['lines_added']}")
    if git["lines_deleted"]:
        parts.append(f"-{git['lines_deleted']}")
    if git["staged"]:
        parts.append(f"{BULLET}{git['staged']}")
    if git["modified"]:
        parts.append(f"~{git['modified']}")
    if git["added"]:
        parts.append(f"?{git['added']}")
    change_text = " ".join(parts) if parts else ("-" if git["clean"] else "-")

    # Sync
    sync_parts = []
    if git["ahead"]:
        sync_parts.append(f"\u2191{git['ahead']}")
    if git["behind"]:
        sync_parts.append(f"\u2193{git['behind']}")
    sync_text = " ".join(sync_parts) if sync_parts else "-"

    # Always 4 segments
    s2 = seg("\U0001f33f", branch, BG_G1, FG_G1, BG_G2)
    s3 = seg("\U0001f525", change_text, BG_G2, FG_G2, BG_G3)
    s4 = seg("\U0001f504", sync_text, BG_G3, FG_G3, last=True)

    return s1 + s2 + s3 + s4


# ============================================================================
# Main
# ============================================================================

def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        d = json.loads(sys.stdin.read())
    except Exception:
        return

    usage_raw = fetch_usage()
    print(build_line1(d, usage_raw) + RESET)
    print(build_line2(d) + RESET)
    print(build_line3(d) + RESET)


if __name__ == "__main__":
    main()
