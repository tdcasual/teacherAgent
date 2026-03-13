from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _issues(path: str) -> list[dict]:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            path,
            "--select",
            "C901",
            "--config",
            "lint.mccabe.max-complexity=10",
            "--output-format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (proc.stdout or "").strip()
    return json.loads(output) if output else []


def test_subject_score_guard_hotspot_removed() -> None:
    target = "services/api/subject_score_guard_service.py"
    source = Path(target).read_text(encoding="utf-8")
    assert "def _iter_overview_subject_texts(" in source
    issues = _issues(target)
    assert not issues, f"C901 issues still present: {issues}"
