#!/usr/bin/env python3
"""PostToolUse Edit|Write|MultiEdit hook: format the touched file by extension.

Silently no-ops if the relevant formatter isn't installed.
"""
import json
import shutil
import subprocess
import sys

data = json.load(sys.stdin)
ti = data.get("tool_input", {})
tr = data.get("tool_response", {})
fpath = ti.get("file_path") or tr.get("filePath") or ""

if not fpath:
    sys.exit(0)

low = fpath.lower()


def run(cmd):
    if shutil.which(cmd[0]) is None:
        return
    try:
        subprocess.run(cmd, check=False, capture_output=True, timeout=20)
    except Exception:
        pass


if low.endswith(".py"):
    run(["black", "-q", fpath])
elif low.endswith(".sql") and "/dbt/" in fpath.replace("\\", "/"):
    run(["sqlfluff", "fix", "--dialect", "trino", fpath])
elif low.endswith((".yaml", ".yml", ".json")):
    run(["prettier", "--write", fpath])
