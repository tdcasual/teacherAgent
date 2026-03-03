from __future__ import annotations

import json
import subprocess
import sys


def test_backend_quality_budget_print_only_within_budget() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/quality/check_backend_quality_budget.py", "--print-only"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    metrics = payload["metrics"]
    budget = payload["budget"]

    assert metrics["ruff_errors"] <= budget["ruff_max"]
    assert metrics["mypy_errors"] <= budget["mypy_max"]
