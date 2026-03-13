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


def test_chat_worker_hotspot_removed() -> None:
    target = "services/api/workers/chat_worker_service.py"
    source = Path(target).read_text(encoding="utf-8")
    assert "def _chat_rescan_pending_jobs(" in source
    assert "def _claim_next_chat_job(" in source
    assert "def _handle_failed_chat_job(" in source
    assert "def _finalize_chat_job(" in source
    assert "def chat_job_worker_loop(" in source
    issues = _issues(target)
    assert not issues, f"C901 issues still present: {issues}"
