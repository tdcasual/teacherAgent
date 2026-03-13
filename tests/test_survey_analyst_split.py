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


def test_survey_analyst_fallback_hotspot_removed() -> None:
    target = "services/api/specialist_agents/survey_analyst.py"
    source = Path(target).read_text(encoding="utf-8")
    assert "def _fallback_artifact(" in source
    issues = _issues(target)
    assert not issues, f"C901 issues still present: {issues}"
