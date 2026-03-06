from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_TARGETS = [
    "services/api/auth_registry_service.py",
    "services/api/chart_executor.py",
    "services/api/teacher_memory_core.py",
    "services/api/exam_upload_parse_service.py",
]


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
            "lint.mccabe.max-complexity=14",
            "--output-format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (proc.stdout or "").strip()
    return json.loads(output) if output else []


def test_target_files_exist() -> None:
    for raw in _TARGETS:
        assert Path(raw).exists(), f"missing target file: {raw}"


def test_target_files_have_no_c901_regressions() -> None:
    issues = [item for target in _TARGETS for item in _issues(target)]
    assert not issues, f"C901 issues still present: {issues}"
