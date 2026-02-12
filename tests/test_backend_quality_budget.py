from __future__ import annotations

import json
from pathlib import Path

_BASELINE_BUDGET = {
    "ruff_max": 745,
    "mypy_max": 482,
    "app_core_max_lines": 700,
}


def _load_budget() -> dict[str, int]:
    path = Path("config/backend_quality_budget.json")
    assert path.exists(), "missing quality budget file"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "quality budget file must be a JSON object"
    return data


def test_backend_quality_budget_file_exists_and_has_keys() -> None:
    data = _load_budget()
    for key in ("ruff_max", "mypy_max", "app_core_max_lines"):
        assert key in data, f"missing key: {key}"


def test_quality_budget_is_tightened_against_baseline() -> None:
    data = _load_budget()
    for key, baseline in _BASELINE_BUDGET.items():
        value = int(data[key])
        assert value > 0, f"{key} must be a positive integer"
        assert value < baseline, f"{key}={value} must be lower than baseline={baseline}"
