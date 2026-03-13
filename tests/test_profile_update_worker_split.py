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


def test_profile_update_worker_hotspot_removed() -> None:
    target = "services/api/workers/profile_update_worker_service.py"
    source = Path(target).read_text(encoding="utf-8")
    assert "def _drain_profile_update_batch(" in source
    assert "def _merge_profile_update_batch(" in source
    assert "def _process_profile_update_batch(" in source
    assert "def profile_update_worker_loop(" in source
    issues = _issues(target)
    assert not issues, f"C901 issues still present: {issues}"
