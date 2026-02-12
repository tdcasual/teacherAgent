from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_queue_runtime_module_mypy_clean() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    target = repo_root / "services" / "api" / "runtime" / "queue_runtime.py"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--follow-imports=skip",
            str(target),
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    output = f"{proc.stdout}\n{proc.stderr}".strip()
    assert proc.returncode == 0, output
