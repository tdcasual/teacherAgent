from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_exam_upload_parse_service_mypy_clean() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    targets = [
        repo_root / "services" / "api" / "exam_upload_parse_service.py",
        repo_root / "services" / "api" / "exam_upload_parse",
    ]
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--follow-imports=skip",
            *[str(target) for target in targets],
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    output = f"{proc.stdout}\n{proc.stderr}".strip()
    assert proc.returncode == 0, output
