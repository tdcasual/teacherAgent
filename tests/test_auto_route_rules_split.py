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


def test_auto_route_rules_hotspot_removed() -> None:
    target = "services/api/skills/auto_route_rules.py"
    source = Path(target).read_text(encoding="utf-8")
    assert "def _score_homework_generator(" in source
    assert "def _score_lesson_capture(" in source
    assert "def _score_core_examples(" in source
    assert "def _score_student_focus(" in source
    assert "def _score_student_coach_teacher(" in source
    assert "def _score_teacher_ops(" in source
    assert "def _score_teacher_skill(" in source
    issues = _issues(target)
    assert not issues, f"C901 issues still present: {issues}"
