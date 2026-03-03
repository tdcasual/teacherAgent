from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_complexity_budget_file_exists_and_has_required_keys() -> None:
    path = Path("config/function_complexity_budget.json")
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "total_c901_max" in payload
    assert "critical_files" in payload
    assert isinstance(payload.get("critical_files"), dict)


def test_complexity_budget_script_passes() -> None:
    root = Path(__file__).resolve().parent.parent
    script = root / "scripts" / "quality" / "check_complexity_budget.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
