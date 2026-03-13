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


def test_exam_score_processing_hotspots_removed() -> None:
    target = "services/api/exam_score_processing_service.py"
    source = Path(target).read_text(encoding="utf-8")
    assert "def build_exam_rows_from_parsed_scores(" in source
    assert "def parse_exam_answer_key_text(" in source
    issues = _issues(target)
    assert not issues, f"C901 issues still present: {issues}"
