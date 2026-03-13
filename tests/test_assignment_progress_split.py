from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from services.api.assignment_progress_service import _attempt_meets_min_graded_total


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


def test_assignment_progress_attempt_hotspot_removed() -> None:
    target = "services/api/assignment_progress_service.py"
    source = Path(target).read_text(encoding="utf-8")
    assert "def _attempt_meets_min_graded_total(" in source
    issues = _issues(target)
    assert not issues, f"C901 issues still present: {issues}"


def test_attempt_meets_min_graded_total_falls_back_to_items_length() -> None:
    assert _attempt_meets_min_graded_total(
        {"items": [{"q": 1}, {"q": 2}], "valid_submission": True},
        2,
    ) is True
    assert _attempt_meets_min_graded_total(
        {"items": [{"q": 1}], "valid_submission": True},
        2,
    ) is False
