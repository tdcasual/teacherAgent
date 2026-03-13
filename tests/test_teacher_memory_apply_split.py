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


def test_teacher_memory_apply_hotspot_removed() -> None:
    target = "services/api/teacher_memory_apply_service.py"
    source = Path(target).read_text(encoding="utf-8")
    assert "def _load_apply_record(" in source
    assert "def _reject_record(" in source
    assert "def _resolve_apply_target_path(" in source
    assert "def _build_memory_entry(" in source
    assert "def _maybe_index_mem0(" in source
    assert "def teacher_memory_apply(" in source
    issues = _issues(target)
    assert not issues, f"C901 issues still present: {issues}"
