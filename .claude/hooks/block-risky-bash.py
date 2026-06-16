#!/usr/bin/env python3
"""PreToolUse Bash hook: block destructive commands."""
import json
import re
import sys

PATTERNS = [
    r"rm\s+-rf?\s+(/|~|\.)(\s|$|/)",
    r"docker\s+system\s+prune.*--volumes",
    r"git\s+push\s+(--force|-f)\b.*\b(main|master)\b",
    r"git\s+reset\s+--hard\s+origin/(main|master)",
    r"\bDROP\s+DATABASE\b",
]

data = json.load(sys.stdin)
cmd = data.get("tool_input", {}).get("command", "")
for p in PATTERNS:
    if re.search(p, cmd, re.IGNORECASE):
        sys.stdout.write(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Blocked by project hook (risky command): {cmd}",
            }
        }))
        sys.exit(0)
