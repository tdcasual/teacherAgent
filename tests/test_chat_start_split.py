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


def test_chat_start_analysis_target_hotspot_removed() -> None:
    target = "services/api/chat_start_service.py"
    source = Path(target).read_text(encoding="utf-8")
    assert "def _normalize_analysis_target_payload(" not in source
    assert "extract_report_id_from_text" not in source
    issues = _issues(target)
    assert not issues, f"C901 issues still present: {issues}"
