from __future__ import annotations

import json
import subprocess
import sys


def _ruff_c901(path: str) -> list[dict]:
    cmd = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        path,
        "--select",
        "C901",
        "--config",
        "lint.mccabe.max-complexity=14",
        "--output-format",
        "json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    out = proc.stdout.strip()
    return json.loads(out) if out else []


def test_auth_and_chat_routes_have_no_c901_over_14() -> None:
    targets = [
        "services/api/routes/auth_routes.py",
        "services/api/routes/chat_routes.py",
    ]
    issues: list[dict] = []
    for target in targets:
        issues.extend(_ruff_c901(target))
    assert not issues, f"C901 issues still present: {issues}"
