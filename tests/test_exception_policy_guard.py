from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_exception_policy_guard_script_passes() -> None:
    root = Path(__file__).resolve().parent.parent
    script = root / "scripts" / "quality" / "check_exception_policy.py"
    result = subprocess.run(
        [sys.executable, str(script), "--quiet"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
