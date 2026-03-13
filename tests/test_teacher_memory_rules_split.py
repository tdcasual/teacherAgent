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


def test_teacher_memory_rules_hotspot_removed() -> None:
    target = "services/api/teacher_memory_rules_service.py"
    source = Path(target).read_text(encoding="utf-8")
    assert "def _source_priority_base(" in source
    assert "def _target_priority_bonus(" in source
    assert "def _text_priority_adjustment(" in source
    assert "def _meta_priority_bonus(" in source
    assert "def teacher_memory_priority_score(" in source
    issues = _issues(target)
    assert not issues, f"C901 issues still present: {issues}"
