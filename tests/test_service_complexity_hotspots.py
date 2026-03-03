from __future__ import annotations

import json
import subprocess
import sys


def _issues(path: str) -> list[dict]:
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


def test_exam_range_and_skill_loader_hotspots_removed() -> None:
    targets = [
        "services/api/exam_range_service.py",
        "services/api/skills/loader.py",
    ]
    issues = [item for target in targets for item in _issues(target)]
    assert not issues, f"C901 issues still present: {issues}"
