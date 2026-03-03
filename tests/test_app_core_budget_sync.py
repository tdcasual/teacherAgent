from __future__ import annotations

import json
from pathlib import Path


def test_app_core_guardrail_thresholds_sync_with_budget() -> None:
    budget = json.loads(Path("config/backend_quality_budget.json").read_text(encoding="utf-8"))
    app_core_max = int(budget["app_core_max_lines"])
    assert app_core_max > 0

    structure_source = Path("tests/test_app_core_structure.py").read_text(encoding="utf-8")
    decomposition_source = Path("tests/test_app_core_decomposition.py").read_text(encoding="utf-8")

    assert "backend_quality_budget.json" in structure_source
    assert "backend_quality_budget.json" in decomposition_source

    assert "assert line_count < 900" not in structure_source
    assert "assert line_count < 1400" not in decomposition_source
