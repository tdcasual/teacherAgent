from __future__ import annotations

import json
from pathlib import Path


def test_backend_quality_budget_file_exists_and_has_keys() -> None:
    path = Path("config/backend_quality_budget.json")
    assert path.exists(), "missing quality budget file"
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in ("ruff_max", "mypy_max", "app_core_max_lines"):
        assert key in data, f"missing key: {key}"
