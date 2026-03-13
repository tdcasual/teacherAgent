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


def test_upload_llm_hotspot_removed() -> None:
    target = "services/api/upload_llm_service.py"
    source = Path(target).read_text(encoding="utf-8")
    assert "def _find_student_header_row(" in source
    assert "def _resolve_student_columns(" in source
    assert "def _format_student_preview_line(" in source
    assert "def _extract_xlsx_students_compact(" in source
    issues = _issues(target)
    assert not issues, f"C901 issues still present: {issues}"
